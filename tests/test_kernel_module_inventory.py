"""Regression tests for original Xiaomi module inventory without runtime guesses."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "mondrian_inventory", ROOT / "tools/audit_mondrian_kernel_module_inventory.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        obj = self.root / module.BUILTIN_EXPECTATION[2]
        obj.parent.mkdir(parents=True)
        obj.write_bytes(b"compiled")
        self.expected = [f"a{i}.ko" for i in range(100)]
        self.expected += [module.BUILTIN_EXPECTATION[0], *module.OPTIONAL_UNSHIPPED]
        self.expected += ["a0.ko", "a1.ko"]
        self.built = {name: object() for name in self.expected
                      if name not in module.OPTIONAL_UNSHIPPED
                      and name != module.BUILTIN_EXPECTATION[0]}
        self.config = {module.BUILTIN_EXPECTATION[1]: "y"}

    def test_oem_counts_and_known_exceptions(self):
        report = module.classify(self.expected, self.built, self.config, self.root)
        self.assertEqual(report["compiled_oem_names"], 100)
        self.assertEqual(report["oem_entries"], 106)
        self.assertEqual(len(module.MONDRIAN_CRITICAL_MODULES), 15)
        self.assertIn("wl2866d.ko", module.MONDRIAN_CRITICAL_MODULES)
        self.assertIn("goodix_fod.ko", module.MONDRIAN_CRITICAL_MODULES)

    def test_missing_essential_module_rejected(self):
        self.built.pop("a10.ko")
        with self.assertRaisesRegex(ValueError, "unreviewed OEM missing"):
            module.classify(self.expected, self.built, self.config, self.root)

    def test_shipping_debug_rtb_rejected(self):
        self.config["CONFIG_QCOM_RTB"] = "m"
        with self.assertRaisesRegex(ValueError, "unexpectedly enabled"):
            module.classify(self.expected, self.built, self.config, self.root)

    def test_builtin_dma_heap_absent_rejected(self):
        (self.root / module.BUILTIN_EXPECTATION[2]).unlink()
        with self.assertRaisesRegex(ValueError, "compiled built-in"):
            module.classify(self.expected, self.built, self.config, self.root)

    def test_unreviewed_fm_selection_rejected(self):
        self.expected[42] = "bt_fm_slim.ko"
        with self.assertRaisesRegex(ValueError, "FM Slimbus"):
            module.classify(self.expected, self.built, self.config, self.root)


if __name__ == "__main__":
    unittest.main()
