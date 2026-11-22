"""Single-branch concurrency prevents duplicated push+PR whole-kernel builds."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class CIConcurrencyTests(unittest.TestCase):
    def test_same_branch_pr_and_push_share_cancel_group(self):
        for name in ("oem-coherent-wlan-compile.yml", "oem-wlan-compile.yml"):
            s = (ROOT / ".github/workflows" / name).read_text()
            self.assertIn("github.head_ref || github.ref_name", s)
            self.assertIn("cancel-in-progress: true", s)
            self.assertNotIn("group: mondrian-coherent-external-wlan-build-${{ github.event_name }}", s)
            self.assertNotIn("group: mondrian-oem-external-wlan-build-${{ github.event_name }}", s)

if __name__ == "__main__":
    unittest.main()
