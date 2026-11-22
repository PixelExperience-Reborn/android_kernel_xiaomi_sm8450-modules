"""Avoid identical heavy PR+push builds without canceling required WLAN checks."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class CIConcurrencyTests(unittest.TestCase):
    def test_coherent_builds_coalesce_same_source_branch(self):
        text = (ROOT / ".github/workflows/oem-coherent-wlan-compile.yml").read_text()
        self.assertIn("group: mondrian-coherent-external-wlan-build-${{ github.head_ref || github.ref_name }}", text)
        self.assertIn("cancel-in-progress: true", text)
        self.assertNotIn("group: mondrian-coherent-external-wlan-build-${{ github.event_name }}", text)

    def test_wlan_push_full_build_not_canceled_by_pr_source_only(self):
        text = (ROOT / ".github/workflows/oem-wlan-compile.yml").read_text()
        self.assertIn("group: mondrian-oem-external-wlan-build-${{ github.event_name }}", text)
        self.assertIn("if: github.event_name != 'pull_request'", text)
        self.assertIn("cancel-in-progress: true", text)
        self.assertNotIn("group: mondrian-oem-external-wlan-build-${{ github.head_ref || github.ref_name }}", text)

if __name__ == "__main__":
    unittest.main()
