"""Fail closed if either Xiaomi QCACLD build silently selects SNOC on mondrian."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
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

if __name__ == "__main__":
    unittest.main()
