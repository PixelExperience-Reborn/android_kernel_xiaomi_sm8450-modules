"""Regression tests for the real Camera <-> Xiaomi WL2866D ELF linkage."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "camera_wl2866d_abi", ROOT / "tools/verify_mondrian_camera_wl2866d_abi.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def good():
    cfg = {"CONFIG_WL2866D": "y", "CONFIG_LDO_WL2866D": "m"}
    camera = {symbol: {"U"} for symbol in module.POWER_SYMBOLS}
    provider = {symbol: {"T"} for symbol in module.POWER_SYMBOLS}
    manifest = {
        "camera_modules_included": True,
        "production_boot_load_order_qualified": False,
        "module_files": {"camera": "extra/camera.ko",
                         "wl2866d": "kernel/drivers/misc/wl2866d.ko"},
        "audited_oem_roots": ["goodix_fod", "wl2866d"],
        "modprobe_camera_insmod_order": [
            "insmod /stage/kernel/drivers/misc/wl2866d.ko",
            "insmod /stage/extra/camera.ko",
        ],
    }
    return cfg, camera, provider, "wl2866d,msm_mmrm", manifest


class OEMCameraWL2866DTests(unittest.TestCase):
    def test_matching_oem_power_abi(self):
        report = module.check_contract(*good())
        self.assertEqual(len(report["verified_power_symbols"]), 2)
        self.assertFalse(report["production_qualified"])

    def test_nm_posix_parse(self):
        self.assertIn("U", module.nm_symbols(
            "wl2866d_camera_power_up U\nother T 0 10\n"
        )["wl2866d_camera_power_up"])

    def test_missing_kernel_camera_feature_is_rejected(self):
        values = list(good())
        values[0]["CONFIG_WL2866D"] = "n"
        with self.assertRaisesRegex(ValueError, "call path"):
            module.check_contract(*values)

    def test_missing_undefined_camera_symbol_is_rejected(self):
        values = list(good())
        values[1].pop("wl2866d_camera_power_down")
        with self.assertRaisesRegex(ValueError, "does not import"):
            module.check_contract(*values)

    def test_missing_provider_symbol_is_rejected(self):
        values = list(good())
        values[2].pop("wl2866d_camera_power_up")
        with self.assertRaisesRegex(ValueError, "does not export"):
            module.check_contract(*values)

    def test_missing_modinfo_dependency_is_rejected(self):
        values = list(good())
        values[3] = "msm_mmrm"
        with self.assertRaisesRegex(ValueError, "modinfo"):
            module.check_contract(*values)

    def test_missing_provider_in_camera_modprobe_is_rejected(self):
        values = list(good())
        values[4]["modprobe_camera_insmod_order"].pop(0)
        with self.assertRaisesRegex(ValueError, "does not load"):
            module.check_contract(*values)

    def test_wrong_camera_modprobe_order_is_rejected(self):
        values = list(good())
        values[4]["modprobe_camera_insmod_order"].reverse()
        with self.assertRaisesRegex(ValueError, "before its WL2866D"):
            module.check_contract(*values)

    def test_wrong_regulator_source_path_is_rejected(self):
        values = list(good())
        values[4]["module_files"]["wl2866d"] = "extra/wl2866d.ko"
        with self.assertRaisesRegex(ValueError, "originate"):
            module.check_contract(*values)

    def test_no_release_claim_in_diagnostic_manifest(self):
        values = list(good())
        values[4]["production_boot_load_order_qualified"] = True
        with self.assertRaisesRegex(ValueError, "production readiness"):
            module.check_contract(*values)


if __name__ == "__main__":
    unittest.main()
