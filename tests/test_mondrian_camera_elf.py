"""Reject a false PMIC ABI contract and donor-specific flash in Camera ELF."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "camera_elf", ROOT / "tools/verify_mondrian_camera_elf.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class MondrianCameraElfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.correct_nm = "\n".join(
            f"{name} T 100 10" for name in
            sorted(gate.PMIC_FUNCTIONS | gate.GENERIC_I2C_FUNCTIONS)
        ) + "\ncam_flash_i2c_driver D 200 40\n" + (
            "cam_flash_i2c_driver_probe t 240 20\n"
        )

    def test_real_oem_qualcomm_symbol_contract(self):
        symbols = gate.parse_nm_posix(self.correct_nm)
        result = gate.check_camera_elf(symbols)
        self.assertTrue(result["pmic_functions"])
        self.assertTrue(result["generic_i2c_functions"])
        self.assertFalse(
            result["unqualified_yudi_sysfs_gpio356_symbols_present"])

    def test_never_demand_nonexistent_pmic_power_ops(self):
        self.assertNotIn("cam_flash_pmic_power_ops", gate.PMIC_FUNCTIONS)
        gate.check_camera_elf(gate.parse_nm_posix(self.correct_nm))

    def test_missing_any_real_pmic_function_blocks(self):
        for name in gate.PMIC_FUNCTIONS:
            with self.subTest(name=name):
                nm = "\n".join(
                    line for line in self.correct_nm.splitlines()
                    if not line.startswith(name + " "))
                with self.assertRaisesRegex(ValueError, "missing PMIC"):
                    gate.check_camera_elf(gate.parse_nm_posix(nm))

    def test_missing_generic_i2c_blocks_without_disabling_driver(self):
        for name in sorted(
                gate.GENERIC_I2C_FUNCTIONS | gate.GENERIC_I2C_DRIVER.keys()):
            with self.subTest(name=name):
                nm = "\n".join(
                    line for line in self.correct_nm.splitlines()
                    if not line.startswith(name + " "))
                with self.assertRaisesRegex(ValueError, "missing generic I2C"):
                    gate.check_camera_elf(gate.parse_nm_posix(nm))

    def test_any_yudi_gpio_sysfs_symbol_blocks(self):
        for name in gate.UNQUALIFIED_YUDI_SYMBOLS:
            with self.subTest(name=name):
                bad = self.correct_nm + name + " b 800 04\n"
                with self.assertRaisesRegex(ValueError, "unqualified yudi"):
                    gate.check_camera_elf(gate.parse_nm_posix(bad))

    def test_only_real_text_or_data_definitions_qualify(self):
        for replacement in (" U ", " N ", " ? "):
            with self.subTest(replacement=replacement):
                bad = self.correct_nm.replace(
                    "cam_flash_led_prepare T ", 
                    "cam_flash_led_prepare" + replacement)
                with self.assertRaisesRegex(ValueError, "missing PMIC"):
                    gate.check_camera_elf(gate.parse_nm_posix(bad))

    def test_camera_kernelrelease_matches_compiled_kbuild_not_hardcoded_git(self):
        gate.check_camera_vermagic(
            "5.10.81-gki-gc9c67329b427 SMP preempt mod_unload aarch64",
            "5.10.81-gki-gc9c67329b427")
        for actual, release in (
            ("5.10.81-gki-g032260f7c8da SMP aarch64",
             "5.10.81-gki-gc9c67329b427"),
            ("5.10.81-gki SMP aarch64",
             "5.10.81-gki-gc9c67329b427"),
            ("5.10.82-gki SMP aarch64", "5.10.82-gki"),
        ):
            with self.subTest(actual=actual, release=release):
                with self.assertRaisesRegex(ValueError, "kernelrelease|vermagic"):
                    gate.check_camera_vermagic(actual, release)

    def test_empty_nm_cannot_pass(self):
        with self.assertRaisesRegex(ValueError, "no ELF symbols"):
            gate.parse_nm_posix("\n")


if __name__ == "__main__":
    unittest.main()
