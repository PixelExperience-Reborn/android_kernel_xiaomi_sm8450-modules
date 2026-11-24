"""Fail-closed contract for the Qualcomm WAIPIO 11900 IPA/RMNET/EVA build."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


series = load("qcom_series", "tools/apply_qualcomm_patch_series.py")
sources = load("qcom_sources", "tools/verify_qualcomm_data_eva_sources.py")
BUILD = (ROOT / "tools/build_mondrian_data_eva.sh").read_text()
LOCK = json.loads((ROOT / "qualcomm-mondrian-waipio-11900-candidates.json").read_text())

EXPECTED_FILES = {
    "patches/qualcomm-dataipa/0001-external-module-build-paths.patch": {
        "drivers/platform/msm/Kbuild",
        "drivers/platform/msm/ipa/ipa_v3/ipa_trace.h",
        "drivers/platform/msm/ipa/ipa_clients/rndis_ipa_trace.h",
    },
    "patches/qualcomm-dataipa/0002-llvm23-prototypes-and-explicit-enum-casts.patch": {
        "drivers/platform/msm/gsi/gsihal/gsihal_reg.c",
        "drivers/platform/msm/ipa/ipa_v3/ipa_stats.c",
        "drivers/platform/msm/ipa/ipa_v3/rmnet_ipa.c",
    },
    "patches/qualcomm-datarmnet/0001-external-module-trace-include-path.patch": {
        "core/Kbuild", "core/dfc.h", "core/rmnet_trace.h", "core/wda.h",
    },
    "patches/qualcomm-eva/0001-llvm23-va-minidump-prototype.patch": {
        "msm/eva/cvp_dump.c",
    },
}


class PatchSeries(unittest.TestCase):
    def test_every_patch_is_reviewed_by_digest_and_scope(self):
        listed = {rel for patches in series.SERIES.values() for rel, _ in patches}
        self.assertEqual(listed, set(EXPECTED_FILES))
        on_disk = {str(p.relative_to(ROOT)) for p in ROOT.glob("patches/qualcomm-*/*.patch")}
        self.assertEqual(on_disk, listed)
        for patches in series.SERIES.values():
            for rel, digest in patches:
                with self.subTest(patch=rel):
                    data = (ROOT / rel).read_bytes()
                    self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
                    self.assertEqual(set(series.patched_paths(data.decode())), EXPECTED_FILES[rel])

    def test_patches_only_adapt_paths_prototypes_and_casts(self):
        ipa_paths = (ROOT / "patches/qualcomm-dataipa/0001-external-module-build-paths.patch").read_text()
        self.assertIn("+DATAIPA_ROOT ?= $(srctree)/../../vendor/qcom/opensource/dataipa", ipa_paths)
        self.assertIn("+#define TRACE_INCLUDE_PATH .", ipa_paths)
        ipa_llvm = (ROOT / "patches/qualcomm-dataipa/0002-llvm23-prototypes-and-explicit-enum-casts.patch").read_text()
        added = [l[1:] for l in ipa_llvm.splitlines() if l.startswith("+") and not l.startswith("+++")]
        self.assertEqual(sum("(void)" in l for l in added), 4)
        self.assertIn("\tq6_ul_flt_rule_ptr->ip = (enum ipa_ip_type)flt_spec_ptr->ip_type;", added)
        self.assertIn("\t\t(enum ipa_flt_action)flt_spec_ptr->filter_action;", added)
        rmnet = (ROOT / "patches/qualcomm-datarmnet/0001-external-module-trace-include-path.patch").read_text()
        self.assertIn("+ccflags-y\t+= -I$(src)", rmnet)
        eva = (ROOT / "patches/qualcomm-eva/0001-llvm23-va-minidump-prototype.patch").read_text()
        self.assertIn("+void cvp_register_va_md_region(void)", eva)
        for text in (ipa_paths, ipa_llvm, rmnet, eva):
            self.assertNotIn("-Wno", text)
            self.assertNotIn("pragma", text)


class BuildContract(unittest.TestCase):
    def test_order_and_no_warning_suppression(self):
        self.assertLess(BUILD.index("python3 tools/verify_qualcomm_data_eva_sources.py"),
                        BUILD.index("python3 tools/apply_qualcomm_patch_series.py"))
        self.assertLess(BUILD.index("python3 tools/apply_qualcomm_patch_series.py"),
                        BUILD.index('build dataipa M='))
        self.assertIn("unset KBUILD_MODPOST_WARN", BUILD)
        self.assertNotIn("KBUILD_MODPOST_WARN=1", BUILD)
        self.assertNotIn("-Wno-error", BUILD)
        self.assertIn('grep -q \'ipa_fmwk_register_ipa\' "$kout/Module.symvers"', BUILD)

    def test_module_list_matches_lock(self):
        built = set(re.findall(r'/([a-z0-9_-]+\.ko)"\n', BUILD))
        locked = {ko for name, sel in LOCK["selection"].items() if sel.get("selected")
                  for ko in sel["modules"]}
        self.assertEqual(built, locked)
        self.assertEqual(len(locked), 15)

    def test_gitlinks_are_pinned(self):
        sources.verify(ROOT, require_checkout=False)

    def test_ci_builds_before_dependency_closure(self):
        workflow = (ROOT / ".github/workflows/oem-coherent-wlan-compile.yml").read_text()
        self.assertLess(workflow.index("bash tools/build_mondrian_audio_video.sh"),
                        workflow.index("bash tools/build_mondrian_data_eva.sh"))
        self.assertLess(workflow.index("bash tools/build_mondrian_data_eva.sh"),
                        workflow.index("python3 tools/stage_mondrian_wlan_kmi.py"))
        contract = (ROOT / ".github/workflows/module-contract.yml").read_text()
        self.assertIn("tools/apply_qualcomm_patch_series.py --check", contract)


if __name__ == "__main__":
    unittest.main()
