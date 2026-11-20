"""Fail-closed source pins for the three-repository mondrian OEM BSP build."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = "ef722b7b3773dacc805a65fd42d022206001266a"
DEVICE_TREES = "24a99f33ea5324f3ac33e54d17dfe9a0009ef04a"


class ThreeRepositorySourceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads((ROOT / "mondrian-camera-flash-policy.json").read_text())
        cls.coherent = (ROOT / ".github/workflows/oem-coherent-wlan-compile.yml").read_text()
        cls.standalone = (ROOT / ".github/workflows/xiaomi-camera-compile-abi.yml").read_text()
        cls.selector = (ROOT / "tools/select_mondrian_pmic_flash.py").read_text()

    def test_all_camera_and_audio_builds_pin_same_original_device_tree(self):
        self.assertEqual(self.policy["xiaomi_device_tree"]["commit"], DEVICE_TREES)
        self.assertEqual(self.policy["selected_kernel_commit"], KERNEL)
        self.assertIn('DTS_SHA = "' + DEVICE_TREES + '"', self.selector)
        self.assertIn('assert camera["mondrian_m11a_csiphy2_and_4_bound"] is True',
                      self.coherent)
        self.assertIn('camera_m11a_csiphy2_and_4_compiled', self.coherent)
        for workflow in (self.coherent, self.standalone):
            self.assertIn("repository: PixelExperience-Reborn/android_kernel_xiaomi_sm8450-devicetrees\n"
                          "          ref: " + DEVICE_TREES, workflow)

    def test_full_oem_build_actually_checks_all_three_repositories(self):
        self.assertIn("submodules: recursive", self.coherent)
        for tool in ("device-tree/tools/build_oem_dtbo.py",
                     "device-tree/tools/build_mondrian_camera_platform.py",
                     "tools/verify_mondrian_camera_wl2866d_abi.py"):
            self.assertIn(tool, self.coherent)
        for condition in ('"production_audio_approved"', '"mondrian_audio_hal_qualified"',
                          '"production_camera_dtbo_approved"',
                          '"goodix_udfps_oem_bindings_verified"'):
            self.assertIn(condition, self.coherent)

    def test_never_promote_diagnostic_build_to_shipping_image(self):
        self.assertIn('"production_boot_dtbo_and_modules_load_approved": False',
                      self.coherent)
        self.assertIn('"audio_hal_and_hardware_verified": False', self.coherent)
        self.assertIn('"camera_sensor_routing_verified": False', self.coherent)
        self.assertIn('"m11a_lhbm_hardware_verified": False', self.coherent)
        self.assertFalse(self.policy["flash_selection"]["production_camera_flash_allowed"])

    def test_dtcoherent_shell_has_no_doubled_backslash_continuations(self):
        block = self.coherent.split("      - name: Integrate exact OEM Kernel,", 1)[1]
        block = block.split("      - name: Check reusable diagnostic Image", 1)[0]
        self.assertNotIn("\\\\\n", block)


if __name__ == "__main__":
    unittest.main()
