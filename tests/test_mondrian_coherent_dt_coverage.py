"""The coherent build applies the Qualcomm audio/video DT and gates DT driver coverage."""
import configparser
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github/workflows/oem-coherent-wlan-compile.yml").read_text()
DT_COMMIT = "c6f47f9b8f9b7129d98b30e36beae8445fd2faa5"


class CoherentDeviceTreeStage(unittest.TestCase):
    def test_devicetree_pin_is_consistent(self):
        cfg = json.loads((ROOT / "modules-bsp-candidates.json").read_text())
        policy = json.loads((ROOT / "mondrian-camera-flash-policy.json").read_text())
        self.assertEqual(cfg["selected_oem_source_candidates"]["selected_devicetrees"]["commit_sha"], DT_COMMIT)
        self.assertEqual(policy["xiaomi_device_tree"]["commit"], DT_COMMIT)

    def test_qualcomm_dt_gitlinks_are_checked(self):
        self.assertIn("audio-devicetree rev-parse HEAD)\" = 50ccb9f0fb8c6a138a0946e81ae5beb700264fd1", WORKFLOW)
        self.assertIn("video-devicetree rev-parse HEAD)\" = 7c85d65ec51887baa2886c5a9df8223d0b0cb01b", WORKFLOW)

    def test_order_m11a_multimedia_coverage_evidence(self):
        order = ["device-tree/tools/build_mondrian_m11a.py",
                 "device-tree/tools/build_mondrian_multimedia.py",
                 "device-tree/tools/verify_dt_driver_coverage.py",
                 '"$RUNNER_TEMP/mondrian-three-repo-diagnostic-evidence.json" <<\'PY\'']
        positions = [WORKFLOW.index(item) for item in order]
        self.assertEqual(positions, sorted(positions))
        # The coverage gate runs after every external module was built.
        self.assertLess(WORKFLOW.index("bash tools/build_mondrian_data_eva.sh"), positions[2])
        self.assertIn('assert coverage["failures"] == []', WORKFLOW)

    def test_coverage_uses_generated_config_and_every_driver_source(self):
        step = WORKFLOW[WORKFLOW.index("device-tree/tools/verify_dt_driver_coverage.py"):]
        step = step[:step.index("--out ")]
        self.assertIn('--kernel-config "$RUNNER_TEMP/mondrian-out/.config"', step)
        sources = dict(re.findall(r"--module-source ([\w-]+)=(\S+)", step))
        self.assertEqual(sources.pop("display"), "kernel/techpack/display")
        modules = configparser.ConfigParser()
        modules.read(ROOT / ".gitmodules")
        gitlinks = {modules[s]["path"] for s in modules.sections()}
        self.assertEqual(set(sources.values()), gitlinks)
        for base in ("cape", "cape-v2", "capep"):
            self.assertIn(f'--dtb "$RUNNER_TEMP/mondrian-coherent-multimedia/{base}-mondrian-full.dtb"', step)


if __name__ == "__main__":
    unittest.main()
