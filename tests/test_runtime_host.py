import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from starforge.doctor import diagnose
from starforge.runtime.host import (
    COMMAND_TIMEOUT,
    MAX_OUTPUT,
    _probe_cgroup,
    _probe_command,
    _probe_cpu,
    _probe_disk,
    _probe_memory,
    probe_host,
)


class CommandProbeTests(unittest.TestCase):
    def test_missing_tool_is_unknown_not_validated(self):
        with (
            patch("starforge.runtime.host.shutil.which", return_value=None),
            patch("starforge.runtime.host.subprocess.run") as run,
        ):
            result = _probe_command("wine", "--version")
        self.assertEqual(result["status"], "unknown")
        self.assertIn("not found", result["reason"])
        run.assert_not_called()

    def test_timeout_is_bounded_and_explicit(self):
        with (
            patch("starforge.runtime.host.shutil.which", return_value="/tools/wine"),
            patch(
                "starforge.runtime.host.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["wine"], COMMAND_TIMEOUT),
            ) as run,
        ):
            result = _probe_command("wine", "--version")
        self.assertEqual(result["status"], "error")
        self.assertIn("timed out", result["reason"])
        self.assertEqual(run.call_args.kwargs["timeout"], COMMAND_TIMEOUT)
        self.assertFalse(run.call_args.kwargs["shell"])
        self.assertEqual(run.call_args.args[0], ["/tools/wine", "--version"])

    def test_failed_process_preserves_exit_code_and_stderr(self):
        process = subprocess.CompletedProcess(["wine"], 7, "", "runtime missing")
        with (
            patch("starforge.runtime.host.shutil.which", return_value="/tools/wine"),
            patch("starforge.runtime.host.subprocess.run", return_value=process),
        ):
            result = _probe_command("wine", "--version")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["data"]["returncode"], 7)
        self.assertEqual(result["data"]["stderr"], "runtime missing")

    def test_os_error_does_not_escape_diagnostics(self):
        with (
            patch("starforge.runtime.host.shutil.which", return_value="/tools/wine"),
            patch("starforge.runtime.host.subprocess.run", side_effect=PermissionError("denied")),
        ):
            result = _probe_command("wine", "--version")
        self.assertEqual(result["status"], "error")
        self.assertIn("denied", result["reason"])

    def test_successful_output_is_bounded_and_truncation_is_reported(self):
        process = subprocess.CompletedProcess(["wine"], 0, "x" * (MAX_OUTPUT + 10), "")
        with (
            patch("starforge.runtime.host.shutil.which", return_value="/tools/wine"),
            patch("starforge.runtime.host.subprocess.run", return_value=process),
        ):
            result = _probe_command("wine", "--version")
        self.assertEqual(result["status"], "available")
        self.assertEqual(len(result["data"]["stdout"]), MAX_OUTPUT)
        self.assertTrue(result["data"]["output_truncated"])


class CgroupProbeTests(unittest.TestCase):
    def setUp(self):
        linux = patch("starforge.runtime.host.sys.platform", "linux")
        linux.start()
        self.addCleanup(linux.stop)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.proc = self.root / "proc"
        (self.proc / "self").mkdir(parents=True)
        self.mount = self.root / "cgroup"
        self.leaf = self.mount / "user.slice" / "session.scope"
        self.leaf.mkdir(parents=True)
        (self.proc / "self/cgroup").write_text("0::/user.slice/session.scope\n")
        (self.proc / "self/mountinfo").write_text(
            f"29 23 0:26 / {self.mount} rw - cgroup2 cgroup rw\n"
        )

    def limits(self, path, cpu="max 100000", memory="max"):
        (path / "cpu.max").write_text(cpu)
        (path / "memory.max").write_text(memory)

    def test_ancestor_limits_override_larger_leaf_limits(self):
        self.limits(self.mount, cpu="max 100000")
        self.limits(self.leaf.parent, cpu="150000 100000", memory=str(2**30))
        self.limits(self.leaf, cpu="200000 100000", memory=str(4 * 2**30))
        result = _probe_cgroup(self.proc)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["data"]["cpu_quota"], 1.5)
        self.assertEqual(result["data"]["memory_limit_bytes"], 2**30)
        cpu = _probe_cpu(result, logical_count=40, affinity_count=8)
        self.assertEqual(cpu["data"]["effective_cpu_upper_bound"], 1.5)

    def test_affinity_can_be_stricter_than_quota(self):
        self.limits(self.leaf, cpu="400000 100000")
        cpu = _probe_cpu(_probe_cgroup(self.proc), logical_count=40, affinity_count=2)
        self.assertEqual(cpu["data"]["effective_cpu_upper_bound"], 2)

    def test_unlimited_controllers_are_explicit(self):
        self.limits(self.leaf)
        result = _probe_cgroup(self.proc)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["data"]["cpu_status"], "available")
        self.assertEqual(result["data"]["memory_status"], "available")
        self.assertIsNone(result["data"]["cpu_quota"])
        self.assertIsNone(result["data"]["memory_limit_bytes"])

    def test_absent_controllers_are_not_assumed_unlimited(self):
        result = _probe_cgroup(self.proc)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["data"]["cpu_status"], "unknown")
        self.assertEqual(result["data"]["memory_status"], "unknown")

    def test_partial_controller_support_remains_visible(self):
        (self.leaf / "cpu.max").write_text("100000 100000")
        result = _probe_cgroup(self.proc)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["data"]["memory_status"], "unknown")

    def test_v1_is_unknown_rather_than_unlimited(self):
        (self.proc / "self/cgroup").write_text("2:cpu:/legacy\n")
        result = _probe_cgroup(self.proc)
        self.assertEqual(result["status"], "unknown")
        self.assertIn("v2", result["reason"])

    def test_mount_root_is_respected(self):
        (self.proc / "self/cgroup").write_text("0::/host/user.slice/session.scope\n")
        (self.proc / "self/mountinfo").write_text(
            f"29 23 0:26 /host {self.mount} rw - cgroup2 cgroup rw\n"
        )
        self.limits(self.leaf, cpu="50000 100000")
        result = _probe_cgroup(self.proc)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["data"]["cpu_quota"], 0.5)

    def test_mountinfo_escaped_spaces_are_decoded(self):
        self.mount = self.root / "cgroup space"
        self.leaf = self.mount / "user.slice" / "session.scope"
        self.leaf.mkdir(parents=True)
        escaped = str(self.mount).replace(" ", r"\040")
        (self.proc / "self/mountinfo").write_text(
            f"29 23 0:26 / {escaped} rw - cgroup2 cgroup rw\n"
        )
        self.limits(self.leaf, cpu="50000 100000")
        result = _probe_cgroup(self.proc)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["data"]["path"], str(self.leaf))

    def test_malformed_limits_are_errors(self):
        for cpu, memory in [
            ("bad", "max"),
            ("1 0", "max"),
            ("-1 100000", "max"),
            ("max 100000", "-1"),
            ("max 100000", "bad"),
        ]:
            with self.subTest(cpu=cpu, memory=memory):
                self.limits(self.leaf, cpu=cpu, memory=memory)
                self.assertEqual(_probe_cgroup(self.proc)["status"], "error")

    def test_traversal_cannot_escape_cgroup_mount(self):
        (self.proc / "self/cgroup").write_text("0::/../../outside\n")
        self.assertEqual(_probe_cgroup(self.proc)["status"], "error")

    def test_unreadable_proc_metadata_is_an_error(self):
        with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
            result = _probe_cgroup(self.proc)
        self.assertEqual(result["status"], "error")
        self.assertIn("denied", result["reason"])

    def test_memory_ceiling_respects_cgroup_not_just_host_ram(self):
        self.limits(self.leaf, memory=str(2**30))
        (self.proc / "meminfo").write_text("MemTotal:       329252864 kB\n")
        result = _probe_memory(_probe_cgroup(self.proc), self.proc)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["data"]["physical_total_bytes"], 329252864 * 1024)
        self.assertEqual(result["data"]["effective_memory_upper_bound_bytes"], 2**30)


class HostProbeTests(unittest.TestCase):
    def test_disk_capacity_does_not_claim_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            result = _probe_disk(Path(directory))
        self.assertEqual(result["status"], "available")
        self.assertGreater(result["data"]["free_bytes"], 0)
        self.assertEqual(result["data"]["persistence"], "unknown")

    def test_non_linux_cgroups_are_unknown(self):
        with patch("starforge.runtime.host.sys.platform", "win32"):
            result = _probe_cgroup()
        self.assertEqual(result["status"], "unknown")

    def test_runtime_is_json_safe_without_external_tools_or_torch(self):
        with patch("starforge.runtime.host.shutil.which", return_value=None):
            runtime = probe_host()
        json.dumps(runtime, allow_nan=False)
        for key in ("host", "cpu", "memory", "cgroup", "disk", "tools"):
            self.assertIn(key, runtime)
        self.assertEqual(runtime["tools"]["gpu"]["status"], "unknown")
        self.assertEqual(runtime["tools"]["wine"]["status"], "unknown")
        self.assertEqual(runtime["tools"]["xvfb"]["status"], "unknown")
        self.assertFalse(runtime["real_game_validated"])

    def test_doctor_preserves_existing_fields_and_adds_runtime(self):
        runtime = {"example": "fixture"}
        with patch("starforge.doctor.probe_host", return_value=runtime):
            result = diagnose()
        self.assertEqual(result["runtime"], runtime)
        for field in ("os_architecture", "python", "cpu_count", "game_files_present"):
            self.assertIn(field, result)
        self.assertFalse(result["real_game_validated"])

    def test_failed_tools_do_not_crash_doctor_or_claim_success(self):
        process = subprocess.CompletedProcess(["tool"], 7, "", "fixture failure")
        with (
            patch("starforge.runtime.host.shutil.which", return_value="/tools/fixture"),
            patch("starforge.runtime.host.subprocess.run", return_value=process),
        ):
            result = diagnose()
        self.assertEqual(result["runtime"]["tools"]["gpu"]["status"], "error")
        self.assertEqual(result["runtime"]["tools"]["wine"]["status"], "error")
        self.assertFalse(result["real_game_validated"])


if __name__ == "__main__":
    unittest.main()
