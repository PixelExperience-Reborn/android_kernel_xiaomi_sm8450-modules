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
        self.assertEqual(self.cfg["build_status"], "oem_kernel_mmrm_wlan_compile_pass_other_bsp_incomplete")
        verified = self.cfg["last_verified_build"]
        self.assertEqual(verified["run_id"], 43088150435)
        self.assertEqual(verified["head"],
                         "ae801df4a5fe8bb0c367c2df3c31a1dbaa49b773")
        self.assertTrue(verified["kernel_llvm23_compiled"])
        self.assertTrue(verified["mmrm_compiled"])
        self.assertTrue(verified["wlan_compiled"])
        self.assertTrue(selected["abi_verified"])
        self.assertTrue(selected["external_ko_compiled"])
        self.assertFalse(verified["vendor_dlkm_release_qualified"])
        self.assertFalse(verified["device_runtime_qualified"])
        self.assertFalse(selected["vendor_dlkm_packaged"])
        self.assertFalse(selected["hardware_qualified"])
        self.assertFalse(selected["audio"]["mondrian_s_oss_branch_exists"])
        self.assertEqual(selected["missing_modules"]["status"],
                         "Remaining Qualcomm BSP source selection and compatibility pending")
        self.assertNotIn("MMRM", selected["missing_modules"]["categories"])
        self.assertTrue(self.cfg["wlan_runtime_closure"]["direct_modinfo_dependencies"])
        self.assertFalse(self.cfg["wlan_runtime_closure"]["vendor_dlkm_packaged"])

    def test_comparison_source_remains_read_only(self):
        self.assertEqual(self.cfg["reference_module_source"]["status"], "read_only_not_selected")
        self.assertIn("FM radio", self.cfg["exclusions"])
        self.assertIn("sigma-dut", self.cfg["selected_oem_source_candidates"]["wlan"]["optional_not_selected"])

if __name__ == "__main__":
    unittest.main()
