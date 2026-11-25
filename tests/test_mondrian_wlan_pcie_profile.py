"""Fail closed if either Xiaomi QCACLD build silently selects SNOC on mondrian."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "tools"))
from mondrian_source_pins import load_pins
KERNEL_SHA = load_pins()["kernel"]
MAKE_ARGS = (
    "CONFIG_CNSS_QCA6490=y", "CONFIG_ROME_IF=pci",
    "WLAN_CTRL_NAME=wlan", "TARGET_BUILD_VARIANT=user",
    "DYNAMIC_SINGLE_CHIP=qca6490",
)

class Qca6490PcieProfileTests(unittest.TestCase):
    def test_both_real_compiles_pin_pcie_source_and_chip(self):
        for path in (
            ".github/workflows/oem-wlan-compile.yml",
            ".github/workflows/oem-coherent-wlan-compile.yml",
        ):
            with self.subTest(path=path):
                s = (ROOT / path).read_text()
                step = s.split("      - name: Build Xiaomi QCACLD QCA6490 as external kernel module", 1)[1]
                step = step.split("      - name:", 1)[0]
                for arg in MAKE_ARGS:
                    self.assertEqual(step.count(arg), 1, arg)
                self.assertIn("WLAN_PROFILE=qca6490", step)
                self.assertIn("CONFIG_QCA_CLD_WLAN=m", step)
                self.assertIn("multibus_pci.o", step)
                self.assertIn("hal_6490.o", step)
                self.assertIn("multibus_snoc.o", step)
                self.assertIn("::error::SNOC HIF", step)
                self.assertLess(step.index("modules\n"), step.index("test -s", step.index("modules\n")))

    def test_no_conflicting_chip_or_bus_fallback(self):
        for path in (
            ".github/workflows/oem-wlan-compile.yml",
            ".github/workflows/oem-coherent-wlan-compile.yml",
        ):
            txt = (ROOT / path).read_text()
            self.assertNotIn("CONFIG_ROME_IF=snoc", txt)
            self.assertNotIn("CONFIG_CNSS_QCA6390=y", txt)
            self.assertNotIn("CONFIG_CNSS_QCA6750=y", txt)

    def test_standalone_and_coherent_jobs_use_exactly_the_same_kernel(self):
        standalone = (ROOT / ".github/workflows/oem-wlan-compile.yml").read_text()
        coherent = (ROOT / ".github/workflows/oem-coherent-wlan-compile.yml").read_text()
        stage = (ROOT / "tools/stage_mondrian_wlan_kmi.py").read_text()
        specialized = (ROOT / "tools/verify_external_wlan_abi.py").read_text()
        for workflow in (standalone, coherent):
            self.assertIn("ref: ${{ steps.pins.outputs.kernel }}", workflow)
            self.assertIn("run: python3 tools/mondrian_source_pins.py github", workflow)
            self.assertNotIn("ref: 2466406b9beac724960b0c88e6e794421d0466e7", workflow)
        self.assertIn('test "$(git -C kernel rev-parse HEAD)" = "$PE_KERNEL_SHA"', standalone)
        # OEM MMRM, WLAN and depmod staging must fail on a different kernel.
        self.assertEqual(standalone.count('--expected-kernel-commit "$PE_KERNEL_SHA"'), 3)
        self.assertIn('KERNEL_SHA = load_pins()["kernel"]', stage)
        self.assertEqual(specialized.count('load_pins()["kernel"]'), 2)

if __name__ == "__main__":
    unittest.main()
