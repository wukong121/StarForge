import json
import hashlib
import os
from pathlib import Path
import subprocess
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

from starforge.doctor import detect_architecture, diagnose
from starforge.agent import QLearner
from dataclasses import asdict
from test_core import obs


class CLITests(unittest.TestCase):
    def test_native_windows_api_overrides_emulated_environment(self):
        with patch("starforge.doctor.windows_machine_codes", return_value=(0x8664, 0xAA64), create=True):
            result = diagnose()
        self.assertEqual(result["os_architecture"], "arm64")
        self.assertEqual(result["process_architecture"], "x64")

    def test_prism_unknown_process_code_keeps_runtime_architecture(self):
        with patch("starforge.doctor.windows_machine_codes", return_value=(0, 0xAA64), create=True), \
                patch("starforge.doctor.platform.machine", return_value="AMD64"):
            result = diagnose()
        self.assertEqual(result["os_architecture"], "arm64")
        self.assertEqual(result["process_architecture"], "x64")

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "starforge", *args],
                              text=True, capture_output=True, timeout=30)

    def test_emulation_does_not_hide_arm_host(self):
        result = detect_architecture("AMD64", {"PROCESSOR_ARCHITEW6432": "ARM64"})
        self.assertEqual(result["os_architecture"], "arm64")
        self.assertEqual(result["process_architecture"], "x64")

    def test_doctor_is_read_only_and_does_not_claim_game_readiness(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_cli("doctor", "--starcraft-dir", folder)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data["game_files_present"])
        self.assertFalse(data["real_game_validated"])

    def test_smoke_creates_reloadable_model_and_separated_report(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_cli("smoke", "--episodes", "100", "--eval-episodes", "10", "--out", folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((Path(folder) / "report.json").read_text())
            self.assertEqual(len(report), 2)
            self.assertTrue(all(row["backend"] == "synthetic" for row in report))
            self.assertTrue((Path(folder) / "checkpoint.json").is_file())
            second = self.run_cli("smoke", "--episodes", "1", "--out", folder)
            self.assertNotEqual(second.returncode, 0)
            summary = self.run_cli("report", str(Path(folder) / "matches.jsonl"))
            self.assertEqual(summary.returncode, 0, summary.stderr)
            self.assertEqual(json.loads(summary.stdout), report)

    def test_invalid_cli_inputs_and_missing_eval_checkpoint_fail(self):
        for args in [("smoke", "--episodes", "0"),
                     ("serve", "--timeout", "nan"),
                     ("serve", "--checkpoint", "does-not-exist.json", "--mode", "eval")]:
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Traceback", result.stderr)

    def test_real_tcp_cli_saves_training_but_never_eval_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            checkpoint = Path(folder) / "q.json"
            log = Path(folder) / "games.jsonl"
            previous_bytes = None
            for mode in ("train", "eval"):
                with socket.socket() as reservation:
                    reservation.bind(("127.0.0.1", 0))
                    port = reservation.getsockname()[1]
                command = [sys.executable, "-m", "starforge", "serve", "--mode", mode,
                           "--port", str(port), "--timeout", "3", "--checkpoint", str(checkpoint),
                           "--log", str(log), "--opponent", "protocol-fixture", "--opponent-version", "1"]
                with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
                    try:
                        self.assertIn("Listening", process.stderr.readline())
                        with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
                            with client.makefile("rwb") as stream:
                                for observation in (obs(backend="broodwar"), obs(backend="broodwar", seq=1,
                                        frame=24, terminal=True, outcome="win", legal_actions=[])):
                                    stream.write((json.dumps(asdict(observation)) + "\n").encode())
                                    stream.flush()
                                    self.assertTrue(stream.readline().startswith(b"ACT "))
                        stdout, stderr = process.communicate(timeout=5)
                        self.assertEqual(process.returncode, 0, stderr)
                        self.assertEqual(json.loads(stdout)[0]["wins"], 1)
                    finally:
                        if process.poll() is None:
                            process.kill()
                            process.communicate()
                if previous_bytes is not None:
                    self.assertEqual(checkpoint.read_bytes(), previous_bytes)
                previous_bytes = checkpoint.read_bytes()
            records = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual([r["mode"] for r in records], ["train", "eval"])

    def test_eval_provenance_stays_with_loaded_model_when_file_is_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            checkpoint = Path(folder) / "q.json"
            log = Path(folder) / "games.jsonl"
            QLearner(backend="broodwar", seed=1).save(checkpoint)
            original_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            command = [sys.executable, "-m", "starforge", "serve", "--mode", "eval", "--episodes", "2",
                       "--port", str(port), "--timeout", "3", "--checkpoint", str(checkpoint), "--log", str(log)]
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
                try:
                    self.assertIn("Listening", process.stderr.readline())
                    # The model is already loaded. Replace the pathname before either game begins.
                    QLearner(backend="broodwar", seed=999).save(checkpoint)
                    for _ in range(2):
                        with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
                            with client.makefile("rwb") as stream:
                                for observation in (obs(backend="broodwar"), obs(backend="broodwar", seq=1,
                                        frame=24, terminal=True, outcome="win", legal_actions=[])):
                                    stream.write((json.dumps(asdict(observation)) + "\n").encode())
                                    stream.flush()
                                    self.assertTrue(stream.readline().startswith(b"ACT "))
                    stdout, stderr = process.communicate(timeout=5)
                    self.assertEqual(process.returncode, 0, stderr)
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.communicate()
            records = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual([r["checkpoint"] for r in records], [original_hash, original_hash])


if __name__ == "__main__":
    unittest.main()
