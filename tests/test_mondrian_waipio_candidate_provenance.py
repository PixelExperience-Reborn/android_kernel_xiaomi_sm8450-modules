"""Guard the exact Qualcomm WAIPIO 11900 release pins selected for mondrian."""
import configparser
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLO = "https://git.codelinaro.org/clo/la/"
SELECTED = {
    "dataipa": ("upstream/qualcomm/dataipa",
                "platform/vendor/opensource/dataipa.git",
                "17561e53321d461e4d73e1a861e97c2af925823a"),
    "datarmnet": ("upstream/qualcomm/datarmnet",
                  "platform/vendor/qcom/opensource/datarmnet.git",
                  "cc9cb6220a426df0506fcd9759d46b4033d0d6c9"),
    "datarmnet-ext": ("upstream/qualcomm/datarmnet-ext",
                      "platform/vendor/qcom/opensource/datarmnet-ext.git",
                      "5aa3b6c45d19245fbae654e015532a61f32c1beb"),
    "eva-kernel": ("upstream/qualcomm/eva",
                   "platform/vendor/opensource/eva-kernel.git",
                   "8613d42b73d64780a62eb4cc5cfdda1e22551c1a"),
}


def lock():
    return json.loads((ROOT / "qualcomm-mondrian-waipio-11900-candidates.json").read_text())


class WaipioReleaseProvenance(unittest.TestCase):
    def test_scope_and_verified_manifest(self):
        data = lock()
        self.assertEqual(data["device"], "mondrian")
        self.assertEqual(data["soc"], "SM8475")
        self.assertEqual(data["android_base"], "AOSP 17")
        self.assertEqual(data["manifest"]["tag"], "LA.VENDOR.1.0.r1-11900-WAIPIO.0")
        self.assertEqual(data["manifest"]["commit"], "4ada7dbba74eacc651b1a0852ec90d7801c8199c")
        self.assertEqual({k: v["commit"] for k, v in data["projects"].items()}, {
            **{name: pin[2] for name, pin in SELECTED.items()},
            "cvp-kernel": "7bc10ddcdf26cfd898ee3d141b251a67fcdba202",
        })
        self.assertEqual(data["evidence"]["workflow_run"], 45432312156)

    def test_release_set_matches_xiaomi_kernel_baseline(self):
        data = lock()
        release = data["release_set"]
        self.assertEqual(release["kernel_platform"]["tag"], "KERNEL.PLATFORM.1.0.r1-07800-kernel.0")
        self.assertEqual(release["kernel_platform"]["linux_version"], "5.10.81")
        self.assertEqual(release["video"]["tag"], "VIDEO.LA.2.0.r1-03100-WAIPIO.0")
        self.assertEqual(release["video"]["video_driver_commit"],
                         "8608fb23bcb1cbffdc96b33eea3a79cb0228b72f")
        self.assertEqual(release["video"]["mmrm_driver_commit"],
                         "69e304b713271a6ee70ecdae9c97d9a7c9f0926f")
        self.assertEqual(release["display"]["tag"], "DISPLAY.LA.2.0.r1-05500-WAIPIO.0")
        self.assertEqual(release["camera"]["tag"], "CAMERA.LA.2.0.r1-04400-WAIPIO.0")
        qualification = data["qualification"]
        for name in ("official_manifest_and_source_commits_verified",
                     "exact_xiaomi_oem_release_match_verified",
                     "source_imported", "selected_for_build"):
            self.assertTrue(qualification[name], name)
        for name in ("kmi_verified", "hardware_verified"):
            self.assertFalse(qualification[name], name)

    def test_selected_gitlinks_and_no_cvp(self):
        config = configparser.ConfigParser(interpolation=None)
        config.read_string((ROOT / ".gitmodules").read_text())
        selection = lock()["selection"]
        for name, (path, url, commit) in SELECTED.items():
            with self.subTest(project=name):
                self.assertTrue(selection[name]["selected"])
                self.assertEqual(selection[name]["gitlink"], path)
                section = config['submodule "' + path + '"']
                self.assertEqual(dict(section), {"path": path, "url": CLO + url})
                tree = subprocess.check_output(["git", "-C", str(ROOT), "ls-tree", "HEAD", path],
                                               text=True).strip()
                self.assertEqual(tree, "160000 commit " + commit + "\t" + path)
        self.assertFalse(selection["cvp-kernel"]["selected"])
        self.assertNotIn("cvp-kernel.git", (ROOT / ".gitmodules").read_text())


if __name__ == "__main__":
    unittest.main()
