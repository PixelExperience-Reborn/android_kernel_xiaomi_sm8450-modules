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

    def test_exact_three_flash_prototype_fixes(self):
        flash = (
            b"#define I2C_FLASH_GPIO_EN 356\n"
            + b"{\n" + patch.FLASH_SIGNATURES[0] +
              b"{ return 0; }\n\tret = " + patch.FLASH_CALLS[0] + b"\n"
            + patch.FLASH_SIGNATURES[1] +
              b"{ return 0; }\n\tret = " + patch.FLASH_CALLS[1] + b"\n"
            + patch.FLASH_SIGNATURES[2] +
              b"{ return; }\n\t" + patch.FLASH_CALLS[2] + b"\n}\n"
        )
        patched = patch.patch_flash_definitions(flash)
        for signature in patch.FLASH_SIGNATURES:
            self.assertNotIn(signature, patched)
            self.assertIn(signature.replace(b"()\\n", b"(void)\\n"), patched)
        for call in patch.FLASH_CALLS:
            self.assertEqual(patched.count(call), 1)
        self.assertEqual(patched.count(patch.FLASH_GPIO_CONTRACT), 1)

    def test_flash_fails_closed_on_missing_or_duplicate_definitions(self):
        flash = (
            patch.FLASH_GPIO_CONTRACT + b"\n"
            + b"\n".join(
                b" ".join((signature.rstrip(b"\n"), call))
                for signature, call in zip(
                    patch.FLASH_SIGNATURES, patch.FLASH_CALLS
                )
            ) + b"\n"
        )
        patch.patch_flash_definitions(flash)
        for signature in patch.FLASH_SIGNATURES:
            for bad in (flash.replace(signature, b""),
                        flash + signature):
                with self.subTest(signature=signature, bad=bad[-40:]):
                    with self.assertRaises(ValueError):
                        patch.patch_flash_definitions(bad)
        with self.assertRaisesRegex(ValueError, "GPIO"):
            patch.patch_flash_definitions(
                flash.replace(patch.FLASH_GPIO_CONTRACT, b""))

    def test_immutable_oem_blob_pins(self):
        self.assertEqual(len(patch.OEM_COMMIT), 40)
        self.assertEqual(len(patch.SOURCE_BLOB), 40)
        self.assertEqual(len(patch.HEADER_BLOB), 40)
        self.assertEqual(patch.FLASH_BLOB,
                         "3a7514facf01022e628e2e59613fd980978f9358")
        self.assertEqual(patch.SOURCE.as_posix(),
                         "drivers/cam_utils/cam_debug_util.c")
        self.assertEqual(patch.HEADER.as_posix(),
                         "drivers/cam_utils/cam_debug_util.h")
        self.assertNotEqual(patch.blob_id(self.src),
                            patch.blob_id(patch.patch_definition(
                                self.src, self.header)))


if __name__ == "__main__":
    unittest.main()
