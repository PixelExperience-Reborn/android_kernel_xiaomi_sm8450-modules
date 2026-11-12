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

    def test_config_parser(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / ".config"
            p.write_text("CONFIG_ICNSS2=m\n# CONFIG_X is not set\nCONFIG_CNSS2=m\n")
            self.assertEqual(module.parse_config(p),
                             {"CONFIG_ICNSS2": "m", "CONFIG_CNSS2": "m"})


if __name__ == "__main__":
    unittest.main()
