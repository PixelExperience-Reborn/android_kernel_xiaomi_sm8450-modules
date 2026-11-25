"""PR source gates remain light; authorized branch push may run ServerHive Full LTO."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CIConcurrencyTests(unittest.TestCase):
    def test_coherent_pr_sources_and_trusted_serverhive_full_build(self):
        text = (ROOT / ".github/workflows/oem-coherent-wlan-compile.yml").read_text()
        triggers = text.split("jobs:\n", 1)[0]
        self.assertNotIn("\n  pull_request:", triggers)
        self.assertIn("\n  workflow_dispatch:", triggers)
        self.assertIn("\n  push:\n", triggers)
        self.assertIn("      - bringup/a17-mondrian-oem-bsp-20261111", triggers)
        self.assertIn("      - .github/workflows/oem-coherent-wlan-compile.yml", triggers)
        self.assertIn("contains(github.event.head_commit.message, '[serverhive-qualification]')", text)
        self.assertIn("group: mondrian-heavy", text)
        self.assertIn(
            "group: mondrian-coherent-external-wlan-build-${{ github.event_name }}-${{ github.head_ref || github.ref_name }}",
            text,
        )
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("    needs: source", text)
        self.assertIn("    timeout-minutes: 90", text)
        self.assertIn("    if: github.event_name == 'workflow_dispatch'", text)

    def test_camera_full_kernel_compile_is_manual_only(self):
        text = (ROOT / ".github/workflows/xiaomi-camera-compile-abi.yml").read_text()
        triggers = text.split("jobs:\n", 1)[0]
        self.assertIn("\n  workflow_dispatch:\n", triggers)
        self.assertNotIn("\n  push:\n", triggers)
        self.assertNotIn("\n  pull_request:\n", triggers)
        self.assertIn("Compile real OEM vmlinux, Image and Module.symvers", text)
        # The regular unit-test suite is still run on every push and PR.
        contracts = (ROOT / ".github/workflows/module-contract.yml").read_text()
        self.assertIn("\n  push:\n", contracts)
        self.assertIn("\n  pull_request:\n", contracts)
        self.assertIn("python3 -m unittest discover -s tests -v", contracts)
        self.assertIn("github.event.pull_request.head.repo.full_name != github.repository", contracts)
        self.assertIn("submodules: recursive", contracts)

    def test_standalone_wlan_is_source_only_automatically(self):
        text = (ROOT / ".github/workflows/oem-wlan-compile.yml").read_text()
        self.assertIn("group: mondrian-oem-external-wlan-build-${{ github.event_name }}", text)
        triggers = text.split("jobs:\n", 1)[0]
        self.assertNotIn("\n  push:", triggers)
        self.assertNotIn("\n  pull_request:", triggers)
        self.assertIn("if: github.event_name == 'workflow_dispatch'", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("    needs: source", text)
        self.assertIn("CONFIG_CNSS_QCA6490=y CONFIG_ROME_IF=pci", text)
        self.assertIn("multibus_pci.o", text)
        self.assertNotIn("if: github.event_name != 'pull_request'", text)


if __name__ == "__main__":
    unittest.main()
