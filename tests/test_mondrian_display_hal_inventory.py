"""Unit tests for the offline HAL inventory; not a hardware or HAL test."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "display_hal_inventory", ROOT / "tools/audit_mondrian_display_hal.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def elf(cls=2, machine=183, suffix=b""):
    data = bytearray(64)
    data[:6] = b"\x7fELF" + bytes([cls, 1])
    data[18:20] = machine.to_bytes(2, "little")
    return bytes(data) + suffix


class MondrianDisplayHALInventoryTests(unittest.TestCase):
    def test_direct_path_and_architecture(self):
        report = audit.identify(elf(suffix=b"/dev/mi_display/disp_feature\0"), "other.so")
        self.assertTrue(report["full_disp_feature_path_literal"])
        self.assertEqual(report["architecture"], "AArch64")
        self.assertFalse(report["filename_hint"])

    def test_split_strings_and_32bit_candidate(self):
        report = audit.identify(elf(1, 40, b"mi_display\0disp_feature\0"), "library.so")
        self.assertTrue(report["mi_display_and_disp_feature_literals"])
        self.assertFalse(report["full_disp_feature_path_literal"])
        self.assertEqual(report["architecture"], "ARM")

    def test_name_is_only_a_hint(self):
        report = audit.identify(elf(), "vendor.fingerprint.so")
        self.assertTrue(report["filename_hint"])
        self.assertFalse(report["full_disp_feature_path_literal"])
        self.assertIsNone(audit.identify(elf(), "unrelated.so"))
        self.assertIsNone(audit.identify(elf(2, 62), "fingerprint.so"))
        self.assertIsNone(audit.identify(b"not ELF", "display.so"))

    def test_sysfs_only_consumers_are_not_discarded(self):
        for path in audit.DISPLAY_SYSFS:
            with self.subTest(path=path):
                result = audit.identify(elf(suffix=path.encode() + b"\0"), "other.so")
                self.assertEqual(result["mi_display_sysfs_path_literals"], [path])
                self.assertFalse(result["full_disp_feature_path_literal"])
                self.assertFalse(result["filename_hint"])

    def test_goodix_dependency_is_a_candidate_without_literals(self):
        result = audit.identify(elf(), "libgf_hal.so")
        self.assertTrue(result["filename_hint"])
        self.assertEqual(result["mi_display_sysfs_path_literals"], [])

    def test_fortified_io_imports_are_detected(self):
        symbols = ("  1: 0 0 FUNC GLOBAL DEFAULT UND __open_2@LIBC\n"
                   "  2: 0 0 FUNC GLOBAL DEFAULT UND __write_chk@LIBC\n"
                   "  3: 0 0 FUNC GLOBAL DEFAULT UND __read_chk@LIBC\n"
                   "  4: 0 0 FUNC GLOBAL DEFAULT UND close@LIBC\n"
                   "  5: 0 0 FUNC GLOBAL DEFAULT 12 write\n")
        self.assertEqual(audit.parse_readelf("", symbols)["io_imports"],
                         ["__open_2", "__read_chk", "__write_chk", "close"])

    def test_imports_do_not_imply_call_arguments(self):
        dynamic = "0x0001 (NEEDED) Shared library: [libc.so]\n"
        symbols = ("  1: 0 0 FUNC GLOBAL DEFAULT UND read@LIBC (2)\n"
                   "  2: 0 0 FUNC GLOBAL DEFAULT UND ioctl@LIBC (2)\n"
                   "  3: 0 0 FUNC GLOBAL DEFAULT 12 poll\n")
        self.assertEqual(audit.parse_readelf(dynamic, symbols),
                         {"needed": ["libc.so"], "io_imports": ["ioctl", "read"]})
