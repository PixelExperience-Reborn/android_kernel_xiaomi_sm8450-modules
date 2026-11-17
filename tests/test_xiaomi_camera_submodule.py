"""Source-lock regression tests for the real Xiaomi Camera BSP Gitlink."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "camera_gitlink", ROOT / "tools/verify_xiaomi_camera_submodule.py")
camera = importlib.util.module_from_spec(spec)
spec.loader.exec_module(camera)


class XiaomiCameraGitlinkTests(unittest.TestCase):
    def test_exact_real_repo_submodule(self):
        camera.validate_gitmodules((ROOT / ".gitmodules").read_text())
        self.assertEqual(camera.SUBMODULE, "xiaomi-camera-source")
        self.assertEqual(len(camera.COMMIT), 40)

    def test_correct_oem_source_provenance(self):
        manifest = json.loads((ROOT / camera.MANIFEST).read_text())
        camera.verify_pinned_metadata(manifest)
        self.assertFalse(manifest["policy"]["lineage_code_imported"])
        self.assertFalse(manifest["policy"]["fm_radio_selected"])

    def test_non_oem_url_rejected(self):
        text = (ROOT / ".gitmodules").read_text()
        modified = text.replace(camera.URL, "https://example.com/donor.git")
        with self.assertRaisesRegex(ValueError, "non-Xiaomi"):
            camera.validate_gitmodules(modified)

    def test_camera_gitlink_ignores_branch_names_and_wrong_sha(self):
        expected = "160000 commit " + camera.COMMIT + "\t" + camera.SUBMODULE
        camera.verify_gitlink_row(expected)
        for row in (
            expected.replace(camera.COMMIT, "0" * 40),
            expected.replace("160000", "100644"),
            expected.replace("\t" + camera.SUBMODULE, "\tother/device"),
            "160000 commit yudi-t-oss\t" + camera.SUBMODULE,
        ):
            with self.subTest(row=row):
                with self.assertRaises(ValueError):
                    camera.verify_gitlink_row(row)

    def test_missing_or_drifted_camera_candidate_rejected(self):
        data = json.loads((ROOT / camera.MANIFEST).read_text())
        for value in ("0" * 40, "HEAD"):
            candidate = json.loads(json.dumps(data))
            candidate["manufacturer_candidate"]["commit"] = value
            with self.assertRaisesRegex(ValueError, "drifts"):
                camera.verify_pinned_metadata(candidate)


if __name__ == "__main__":
    unittest.main()
