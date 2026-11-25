"""Keep the diagnostic Xiaomi display separate from production and expiring CI archives."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class XiaomiDisplayPatchContractTests(unittest.TestCase):
    def test_reviewable_patch_series_and_real_kernel(self):
        script = (ROOT / "tools/qualify_xiaomi_garnet_display.py").read_text()
        patches = sorted((ROOT / "patches/xiaomi-display").glob("*.patch"))
        self.assertEqual(len(patches), 4)
        for path in patches:
            self.assertIn(path.name, script)
            self.assertIn("diff --git ", path.read_text())
        self.assertIn('nonempty(ko / "vmlinux")', script)
        self.assertIn('"git", "apply", "--check"', script)
        self.assertIn('imported_crcs_checked=len(imports)', script)
        self.assertNotIn("REPLAY_RUN", script)
        self.assertNotIn("SDE_FIXES", script)
        self.assertNotIn("45445498683", script)

    def test_m11a_scope_is_explicit_and_refuses_foreign_panels(self):
        script = (ROOT / "tools/qualify_xiaomi_garnet_display.py").read_text()
        patch = (ROOT / "patches/xiaomi-display/0004-mondrian-m11a-pwrkey-scope.patch").read_text()
        self.assertIn('"PE_MONDRIAN_M11A_ONLY=1"', script)
        self.assertIn("0x4D31314100420200", script)
        self.assertIn("Foreign-panel power-key callback still imported", script)
        self.assertIn("ifeq ($(PE_MONDRIAN_M11A_ONLY),1)", patch)
        self.assertIn("panel_id != M11A_42_02_0A_PANEL_ID", patch)
        self.assertIn("rc = -ENODEV;", patch)
        self.assertEqual(patch.count("+#ifndef PE_MONDRIAN_M11A_ONLY"), 2)
        self.assertIn("mi_display_pwrkey_callback_set(mi_display_powerkey_callback);", patch)
        self.assertNotIn("EXPORT_SYMBOL", patch)

    def test_candidate_and_kernel_share_one_real_build_job(self):
        workflow = (ROOT / ".github/workflows/oem-coherent-wlan-compile.yml").read_text()
        self.assertLess(workflow.index("Build full OEM vmlinux"),
                        workflow.index("Compile full Xiaomi Display"))
        self.assertLess(workflow.index("Build Qualcomm official MMRM"),
                        workflow.index("Compile full Xiaomi Display"))
        self.assertIn("inputs.scope == 'display'", workflow)
        self.assertIn("git -C xiaomi-display-preflight apply --check", workflow)
        self.assertNotIn("download-artifact", workflow)
        self.assertFalse((ROOT / ".github/workflows/xiaomi-garnet-dsi-candidate.yml").exists())
