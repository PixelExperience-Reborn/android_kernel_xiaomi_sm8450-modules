"""Verify one active source lock, reject stale qualification metadata."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from mondrian_source_pins import load_pins


class ActiveSourcePinsTests(unittest.TestCase):
    def test_active_pins_match_all_checked_in_contracts(self):
        pins = load_pins()
        self.assertEqual(len(pins["kernel"]), 40)
        self.assertEqual(len(pins["devicetrees"]), 40)
        for path in (ROOT / ".github/workflows").glob("*.yml"):
            text = path.read_text()
            for pin in pins.values():
                self.assertNotIn(pin, text, str(path))
        self.assertNotEqual(pins["kernel"], "2466406b9beac724960b0c88e6e794421d0466e7")

    def test_drift_is_rejected_instead_of_silently_relabeling_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("modules-bsp-candidates.json", "camera-bsp-candidate.json",
                         "mondrian-camera-flash-policy.json"):
                shutil.copyfile(ROOT / name, root / name)
            load_pins(root)
            path = root / "modules-bsp-candidates.json"
            config = json.loads(path.read_text())
            config["selected_oem_source_candidates"]["selected_kernel"]["commit_sha"] = "1" * 40
            path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, "disagree"):
                load_pins(root)
