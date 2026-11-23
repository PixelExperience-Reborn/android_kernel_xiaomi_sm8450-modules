"""Ensure the OEM 5.10.81 Full LTO integration has real runner resource controls."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
COHERENT = ROOT / ".github/workflows/oem-coherent-wlan-compile.yml"
STANDALONE = ROOT / ".github/workflows/oem-wlan-compile.yml"
SCRIPT = ROOT / "tools/prepare_mondrian_lto_resources.sh"
LINKER_SCRIPT = ROOT / "tools/prepare_mondrian_lto_linker.sh"


class FullLtoResourceTests(unittest.TestCase):
    def test_one_automatic_full_kernel_link(self):
        coherent = COHERENT.read_text()
        standalone = STANDALONE.read_text()
        coherent_triggers = coherent.split("jobs:\n", 1)[0]
        self.assertNotIn("\n  push:", coherent_triggers)
        self.assertIn("\n  pull_request:", coherent_triggers)
        self.assertIn("\n  workflow_dispatch:", coherent_triggers)
        self.assertIn("if: github.event_name == 'workflow_dispatch'", standalone)
        self.assertNotIn("if: github.event_name != 'pull_request'", standalone)
        self.assertIn("Build Xiaomi QCACLD QCA6490 as external kernel module", coherent)
        self.assertIn("Build Xiaomi QCACLD QCA6490 as external kernel module", standalone)
        self.assertIn("CONFIG_CNSS_QCA6490=y CONFIG_ROME_IF=pci", coherent)
        self.assertIn("WLAN_CTRL_NAME=wlan TARGET_BUILD_VARIANT=user DYNAMIC_SINGLE_CHIP=qca6490", coherent)

    def test_full_kernel_link_is_not_replaced_with_fake_module_only_job(self):
        for workflow in (COHERENT, STANDALONE):
            text = workflow.read_text()
            self.assertIn("Prepare bounded Full LTO memory and disk headroom", text)
            self.assertIn("bash tools/prepare_mondrian_lto_resources.sh", text)
            self.assertIn("source tools/prepare_mondrian_lto_linker.sh", text)
            self.assertIn('make -C kernel O="$RUNNER_TEMP/mondrian-out" -j2 vmlinux Image modules', text)
            self.assertIn("tools/verify_mondrian_kernel_hardening.py", text)
            self.assertIn("monitor_resources &", text)
            self.assertNotIn("CONFIG_LTO_CLANG_FULL=n", text)
            self.assertNotIn("CONFIG_LTO_NONE=y", text)

    def test_exact_clang23_lld_remains_full_lto_with_bounded_link_threads(self):
        text = LINKER_SCRIPT.read_text()
        self.assertIn("/tmp/google-clang/clang-r614150/bin/ld.lld", text)
        self.assertIn("--threads=1", text)
        self.assertIn("export PATH=", text)
        self.assertNotIn("CONFIG_LTO_NONE=y", text)
        self.assertNotIn("CONFIG_LTO_CLANG_THIN=y", text)

    def test_swap_is_optional_and_bounded_by_actual_free_disk(self):
        text = SCRIPT.read_text()
        self.assertIn('test -d "$RUNNER_TEMP"', text)
        self.assertIn("df -Pk", text)
        self.assertIn("available_kib <= SWAP_KIB + KEEP_FREE_KIB", text)
        self.assertIn("3 * 1024 * 1024", text)
        self.assertIn("4 * 1024 * 1024", text)
        self.assertIn('sudo chmod 600 "$swapfile"', text)
        self.assertIn('sudo mkswap "$swapfile"', text)
        self.assertIn('sudo swapon "$swapfile"', text)
        self.assertIn('sudo rm -f "$swapfile"', text)
        self.assertNotIn("CONFIG_CFI_CLANG=n", text)
        self.assertNotIn("CONFIG_SHADOW_CALL_STACK=n", text)


if __name__ == "__main__":
    unittest.main()
