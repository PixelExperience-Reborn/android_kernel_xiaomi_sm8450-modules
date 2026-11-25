"""OEM QCA6490 PCIe CE-SRNG implicit-prototype regression checks."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("wlanfix", ROOT / "tools/apply_oem_wlan_fix.py")
fix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fix)

class QualcommCeSrngTests(unittest.TestCase):
    def test_exact_manufacturer_blob_and_signature(self):
        entries = [s for s in fix.PATCHES
                   if s["path"] == "qca-wifi-host-cmn/hif/src/ce/ce_service_srng.c"]
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["blob"], "318f50f93229be97404394b882ad9ebae73b4a67")
        self.assertEqual(e["from"], b"struct ce_ops *ce_services_srng()\n")
        self.assertEqual(e["to"], b"struct ce_ops *ce_services_srng(void)\n")
        self.assertNotIn("expected_occurrences", e)

    def test_signature_only_does_not_remove_ce_services(self):
        e = [s for s in fix.PATCHES if s["path"].endswith("ce_service_srng.c")][0]
        original = (
            b"struct ce_ops *ce_services_srng()\n"
            b"{\n"
            b"\treturn &ce_service_srng;\n"
            b"}\n"
            b"qdf_export_symbol(ce_services_srng);\n"
            b"void ce_service_srng_init(void)\n"
            b"{\n"
            b"\tce_service_register_module(CE_SVC_SRNG, &ce_services_srng);\n"
            b"}\n"
        )
        self.assertEqual(original.count(e["from"]), 1)
        changed = original.replace(e["from"], e["to"])
        self.assertEqual(changed.count(e["to"]), 1)
        self.assertIn(b"return &ce_service_srng;", changed)
        self.assertIn(b"qdf_export_symbol(ce_services_srng);", changed)
        self.assertIn(b"ce_service_register_module(CE_SVC_SRNG, &ce_services_srng);", changed)

    def test_full_wlan_ci_validates_fix_before_build(self):
        for path in (".github/workflows/oem-wlan-compile.yml",
                     ".github/workflows/oem-coherent-wlan-compile.yml"):
            wf = (ROOT / path).read_text()
            self.assertIn("python3 tools/apply_oem_wlan_fix.py --apply", wf)
            self.assertLess(wf.index("python3 tools/apply_oem_wlan_fix.py --apply"),
                            wf.index("Build Xiaomi QCACLD QCA6490 as external kernel module"))

if __name__ == "__main__":
    unittest.main()
