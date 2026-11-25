"""Fail-closed runtime evidence tests. These are not hardware qualifications."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "runtime", ROOT / "tools/check_mondrian_camera_runtime.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

GOOD = {
    "metadata.txt": "device=mondrian\nvendor_device=mondrian\nkernelrelease=5.10.81-oem\nsdk=37\nread_only=1\n",
    "modules.txt": "camera 1000 0 - Live 0x0\nwl2866d 120 1 camera Live 0x1\n",
    "video4linux.tsv": "v4l-subdev0\tcam_sensor0\n",
    "i2c_devices.tsv": "4-0028\txiaomi,wl2866d\n",
    "regulator_names.tsv": "regulator.0\tcamera-vin\n",
    "README.txt": "read-only evidence\n",
}


def make(root):
    for name, text in GOOD.items():
        (root / name).write_text(text)


class RuntimeEvidenceTests(unittest.TestCase):
    def test_snapshot_parses_but_does_not_claim_functional_camera(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            make(root)
            result = module.inspect(root)
            self.assertTrue(result["modules_observed_in_proc"]["camera"])
            self.assertTrue(result["kernel_5_10_81_detected"])
            self.assertIn("xiaomi,wl2866d", result["candidate_camera_i2c_names"])
            for key in ("hardware_probe_verified", "camera_hal_verified",
                        "ak7323_ois_verified", "power_cycle_verified",
                        "production_approved"):
                self.assertFalse(result[key])

    def test_rejects_wrong_device(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            make(root)
            (root / "metadata.txt").write_text(GOOD["metadata.txt"].replace(
                "mondrian", "diting"))
            with self.assertRaises(ValueError):
                module.inspect(root)

    def test_rejects_missing_and_symlinked_source(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            make(root)
            (root / "modules.txt").unlink()
            with self.assertRaises(ValueError):
                module.inspect(root)
            (root / "modules.txt").symlink_to(root / "metadata.txt")
            with self.assertRaisesRegex(ValueError, "unsafe"):
                module.inspect(root)

    def test_collector_never_writes_to_camera_hardware(self):
        script = (ROOT / "tools/collect_mondrian_camera_runtime.sh").read_text()
        self.assertIn("umask 077", script)
        self.assertIn("This diagnostic is only for mondrian", script)
        self.assertNotIn("insmod ", script)
        self.assertNotIn("modprobe ", script)
        self.assertNotIn("i2cset ", script)
        self.assertNotIn("setprop ", script)
        self.assertNotIn("dumpsys", script)
        self.assertNotIn("dmesg", script)


if __name__ == "__main__":
    unittest.main()
