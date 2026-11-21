"""Fail-closed checks for OEM-only and coherent OEM+Display ABI evidence."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "verify_module_abi", ROOT / "tools/verify_external_module_abi.py"
)
abi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(abi)

OEM = "2466406b9beac724960b0c88e6e794421d0466e7"
MERGED = "a86d3dc9f8eb17af032c61dea412c0ec2d312627"


class ExactKernelCommitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.kernel = self.root / "kernel"
        self.out = self.root / "out"
        self.module = self.root / "msm_drm.ko"
        self.report = self.root / "abi.json"
        self.kernel.mkdir()
        self.out.mkdir()
        for p in (self.out / "vmlinux", self.out / "Module.symvers",
                  self.out / ".config", self.module):
            p.write_bytes(b"fixture")

    def run_gate(self, actual=OEM, expected=None, vermagic="5.10.81-fixture SMP aarch64"):
        argv = ["verify_external_module_abi.py",
                "--kernel", str(self.kernel), "--kernel-out", str(self.out),
                "--module", str(self.module), "--out", str(self.report)]
        if expected is not None:
            argv += ["--expected-kernel-commit", expected]

        def fake_cmd(cmd):
            if cmd[:2] == ["git", "-C"]:
                return actual
            if cmd[0] == "make":
                return "5.10.81-fixture"
            if cmd[:3] == ["modinfo", "-F", "vermagic"]:
                return vermagic
            if cmd[0] == "readelf":
                return "Machine: AArch64"
            if cmd[:3] == ["modinfo", "-F", "license"]:
                return "GPL v2"
            if cmd[:3] == ["modinfo", "-F", "depends"]:
                return "msm-mmrm"
            raise AssertionError("Unexpected command: " + repr(cmd))

        with patch.object(sys, "argv", argv), patch.object(
                abi, "command", side_effect=fake_cmd):
            abi.main()

    def test_legacy_oem_pin_remains_default(self):
        self.run_gate()
        report = json.loads(self.report.read_text())
        self.assertEqual(report["kernel_commit"], OEM)
        self.assertEqual(report["depends"], ["msm-mmrm"])
        self.assertFalse(report["hardware_booted"])

    def test_unpinned_different_kernel_is_rejected(self):
        with self.assertRaisesRegex(SystemExit, "2"):
            self.run_gate(actual=MERGED)
        self.assertFalse(self.report.exists())

    def test_merged_kernel_requires_exact_explicit_pin(self):
        self.run_gate(actual=MERGED, expected=MERGED)
        self.assertEqual(json.loads(self.report.read_text())["kernel_commit"], MERGED)

    def test_explicit_wrong_kernel_is_rejected(self):
        with self.assertRaises(SystemExit) as result:
            self.run_gate(actual=MERGED, expected=OEM)
        self.assertEqual(result.exception.code, 2)
        self.assertFalse(self.report.exists())

    def test_malformed_kernel_sha_rejected(self):
        for invalid in ("", "HEAD", "a" * 39, "G" * 40):
            with self.subTest(invalid=invalid):
                with self.assertRaises(SystemExit) as result:
                    self.run_gate(actual=MERGED, expected=invalid)
                self.assertEqual(result.exception.code, 2)
                self.assertFalse(self.report.exists())

    def test_matching_commit_does_not_bypass_vermagic(self):
        with self.assertRaises(SystemExit) as result:
            self.run_gate(actual=MERGED, expected=MERGED, vermagic="5.10.82-wrong SMP aarch64")
        self.assertEqual(result.exception.code, 2)
        self.assertFalse(self.report.exists())


if __name__ == "__main__":
    unittest.main()
