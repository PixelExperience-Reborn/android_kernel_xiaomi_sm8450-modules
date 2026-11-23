"""PR source gates run automatically; full OEM Full LTO builds are manual."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CIConcurrencyTests(unittest.TestCase):
    def test_coherent_pr_checks_sources_and_full_build_is_manual(self):
        text = (ROOT / ".github/workflows/oem-coherent-wlan-compile.yml").read_text()
        triggers = text.split("jobs:\n", 1)[0]
        self.assertIn("\n  pull_request:", triggers)
        self.assertIn("\n  workflow_dispatch:", triggers)
        self.assertNotIn("\n  push:", triggers)
        self.assertIn(
            "group: mondrian-coherent-external-wlan-build-${{ github.head_ref || github.ref_name }}",
            text,
        )
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("    needs: source", text)
        self.assertIn("    timeout-minutes: 90", text)
        self.assertIn("    if: github.event_name == 'workflow_dispatch'", text)

    def test_standalone_wlan_is_source_only_automatically(self):
        text = (ROOT / ".github/workflows/oem-wlan-compile.yml").read_text()
        self.assertIn("group: mondrian-oem-external-wlan-build-${{ github.event_name }}", text)
        self.assertIn("if: github.event_name == 'workflow_dispatch'", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("    needs: source", text)
        self.assertIn("CONFIG_CNSS_QCA6490=y CONFIG_ROME_IF=pci", text)
        self.assertIn("multibus_pci.o", text)
        self.assertNotIn("if: github.event_name != 'pull_request'", text)


if __name__ == "__main__":
    unittest.main()
