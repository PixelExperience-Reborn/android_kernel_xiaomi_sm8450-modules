"""Static and pure-function regression checks for OEM module closure."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "stage_oem", ROOT / "tools/stage_mondrian_wlan_kmi.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ModuleStagingTests(unittest.TestCase):
    def test_exact_oem_mondrian_dependency_symbols(self):
        self.assertEqual(
            module.ROOT_WLAN_DEPS,
            frozenset(("icnss2", "mi_cnss_statistic", "cfg80211",
                       "cnss_prealloc", "cnss_nl", "cnss_utils"))
        )
        self.assertEqual(len(module.REQUIRED_CONFIG), 6)

    def test_recursive_dependency_topological_order(self):
        files = {"wlan": Path("wlan.ko"), "cfg80211": Path("cfg80211.ko"),
                 "icnss2": Path("icnss2.ko")}
        fake = {"wlan.ko": ["cfg80211", "icnss2"],
                "cfg80211.ko": [], "icnss2.ko": ["cfg80211"]}
        with patch.object(module, "dependencies", side_effect=lambda p: fake[p.name]):
            self.assertEqual(module.compute_closure(["wlan"], files),
                             ["cfg80211", "icnss2", "wlan"])

    def test_missing_dependency_fails_closed(self):
        with patch.object(module, "dependencies", return_value=["cnss_nl"]):
            with self.assertRaisesRegex(RuntimeError, "missing: cnss_nl"):
                module.compute_closure(["wlan"], {"wlan": Path("wlan.ko")})

    def test_module_cycle_fails_closed(self):
        with patch.object(module, "dependencies",
                          side_effect=lambda p: ["b"] if p.name == "a.ko" else ["a"]):
            with self.assertRaisesRegex(RuntimeError, "cycle"):
                module.compute_closure(["a"], {"a": Path("a.ko"), "b": Path("b.ko")})

    def test_modprobe_union_of_two_independent_roots(self):
        # Modprobe of WLAN cannot be expected to load MMRM and its
        # otherwise unrelated transitive dependencies.
        wlan = ["insmod /tmp/kernel/cfg80211.ko",
                "insmod /tmp/extra/qca_cld3_qca6490.ko"]
        mmrm = ["insmod /tmp/kernel/qcom_clock.ko",
                "insmod /tmp/extra/msm-mmrm.ko"]
        expected = {"cfg80211.ko", "qca_cld3_qca6490.ko",
                    "qcom_clock.ko", "msm-mmrm.ko"}
        actual = module.insmod_basenames(wlan) | module.insmod_basenames(mmrm)
        self.assertEqual(actual, expected)
        self.assertNotEqual(module.insmod_basenames(wlan), expected)

    def test_modprobe_trailing_whitespace_is_not_part_of_filename(self):
        # Real modprobe --show-depends output from CI appends spaces
        # after OEM .ko paths. Names must match staged file basenames.
        rows = [
            "insmod /tmp/kernel/cfg80211.ko ",
            "insmod   /tmp/kernel/icnss2.ko  ",
            "insmod /tmp/extra/qca_cld3_qca6490.ko  ",
            "install /usr/bin/ignored",
        ]
        self.assertEqual(
            module.insmod_basenames(rows),
            {"cfg80211.ko", "icnss2.ko", "qca_cld3_qca6490.ko"},
        )

    def test_staging_explicit_kernel_pin_is_exact(self):
        oem = module.KERNEL_SHA
        merged = "69c3911404debdfab1eb484aaa626b319b9d93d7"
        with patch.object(module, "command", return_value=merged):
            self.assertEqual(
                module.verify_kernel_revision(Path("/fake/kernel"), merged), merged)
            with self.assertRaisesRegex(ValueError, "Kernel revision drift"):
                module.verify_kernel_revision(Path("/fake/kernel"), oem)
            for invalid in ("HEAD", "", "g" * 40, "a" * 39):
                with self.subTest(ref=invalid):
                    with self.assertRaisesRegex(ValueError, "40-hex"):
                        module.verify_kernel_revision(Path("/fake/kernel"), invalid)

    def test_three_independent_wlan_mmrm_display_roots(self):
        files = {name: Path(name + ".ko") for name in
                 ("qca_cld3_qca6490", "msm_mmrm", "msm_drm",
                  "cfg80211", "qcom_display_notifier")}
        graph = {
            "qca_cld3_qca6490": ["cfg80211"],
            "msm_mmrm": [],
            "msm_drm": ["msm_mmrm", "qcom_display_notifier"],
            "cfg80211": [],
            "qcom_display_notifier": [],
        }
        with patch.object(module, "dependencies",
                          side_effect=lambda p: graph[p.stem]):
            order = module.compute_closure(
                ("msm_mmrm", "qca_cld3_qca6490", "msm_drm"), files)
        self.assertEqual(set(order), set(files))
        self.assertLess(order.index("msm_mmrm"), order.index("msm_drm"))
        self.assertLess(order.index("cfg80211"), order.index("qca_cld3_qca6490"))
        self.assertLess(order.index("qcom_display_notifier"), order.index("msm_drm"))

    def test_display_missing_dependency_must_fail_not_fake_stub(self):
        files = {"msm_drm": Path("msm_drm.ko")}
        with patch.object(module, "dependencies", return_value=["msm_mmrm"]):
            with self.assertRaisesRegex(RuntimeError, "missing: msm_mmrm"):
                module.compute_closure(("msm_drm",), files)

    def test_stage_refuses_to_delete_existing_diagnostic_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            kernel = root / "kernel"
            kernel.mkdir()
            stage = root / "stage"
            stage.mkdir()
            sentinel = stage / "valuable-evidence.json"
            sentinel.write_text("do not erase")
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                module.checked_stage_directory(stage, (kernel,))
            self.assertEqual(sentinel.read_text(), "do not erase")

    def test_stage_refuses_destination_inside_oem_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            kernel = root / "kernel"
            kernel.mkdir()
            with self.assertRaisesRegex(ValueError, "overlaps"):
                module.checked_stage_directory(kernel / "new-stage", (kernel,))

    def test_stage_rejects_existing_symlink_alias(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "kernel"
            source.mkdir()
            alias = root / "alias"
            alias.symlink_to(source, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                module.checked_stage_directory(alias, (source,))
            self.assertTrue(source.is_dir())

    def test_stage_accepts_fresh_disjoint_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            kernel = root / "kernel"
            kernel.mkdir()
            kernel_out = root / "kernel-out"
            kernel_out.mkdir()
            stage = root / "stage"
            self.assertEqual(
                module.checked_stage_directory(stage, (kernel, kernel_out)),
                stage,
            )
            self.assertFalse(stage.exists())

    def test_extra_oem_root_checked_by_compiled_filename(self):
        compiled = {
            "goodix_core.ko": Path("goodix_core.ko"),
            "dispcc-waipio.ko": Path("dispcc-waipio.ko"),
        }
        with patch.object(module, "module_name",
                          side_effect=lambda path: path.stem.replace("-", "_")):
            roots = module.verify_oem_diagnostic_roots(
                ["goodix_core.ko", "dispcc-waipio.ko"], compiled, {"msm_drm"})
            self.assertEqual(roots, ("goodix_core", "dispcc_waipio"))

    def test_extra_oem_root_missing_or_unsafe_fails_closed(self):
        with patch.object(module, "module_name", return_value="goodix_core"):
            for invalid in ("../goodix_core.ko", "/tmp/module.ko",
                            "goodix_core.o", "unknown.ko"):
                with self.subTest(value=invalid):
                    with self.assertRaises(ValueError):
                        module.verify_oem_diagnostic_roots(
                            [invalid], {"goodix_core.ko": Path("goodix_core.ko")}, set())

    def test_extra_oem_root_collision_or_duplicate_fails_closed(self):
        compiled = {"goodix_core.ko": Path("goodix_core.ko")}
        with patch.object(module, "module_name", return_value="goodix_core"):
            with self.assertRaisesRegex(ValueError, "colliding"):
                module.verify_oem_diagnostic_roots(
                    ["goodix_core.ko"], compiled, {"goodix_core"})
            with self.assertRaisesRegex(ValueError, "colliding"):
                module.verify_oem_diagnostic_roots(
                    ["goodix_core.ko", "goodix_core.ko"], compiled, set())

    def test_oem_roots_are_diagnostic_not_a_shipping_load_list(self):
        with patch.object(module, "dependencies", return_value=[]):
            files = {"goodix_core": Path("goodix_core.ko"),
                     "msm_drm": Path("msm_drm.ko")}
            self.assertEqual(
                module.compute_closure(("msm_drm", "goodix_core"), files),
                ["msm_drm", "goodix_core"],
            )

    def test_config_parser(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / ".config"
            p.write_text("CONFIG_ICNSS2=m\n# CONFIG_X is not set\nCONFIG_CNSS2=m\n")
            self.assertEqual(module.parse_config(p),
                             {"CONFIG_ICNSS2": "m", "CONFIG_CNSS2": "m"})


if __name__ == "__main__":
    unittest.main()
