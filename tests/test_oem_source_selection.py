import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class OemSourceSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / "modules-bsp-candidates.json").read_text())

    def test_manufacturer_kernel_and_wlan_are_pinned(self):
        selected = self.cfg["selected_oem_source_candidates"]
        kernel = selected["kernel"]
        wlan = selected["wlan"]
        self.assertEqual(kernel["repository"], "MiCode/Xiaomi_Kernel_OpenSource")
        self.assertEqual(kernel["branch"], "mondrian-s-oss")
        self.assertEqual(wlan["repository"], "MiCode/vendor_qcom_opensource_wlan")
        self.assertEqual(wlan["branch"], "mondrian-s-oss")
        self.assertEqual(len(kernel["commit_sha"]), 40)
        self.assertEqual(len(wlan["commit_sha"]), 40)
        self.assertEqual(len(wlan["qcacld_kbuild_blob_sha"]), 40)
        self.assertEqual(set(wlan["source_subtrees"]), {"qcacld-3.0", "qca-wifi-host-cmn", "fw-api"})

    def test_no_unverified_external_driver_or_abi_claim(self):
        selected = self.cfg["selected_oem_source_candidates"]
        self.assertEqual(self.cfg["build_status"], "not_buildable")
        self.assertFalse(selected["abi_verified"])
        self.assertFalse(selected["external_ko_compiled"])
        self.assertFalse(selected["vendor_dlkm_packaged"])
        self.assertFalse(selected["hardware_qualified"])
        self.assertFalse(selected["audio"]["mondrian_s_oss_branch_exists"])
        self.assertEqual(selected["missing_modules"]["status"],
                         "Qualcomm BSP revisions not selected; no external driver source imported")

    def test_comparison_source_remains_read_only(self):
        self.assertEqual(self.cfg["reference_module_source"]["status"], "read_only_not_selected")
        self.assertIn("FM radio", self.cfg["exclusions"])
        self.assertIn("sigma-dut", self.cfg["selected_oem_source_candidates"]["wlan"]["optional_not_selected"])

if __name__ == "__main__":
    unittest.main()
