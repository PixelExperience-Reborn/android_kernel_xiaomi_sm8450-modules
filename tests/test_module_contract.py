import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ModuleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads((ROOT / "modules-bsp-candidates.json").read_text())

    def test_scope_and_source_pins(self):
        d = self.cfg
        self.assertEqual(d["schema_version"], 1)
        self.assertEqual(d["device"], "mondrian")
        self.assertEqual(d["soc"], "SM8475")
        self.assertEqual(d["android_base"], "AOSP 17")
        self.assertEqual(d["build_status"], "not_buildable")
        s = d["reference_module_source"]
        self.assertEqual(s["status"], "read_only_not_selected")
        self.assertNotEqual(s["commit_sha"], s["tree_sha"])
        for key in ("commit_sha", "tree_sha"):
            self.assertRegex(s[key], r"^[0-9a-f]{40}$")

    def test_oem_ordered_list_is_unqualified(self):
        oem = self.cfg["reference_oem_list"]
        self.assertEqual(oem["ordered_entries"], 106)
        self.assertEqual(oem["unique_entries"], 104)
        self.assertEqual(set(oem["duplicates"]), {"gh_virt_wdt.ko", "qcom_wdt_core.ko"})
        self.assertRegex(oem["blob_sha"], r"^[0-9a-f]{40}$")

    def test_no_unsafe_kernel_or_partition_assumptions(self):
        q = self.cfg["required_qualification"]
        for key in ("kernel_source_commit", "kernel_config_hash", "toolchain_revision", "kmi_symbol_list_hash", "module_symvers_hash", "compiled_modules_hash"):
            self.assertIsNone(q[key])
        for key in ("dependency_order_qualified", "vendor_boot_modules_qualified", "vendor_dlkm_modules_qualified", "firmware_qualified", "boot_proven"):
            self.assertIs(q[key], False)
        self.assertIn("FM radio", self.cfg["exclusions"])
        self.assertIn("ROM-specific LineageOS product dependencies", self.cfg["exclusions"])


if __name__ == "__main__":
    unittest.main()
