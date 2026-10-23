"""Read-only diagnostics; presence of files is not proof of compatibility."""

import os
from pathlib import Path
import platform
import shutil
import struct
import sys


def windows_machine_codes():
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes
    try:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        query = kernel.IsWow64Process2
        query.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.USHORT), ctypes.POINTER(wintypes.USHORT))
        query.restype = wintypes.BOOL
        process, native = wintypes.USHORT(), wintypes.USHORT()
        if query(kernel.GetCurrentProcess(), ctypes.byref(process), ctypes.byref(native)):
            return process.value, native.value
    except (AttributeError, OSError):
        pass
    return None


def detect_architecture(machine=None, environment=None):
    machine = platform.machine() if machine is None else machine
    environment = os.environ if environment is None else environment
    aliases = {"amd64": "x64", "x86_64": "x64", "aarch64": "arm64", "arm64": "arm64",
               "x86": "x86", "i386": "x86", "i686": "x86"}
    process = aliases.get(machine.lower(), machine.lower())
    native = environment.get("PROCESSOR_ARCHITEW6432") or environment.get("PROCESSOR_ARCHITECTURE") or machine
    return dict(os_architecture=aliases.get(native.lower(), native.lower()),
                process_architecture=process)


def diagnose(starcraft_dir=None):
    root = Path(starcraft_dir) if starcraft_dir else None
    required = ("StarCraft.exe", "StarDat.mpq", "BrooDat.mpq", "Patch_rt.mpq")
    present = {name: bool(root and (root / name).is_file()) for name in required}
    architecture = detect_architecture()
    machine_codes = windows_machine_codes()
    if machine_codes is not None:
        process, native = machine_codes
        names = {0x014C: "x86", 0x8664: "x64", 0xAA64: "arm64"}
        architecture["os_architecture"] = names.get(native, f"unknown-{native:x}")
        # Prism can return UNKNOWN for an x64 image. The runtime/PE architecture
        # remains x64 even when Windows does not classify it as a WoW process.
        if process:
            architecture["process_architecture"] = names.get(process, f"unknown-{process:x}")
    return dict(**architecture, os_version=platform.version(), python=sys.version.split()[0],
                python_executable=sys.executable, python_pointer_bits=struct.calcsize("P") * 8,
                cpu_count=os.cpu_count(), cmake=shutil.which("cmake"),
                starcraft_dir=str(root) if root else None, files=present,
                game_files_present=all(present.values()),
                bwapi_config_present=bool(root and (root / "bwapi-data/bwapi.ini").is_file()),
                real_game_validated=False, pluto_compatibility="unverified",
                recommendation=("ARM development supported; test Prism/BWAPI/Pluto locally or use an x64 game worker."
                                if architecture["os_architecture"] == "arm64" else
                                "Validate StarCraft 1.16.1 + BWAPI 4.4.0 before training."))
