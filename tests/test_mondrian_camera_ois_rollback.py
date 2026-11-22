"""OEM Xiaomi camera OIS error-unwind source and diff contract.

The Qualcomm platform OIS driver must be unregistered if its follow-up I2C
driver registration fails. Do not borrow another ROM or change hardware DT.
"""
import hashlib
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "xiaomi-camera-source/drivers/cam_sensor_module/cam_ois/cam_ois_dev.c"
PATCH = ROOT / "patches/mondrian-camera-ois-driver-init-rollback.patch"
OEM_SOURCE_BLOB = "90071b155ed33071dd96706819a3d5d371f107e1"
OEM_REVISION = "9ed4ce96d49c0759c6365627113c5f59c2407942"

OLD = (
    b"\trc = i2c_add_driver(&cam_ois_i2c_driver);\n"
    b"\tif (rc) {\n"
    b'\t\tCAM_ERR(CAM_OIS, "i2c_add_driver failed rc = %d", rc);\n'
    b"\t\treturn rc;\n"
    b"\t}\n"
)
NEW = (
    b"\trc = i2c_add_driver(&cam_ois_i2c_driver);\n"
    b"\tif (rc) {\n"
    b'\t\tCAM_ERR(CAM_OIS, "i2c_add_driver failed rc = %d", rc);\n'
    b"\t\tplatform_driver_unregister(&cam_ois_platform_driver);\n"
    b"\t\tregistered_driver.platform_driver = 0;\n"
    b"\t\treturn rc;\n"
    b"\t}\n"
)


def sha_git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() +
                        b"\0" + data).hexdigest()


class CameraOisDriverRollbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = SOURCE.read_bytes()
        cls.diff = PATCH.read_text()
        cls.revision = subprocess.check_output(
            ["git", "-C", str(ROOT / "xiaomi-camera-source"),
             "rev-parse", "HEAD"], text=True).strip()

    def test_original_xiaomi_camera_ois_source_pinned(self):
        self.assertEqual(self.revision, OEM_REVISION)
        self.assertEqual(sha_git_blob(self.original), OEM_SOURCE_BLOB)
        self.assertEqual(self.original.count(OLD), 1)
        self.assertNotIn(NEW, self.original)

    def test_error_unwind_releases_original_platform_registration(self):
        self.assertEqual(self.diff.count("+\t\tplatform_driver_unregister(&cam_ois_platform_driver);"), 1)
        self.assertEqual(self.diff.count("+\t\tregistered_driver.platform_driver = 0;"), 1)
        self.assertNotIn("-\t\treturn rc;", self.diff)
        self.assertEqual(self.diff.count("diff --git "), 1)
        self.assertIn("drivers/cam_sensor_module/cam_ois/cam_ois_dev.c", self.diff)
        patched = self.original.replace(OLD, NEW)
        self.assertEqual(len(patched) - len(self.original), len(NEW) - len(OLD))
        self.assertIn(b"void cam_ois_driver_exit(void)", patched)
        self.assertIn(b"registered_driver.i2c_driver = 1;", patched)

    def test_patch_applies_to_exact_unmodified_oem_source(self):
        subprocess.run(
            ["git", "-C", str(ROOT / "xiaomi-camera-source"),
             "apply", "--check", str(PATCH)], check=True, capture_output=True)

    def test_both_real_camera_compile_workflows_apply_fix(self):
        for workflow in (
            ".github/workflows/oem-coherent-wlan-compile.yml",
            ".github/workflows/xiaomi-camera-compile-abi.yml",
        ):
            with self.subTest(workflow=workflow):
                w = (ROOT / workflow).read_text()
                marker = 'git -C xiaomi-camera-source apply "$GITHUB_WORKSPACE/patches/mondrian-camera-ois-driver-init-rollback.patch"'
                self.assertEqual(w.count(marker), 1)
                self.assertIn("test_mondrian_camera_ois_rollback.py", w if workflow.endswith("oem-coherent-wlan-compile.yml") else
                              (ROOT / ".github/workflows/oem-coherent-wlan-compile.yml").read_text())
                self.assertLess(w.index(marker), w.index("Build Xiaomi Camera") if "Build Xiaomi Camera" in w else
                                w.index("Build OEM Xiaomi Camera") if "Build OEM Xiaomi Camera" in w else len(w))


if __name__ == "__main__":
    unittest.main()
