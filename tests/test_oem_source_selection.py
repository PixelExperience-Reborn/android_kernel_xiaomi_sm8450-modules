import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "tools"))
from mondrian_source_pins import load_pins

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
        self.assertEqual(self.cfg["build_status"], "current_kernel_full_lto_and_external_bsp_abi_pending")
        verified = self.cfg["last_verified_build"]
        self.assertEqual(verified["run_id"], 43088150435)
        self.assertEqual(verified["head"],
                         "ae801df4a5fe8bb0c367c2df3c31a1dbaa49b773")
        self.assertTrue(verified["kernel_llvm23_compiled"])
        self.assertTrue(verified["mmrm_compiled"])
        self.assertTrue(verified["wlan_compiled"])
        self.assertFalse(selected["abi_verified"])
        self.assertFalse(selected["external_ko_compiled"])
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


    def test_selected_kernel_matches_both_ci_paths_and_no_abi_implicit_fallback(self):
        """Old verified run is historical, not proof for the active pinned kernel."""
        selected = self.cfg["selected_oem_source_candidates"]
        current = load_pins()["kernel"]
        old = "2466406b9beac724960b0c88e6e794421d0466e7"
        self.assertEqual(selected["selected_kernel"]["commit_sha"], current)
        self.assertEqual(self.cfg["wlan_runtime_closure"]["kernel_commit"], current)
        self.assertNotEqual(current, old)
        self.assertTrue(self.cfg["last_verified_build"]["kernel_llvm23_compiled"])
        for filename in ("oem-coherent-wlan-compile.yml", "oem-wlan-compile.yml"):
            workflow = (ROOT / ".github/workflows" / filename).read_text()
            self.assertIn("ref: ${{ steps.pins.outputs.kernel }}", workflow)
            self.assertIn("run: python3 tools/mondrian_source_pins.py github", workflow)
            self.assertNotIn("ref: " + old, workflow)
        helper = (ROOT / "tools/verify_external_module_abi.py").read_text()
        self.assertIn('p.add_argument("--expected-kernel-commit", required=True,', helper)
        self.assertNotIn("DEFAULT_KERNEL_COMMIT", helper)
        self.assertIn('kernel_sha="$(python3 tools/mondrian_source_pins.py kernel)"', (ROOT / "tools/build_mondrian_audio_video.sh").read_text())

    def test_audio_source_is_xiaomi_ziyi_without_fm(self):
        audio = self.cfg["selected_oem_source_candidates"]["audio"]
        self.assertEqual(audio["repository"], "MiCode/vendor_qcom_opensource_audio-kernel")
        self.assertEqual(audio["branch"], "ziyi-s-oss")
        self.assertEqual(audio["commit_sha"],
                         "8b1c8d3486a7ac3349d1422201a4436ad852fcb1")
        self.assertFalse(audio["fm_radio_enabled"])
        self.assertEqual(audio["status"], "selected_for_oem_waipio_audio_diagnostic_build_abi_pending")

    def test_comparison_source_remains_read_only(self):
        self.assertEqual(self.cfg["reference_module_source"]["status"], "read_only_not_selected")
        self.assertIn("FM radio", self.cfg["exclusions"])
        self.assertIn("sigma-dut", self.cfg["selected_oem_source_candidates"]["wlan"]["optional_not_selected"])

if __name__ == "__main__":
    unittest.main()
