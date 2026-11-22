"""Regression checks for real factory Camera power and unqualified OIS."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "cam_power", ROOT / "tools/verify_mondrian_camera_ois_power.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fixtures():
    h = json.loads((ROOT / "tests/fixtures/mondrian-camera-hal-profiles.json").read_text())
    c = {"device": "mondrian", "factory_camera_hal_profiles": copy.deepcopy(h),
         "board_rear_flash_switch0_mask": 1,
         "production_camera_dtbo_approved": False,
         "per_board": {n: {"camera_slots": {
             r: {"factory_camera_id": i, "ois_src_present": False,
                 "sensor_node": "/soc/sensor" + str(i),
                 "eeprom_node": "/soc/eeprom" + str(i)}
             for i, (r, *_rest) in enumerate(mod.EXPECTED)}}
                       for n in mod.CAPE_BASES}}
    return h, c


class CameraOisPowerTests(unittest.TestCase):
    def test_verified_factory_record_set(self):
        h, c = fixtures()
        out = mod.verify_factory_profiles(h, c)
        self.assertEqual(len(out), 4)
        self.assertEqual([x["factory_eeprom_power_rail"] for x in out],
                         ["WL2866D_AVDD1"] * 3 + ["VIO"])
        self.assertFalse(h["slots"][0]["ois_control"]["standalone_subdevice_in_stock_dt"])

    def test_ois_must_not_be_assumed_active(self):
        h, c = fixtures()
        for edit in (
            lambda h: h["slots"][0]["ois_control"].update({"transport": "CCI"}),
            lambda h: h["slots"][0]["ois_control"].update({"nonzero_register_data_records_per_profile": 13}),
            lambda h: h["slots"][0].update({"ois": "AK7323-enabled"}),
            lambda h: h["slots"][1].update({"ois": "AK7323"}),
        ):
            with self.subTest(edit=edit):
                a, b = copy.deepcopy(h), copy.deepcopy(c)
                edit(a)
                b["factory_camera_hal_profiles"] = copy.deepcopy(a)
                with self.assertRaises(ValueError):
                    mod.verify_factory_profiles(a, b)

    def test_wrong_factory_power_records_block(self):
        h, c = fixtures()
        for slot in range(4):
            with self.subTest(slot=slot):
                a, b = copy.deepcopy(h), copy.deepcopy(c)
                a["slots"][slot]["eeprom_power"]["enable_delay_ms"] = 0
                b["factory_camera_hal_profiles"] = copy.deepcopy(a)
                with self.assertRaisesRegex(ValueError, "EEPROM power"):
                    mod.verify_factory_profiles(a, b)

    def test_wrong_manifest_and_board_mask_block(self):
        h, c = fixtures()
        c["board_rear_flash_switch0_mask"] = 9
        with self.assertRaisesRegex(ValueError, "PM8350C"):
            mod.verify_factory_profiles(h, c)
        c["board_rear_flash_switch0_mask"] = 1
        c["production_camera_dtbo_approved"] = True
        with self.assertRaisesRegex(ValueError, "wrongly approved"):
            mod.verify_factory_profiles(h, c)

    def test_missing_source_evidence_and_all_boards_required(self):
        h, c = fixtures()
        c["per_board"].pop("capep")
        with self.assertRaisesRegex(ValueError, "compiled Cape"):
            mod.verify_factory_profiles(h, c)
        c["per_board"]["capep"] = c["per_board"]["cape"]
        c["factory_camera_hal_profiles"]["slots"][2]["sensor"] = "incorrect"
        with self.assertRaisesRegex(ValueError, "not tied"):
            mod.verify_factory_profiles(h, c)

    def test_fdt_reader_cannot_ignore_failed_compiled_probe(self):
        with patch.object(mod.subprocess, "check_output",
                          side_effect=subprocess_error()):
            with self.assertRaises(mod.subprocess.CalledProcessError):
                mod.fdtget(Path("/bad.dtb"), "/soc/sensor0", "cell-index", "d")


def subprocess_error():
    return mod.subprocess.CalledProcessError(1, ["fdtget"])


if __name__ == "__main__":
    unittest.main()
