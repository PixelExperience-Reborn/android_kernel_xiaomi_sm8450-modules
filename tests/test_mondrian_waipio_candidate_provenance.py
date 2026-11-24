"""Guard the exact upstream candidate pins; never promote audit to selection."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WaipioCandidateProvenance(unittest.TestCase):
    def test_scope_and_verified_manifest(self):
        lock = json.loads((ROOT / "qualcomm-mondrian-waipio-11900-candidates.json").read_text())
        self.assertEqual(lock["device"], "mondrian")
        self.assertEqual(lock["soc"], "SM8475")
        self.assertEqual(lock["android_base"], "AOSP 17")
        self.assertEqual(lock["manifest"]["tag"], "LA.VENDOR.1.0.r1-11900-WAIPIO.0")
        self.assertEqual(lock["manifest"]["commit"], "4ada7dbba74eacc651b1a0852ec90d7801c8199c")
        self.assertEqual({k: v["commit"] for k, v in lock["projects"].items()}, {
            "dataipa": "17561e53321d461e4d73e1a861e97c2af925823a",
            "datarmnet": "cc9cb6220a426df0506fcd9759d46b4033d0d6c9",
            "datarmnet-ext": "5aa3b6c45d19245fbae654e015532a61f32c1beb",
            "eva-kernel": "8613d42b73d64780a62eb4cc5cfdda1e22551c1a",
            "cvp-kernel": "7bc10ddcdf26cfd898ee3d141b251a67fcdba202",
        })
        self.assertTrue(lock["qualification"]["official_manifest_and_source_commits_verified"])
        for name in ("exact_xiaomi_oem_release_match_verified", "source_imported",
                     "selected_for_build", "kmi_verified", "hardware_verified"):
            self.assertFalse(lock["qualification"][name])
        self.assertEqual(lock["evidence"]["workflow_run"], 45432312156)

    def test_no_candidate_gitlinks_added(self):
        gitmodules = (ROOT / ".gitmodules").read_text()
        for name in ("dataipa", "datarmnet", "datarmnet-ext", "eva-kernel", "cvp-kernel"):
            self.assertNotIn("/" + name + ".git", gitmodules)


if __name__ == "__main__":
    unittest.main()
