"""Fail-closed tests for Xiaomi Camera auxiliary I2C / PM8350C selection."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "pmic_gate", ROOT / "tools/select_mondrian_pmic_flash.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class MondrianPmicFlashTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(
            (ROOT / "mondrian-camera-flash-policy.json").read_text())

    def test_manifest_does_not_claim_hardware_or_donor_flash(self):
        gate.verify_policy(self.policy)
        self.assertFalse(
            self.policy["flash_selection"]["production_camera_flash_allowed"])
        self.assertFalse(self.policy["flash_selection"][
            "manufacturer_yudi_i2c_sysfs_gpio356_enabled"])

    def test_rejects_unsafe_board_config_or_wrong_source(self):
        changes = [
            ("flash_selection", "production_camera_flash_allowed", True),
            ("flash_selection", "mutter_flash_mask_hardware_qualified", True),
            ("flash_selection",
             "manufacturer_yudi_i2c_sysfs_gpio356_enabled", True),
            ("manufacturer_camera", "commit", "0" * 40),
            ("xiaomi_device_tree", "commit", "0" * 40),
        ]
        for group, field, value in changes:
            with self.subTest(group=group, field=field):
                policy = copy.deepcopy(self.policy)
                policy[group][field] = value
                with self.assertRaises(ValueError):
                    gate.verify_policy(policy)

    def test_single_macro_guard_and_no_other_code_changes(self):
        original = (gate.NEARBY + b"\n" + gate.DEFINITION +
                    b"/* other OEM I2C and PMIC logic remains */\n")
        updated = gate.select_mondrian_flash(original)
        self.assertEqual(updated, original.replace(
            gate.DEFINITION, gate.REPLACEMENT))
        self.assertNotIn(gate.DEFINITION, updated)
        self.assertIn(b"#error", updated)
        self.assertIn(b"other OEM I2C and PMIC logic", updated)

    def test_missing_double_and_changed_header_rejected(self):
        original = gate.NEARBY + b"\n" + gate.DEFINITION
        for candidate in (original + gate.DEFINITION,
                          original.replace(gate.DEFINITION, b""),
                          original.replace(gate.NEARBY, b""),
                          original.replace(gate.DEFINITION, gate.REPLACEMENT)):
            with self.subTest(candidate=candidate[-90:]):
                with self.assertRaises(ValueError):
                    gate.select_mondrian_flash(candidate)

    def test_original_xiaomi_blob_lock_and_no_other_rom(self):
        self.assertEqual(gate.HEADER_BLOB,
                         "592f7380c157e386ea724b20078f76d2edbac94d")
        self.assertEqual(gate.OEM_COMMON_BLOB,
                         "e4e321d4d54353f0243b0283647528180baa3137")
        self.assertEqual(gate.HEADER.as_posix(),
                         "drivers/cam_sensor_module/cam_flash/cam_flash_dev.h")
        self.assertEqual(len(gate.CAMERA_SHA), 40)


if __name__ == "__main__":
    unittest.main()
