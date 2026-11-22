"""Regression tests for the final, not requested, OEM ARM64 kernel .config."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "hardening", ROOT / "tools/verify_mondrian_kernel_hardening.py")
hardening = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hardening)


def config(values=None):
    given = dict(hardening.REQUIRED)
    given["CONFIG_ARM64"] = "y"
    given.update(values or {})
    return "\n".join(
        (f"{k}={v}" if v != "n" else f"# {k} is not set")
        for k, v in sorted(given.items())
    ) + "\n"


class KernelHardeningTests(unittest.TestCase):
    def test_expected_gki_modes_not_just_disabled_headers(self):
        result = hardening.verify(config())
        self.assertTrue(result["pass"])
        self.assertFalse(result["hardware_boot_verified"])

    def test_original_actual_oem_artifact_must_fail(self):
        # Actual c67ed74 artefact: generic.o with KASAN_GENERIC and LTO_NONE,
        # and both CFI + SCS absent. Capability detection was NOT the issue.
        opts = {
            "CONFIG_KASAN_GENERIC": "y",
            "CONFIG_KASAN_HW_TAGS": "n",
            "CONFIG_LTO_NONE": "y",
            "CONFIG_LTO_CLANG_FULL": "n",
            "CONFIG_CFI_CLANG": "n",
            "CONFIG_SHADOW_CALL_STACK": "n",
        }
        with self.assertRaisesRegex(ValueError, "GKI|mismatch"):
            hardening.verify(config(opts))

    def test_each_security_feature_is_a_hard_requirement(self):
        for name, val in hardening.REQUIRED.items():
            with self.subTest(config=name):
                opposite = "n" if val == "y" else "y"
                with self.assertRaises(ValueError):
                    hardening.verify(config({name: opposite}))

    def test_duplicate_metadata_or_wrong_architecture_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            hardening.verify(config() + "CONFIG_KASAN=y\n")
        with self.assertRaisesRegex(ValueError, "not an evaluated ARM64"):
            hardening.verify("CONFIG_KASAN=y\n")

    def test_all_compilation_jobs_verify_after_olddefconfig(self):
        for path in (
            ".github/workflows/oem-wlan-compile.yml",
            ".github/workflows/oem-coherent-wlan-compile.yml",
            ".github/workflows/xiaomi-camera-compile-abi.yml",
        ):
            with self.subTest(path=path):
                text = (ROOT / path).read_text()
                self.assertIn("tools/config/mondrian_gki_hardening.config", text)
                self.assertIn("python3 tools/verify_mondrian_kernel_hardening.py", text)
                self.assertLess(text.index("gki_defconfig"),
                                text.index("tools/config/mondrian_gki_hardening.config"))
                self.assertLess(text.index("olddefconfig"),
                                text.index("python3 tools/verify_mondrian_kernel_hardening.py"))


if __name__ == "__main__":
    unittest.main()
