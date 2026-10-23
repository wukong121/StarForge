"""Read-only host evidence; tool availability never certifies game compatibility."""

import math
import os
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, NotRequired, TypedDict

COMMAND_TIMEOUT = 3.0
MAX_OUTPUT = 8192
Status = Literal["available", "unknown", "error"]


class ProbeResult(TypedDict):
    status: Status
    data: dict[str, object]
    reason: NotRequired[str]


def _result(status: Status, *, reason: str | None = None, **data: object) -> ProbeResult:
    result: ProbeResult = {"status": status, "data": data}
    if reason is not None:
        result["reason"] = reason
    return result


def _probe_command(tool: str, *args: str) -> ProbeResult:
    executable = shutil.which(tool)
    if executable is None:
        return _result("unknown", reason=f"{tool} not found on PATH")
    try:
        process = subprocess.run(
            [executable, *args],
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=COMMAND_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _result(
            "error", reason=f"{tool} timed out after {COMMAND_TIMEOUT:g}s", executable=executable
        )
    except OSError as error:
        return _result("error", reason=f"{type(error).__name__}: {error}", executable=executable)
    return _result(
        "available" if process.returncode == 0 else "error",
        reason=None if process.returncode == 0 else f"{tool} exited with {process.returncode}",
        executable=executable,
        returncode=process.returncode,
        stdout=process.stdout[:MAX_OUTPUT],
        stderr=process.stderr[:MAX_OUTPUT],
        output_truncated=len(process.stdout) > MAX_OUTPUT or len(process.stderr) > MAX_OUTPUT,
    )


@dataclass(frozen=True)
class _Mount:
    root: PurePosixPath
    point: Path
    filesystem: str


def _mounts(proc_root: Path) -> list[_Mount]:
    mounts = []
    for line in (proc_root / "self/mountinfo").read_text(encoding="utf-8").splitlines():
        before, after = line.split(" - ", 1)
        fields, filesystem = before.split(), after.split()[0]
        root, point = (re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), f) for f in fields[3:5])
        mounts.append(_Mount(PurePosixPath(root), Path(point), filesystem))
    return mounts


def _cpu_quota(text: str) -> float | None:
    quota, period = text.split()
    if int(period) <= 0:
        raise ValueError("cpu.max period must be positive")
    if quota == "max":
        return None
    value = int(quota) / int(period)
    if value <= 0 or not math.isfinite(value):
        raise ValueError("cpu.max quota must be finite and positive")
    return value


def _probe_cgroup(proc_root: Path = Path("/proc")) -> ProbeResult:
    if sys.platform != "linux":
        return _result("unknown", reason="cgroup v2 probing is Linux-only")
    try:
        memberships = (proc_root / "self/cgroup").read_text(encoding="utf-8").splitlines()
        membership = next((line[3:] for line in memberships if line.startswith("0::")), None)
        if membership is None:
            return _result("unknown", reason="no unified cgroup v2 membership; v1 is not probed")
        member = PurePosixPath(membership)
        if not member.is_absolute() or ".." in member.parts:
            raise ValueError("invalid cgroup membership path")
        mount = next(
            (
                m
                for m in _mounts(proc_root)
                if m.filesystem == "cgroup2" and member.is_relative_to(m.root)
            ),
            None,
        )
        if mount is None:
            return _result("unknown", reason="no matching cgroup v2 mount in this namespace")
        leaf = mount.point / member.relative_to(mount.root)
        quotas: list[float] = []
        memory_limits: list[int] = []
        cpu_seen = memory_seen = False
        evidence: list[dict[str, str]] = []
        for directory in (leaf, *leaf.parents):
            entry = {"path": str(directory)}
            for filename in ("cpu.max", "memory.max"):
                path = directory / filename
                try:
                    text = path.read_text(encoding="utf-8").strip()
                except FileNotFoundError:
                    continue
                entry[filename] = text
                if filename == "cpu.max":
                    cpu_seen = True
                    quota = _cpu_quota(text)
                    if quota is not None:
                        quotas.append(quota)
                else:
                    memory_seen = True
                    if text != "max":
                        limit = int(text)
                        if limit < 0:
                            raise ValueError("memory.max must be nonnegative or max")
                        memory_limits.append(limit)
            evidence.append(entry)
            if directory == mount.point:
                break
        return _result(
            "available" if cpu_seen or memory_seen else "unknown",
            reason=None
            if cpu_seen and memory_seen
            else "one or more cgroup controllers are unavailable",
            version=2,
            path=str(leaf),
            cpu_status="available" if cpu_seen else "unknown",
            memory_status="available" if memory_seen else "unknown",
            cpu_quota=min(quotas) if quotas else None,
            memory_limit_bytes=min(memory_limits) if memory_limits else None,
            hierarchy=evidence,
        )
    except (OSError, ValueError, IndexError, OverflowError) as error:
        return _result("error", reason=f"{type(error).__name__}: {error}")


def _probe_cpu(
    cgroup: ProbeResult, *, logical_count: int | None = None, affinity_count: int | None = None
) -> ProbeResult:
    logical_count = os.cpu_count() if logical_count is None else logical_count
    try:
        if affinity_count is None and hasattr(os, "sched_getaffinity"):
            affinity_count = len(os.sched_getaffinity(0))
    except OSError as error:
        return _result("error", reason=f"CPU affinity: {error}", logical_count=logical_count)
    bounds = [float(n) for n in (logical_count, affinity_count) if n is not None]
    quota = cgroup["data"].get("cpu_quota")
    if isinstance(quota, (float, int)):
        bounds.append(quota)
    return _result(
        "available" if bounds else "unknown",
        reason=None if bounds else "CPU count and affinity are unavailable",
        logical_count=logical_count,
        affinity_count=affinity_count,
        effective_cpu_upper_bound=min(bounds) if bounds else None,
        cgroup_status=cgroup["data"].get("cpu_status", cgroup["status"]),
    )


def _probe_memory(cgroup: ProbeResult, proc_root: Path = Path("/proc")) -> ProbeResult:
    if sys.platform != "linux":
        return _result("unknown", reason="physical memory probing is Linux-only")
    try:
        lines = (proc_root / "meminfo").read_text(encoding="utf-8").splitlines()
        fields = next(line.split() for line in lines if line.startswith("MemTotal:"))
        if len(fields) != 3 or fields[2] != "kB" or int(fields[1]) <= 0:
            raise ValueError("invalid MemTotal")
        total = int(fields[1]) * 1024
        limit = cgroup["data"].get("memory_limit_bytes")
        return _result(
            "available",
            physical_total_bytes=total,
            effective_memory_upper_bound_bytes=min(total, limit)
            if isinstance(limit, int)
            else total,
            cgroup_status=cgroup["data"].get("memory_status", cgroup["status"]),
        )
    except (OSError, ValueError, StopIteration) as error:
        return _result("error", reason=f"{type(error).__name__}: {error}")


def _probe_disk(path: Path) -> ProbeResult:
    try:
        usage = shutil.disk_usage(path)
        return _result(
            "available",
            path=str(path.resolve()),
            total_bytes=usage.total,
            free_bytes=usage.free,
            persistence="unknown",
            persistence_reason="Cloud disk persistence requires provider/user confirmation.",
        )
    except OSError as error:
        return _result("error", reason=f"{type(error).__name__}: {error}")


def _probe_os_release() -> ProbeResult:
    if sys.platform != "linux":
        return _result("unknown", reason="freedesktop os-release is Linux-only")
    try:
        release = platform.freedesktop_os_release()
        return _result(
            "available",
            **{key: release[key] for key in ("ID", "VERSION_ID", "PRETTY_NAME") if key in release},
        )
    except OSError as error:
        return _result("error", reason=f"{type(error).__name__}: {error}")


def probe_host() -> dict[str, object]:
    """Collect evidence without installing tools, importing torch, or starting a game."""
    cgroup = _probe_cgroup()
    tools = {
        "gpu": _probe_command(
            "nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"
        ),
        "wine": _probe_command("wine", "--version"),
        "xvfb": _probe_command("Xvfb", "-help"),
        "cmake": _probe_command("cmake", "--version"),
    }
    tools["xvfb"]["data"]["version_status"] = "unknown"
    return {
        "probe_schema": 1,
        "host": _result(
            "available",
            system=platform.system(),
            machine=platform.machine(),
            kernel=platform.release(),
            os_release=_probe_os_release(),
        ),
        "cpu": _probe_cpu(cgroup),
        "memory": _probe_memory(cgroup),
        "cgroup": cgroup,
        "disk": _probe_disk(Path.cwd()),
        "tools": tools,
        "real_game_validated": False,
    }
