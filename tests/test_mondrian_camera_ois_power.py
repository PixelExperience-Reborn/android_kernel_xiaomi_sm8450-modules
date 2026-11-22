"""Regression checks for real factory Camera power and unqualified OIS."""
import copy
import importlib.util
import json
from pathlib import Path
import hashlib
from tempfile import TemporaryDirectory
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

    def test_fdt_reader_uses_aosp17_unsigned_cell_type(self):
        image = Path("/tmp/diagnostic.dtb")
        result = mod.subprocess.CompletedProcess(["fdtget"], 0, "1\n", "")
        with patch.object(mod.subprocess, "run", return_value=result) as run:
            self.assertEqual(
                mod.fdtget(image, "/soc/sensor2", "gpio-reset", "u"), "1")
            self.assertEqual(run.call_args.args[0], [
                "fdtget", "-t", "u", str(image), "/soc/sensor2", "gpio-reset"])
            self.assertEqual(run.call_args.kwargs["capture_output"], True)

    def test_fdt_reader_rejects_invalid_d_and_missing_property(self):
        with patch.object(mod.subprocess, "run") as run:
            with self.assertRaisesRegex(ValueError, "invalid or misplaced"):
                mod.fdtget(Path("/test.dtb"), "/sensor", "gpio-reset", "d")
            run.assert_not_called()
        failed = mod.subprocess.CompletedProcess(
            ["fdtget"], 1, "", "Error at 'gpio-reset': FDT_ERR_NOTFOUND\n")
        with patch.object(mod.subprocess, "run", return_value=failed):
            with self.assertRaisesRegex(ValueError, "FDT_ERR_NOTFOUND"):
                mod.fdtget(Path("/test.dtb"), "/sensor", "gpio-reset", "u")

    def test_three_compiled_boards_check_unsigned_reset_not_disabled_ois(self):
        hal, camera = fixtures()
        records = mod.verify_factory_profiles(hal, camera)
        calls = []
        with TemporaryDirectory() as tmp:
            images = Path(tmp) / "images"
            images.mkdir()
            for cape in mod.CAPE_BASES:
                image = images / (cape + "-mondrian-camera-board-diagnostic.dtb")
                image.write_bytes(b"synthetic FDT test fixture only:" + bytes(96))
                camera["per_board"][cape]["camera_board_merged_sha256"] = (
                    hashlib.sha256(image.read_bytes()).hexdigest())
            def fake_fdtget(image, node, property_name=None, fmt=None, *, tool="fdtget"):
                calls.append((image.name, node, property_name, fmt))
                if property_name == "gpio-reset":
                    self.assertEqual(fmt, "u")
                    self.assertTrue(node.endswith("sensor2"))
                    return "1"
                if property_name == "regulator-names":
                    self.assertEqual(fmt, "s")
                    index = int(node.rsplit("eeprom", 1)[1])
                    return " ".join(records[index]["expected_eeprom_fdt_regulator_names"])
                if "eeprom" in node:
                    return "regulator-names\ncell-index\n"
                return ("cell-index\neeprom-src\ncsiphy-sd-index\n"
                        + ("actuator-src\n" if node.endswith("sensor0") else "")
                        + ("gpio-reset\n" if node.endswith("sensor2") else ""))
            with patch.object(mod, "fdtget", side_effect=fake_fdtget):
                actual = mod.inspect_compiled_boards(camera, Path(tmp), records)
        self.assertEqual(set(actual), set(mod.CAPE_BASES))
        resets = [row for row in calls if row[2] == "gpio-reset"]
        self.assertEqual(len(resets), 3)
        self.assertTrue(all(row[3] == "u" for row in resets))


if __name__ == "__main__":
    unittest.main()
