"""Byte-exact regression tests for source-only Xiaomi Camera Clang 23 patch."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "camera_clang_fix", ROOT / "tools/apply_xiaomi_camera_clang23_fix.py")
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)


class XiaomiCameraClang23Tests(unittest.TestCase):
    def setUp(self):
        self.src = b"int before(void) { return 0; }\n" + patch.OLD + (
            b"{\n\treturn &cam_debug;\n}\n")
        self.header = b"#pragma once\n" + patch.HEADER_DECL + b"\n"

    def test_only_definition_changes_not_behavior(self):
        corrected = patch.patch_definition(self.src, self.header)
        self.assertEqual(corrected, self.src.replace(patch.OLD, patch.NEW))
        self.assertEqual(corrected.count(b"return &cam_debug;"), 1)
        self.assertNotIn(patch.OLD, corrected)

    def test_rejects_changed_header(self):
        with self.assertRaisesRegex(ValueError, "header"):
            patch.patch_definition(self.src, b"prototype changed")

    def test_rejects_duplicate_or_missing_old_definition(self):
        for candidate in (self.src + patch.OLD,
                          self.src.replace(patch.OLD, b""),
                          self.src.replace(patch.OLD, patch.NEW)):
            with self.subTest(candidate=candidate[-80:]):
                with self.assertRaises(ValueError):
                    patch.patch_definition(candidate, self.header)

    def test_immutable_oem_blob_pins(self):
        self.assertEqual(len(patch.OEM_COMMIT), 40)
        self.assertEqual(len(patch.SOURCE_BLOB), 40)
        self.assertEqual(len(patch.HEADER_BLOB), 40)
        self.assertEqual(patch.SOURCE.as_posix(),
                         "drivers/cam_utils/cam_debug_util.c")
        self.assertEqual(patch.HEADER.as_posix(),
                         "drivers/cam_utils/cam_debug_util.h")
        self.assertNotEqual(patch.blob_id(self.src),
                            patch.blob_id(patch.patch_definition(
                                self.src, self.header)))


if __name__ == "__main__":
    unittest.main()
