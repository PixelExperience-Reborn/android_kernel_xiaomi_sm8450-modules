"""Original Xiaomi Ziyi is the sole selected mondrian Audio source."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "ziyi", ROOT / "tools/apply_ziyi_audio_clang23_fix.py")
z = importlib.util.module_from_spec(spec)
spec.loader.exec_module(z)

class ZiyiAudioSelectionTests(unittest.TestCase):
    def test_known_micode_revision_and_hardware_source_blobs(self):
        self.assertEqual(z.REVISION, "8b1c8d3486a7ac3349d1422201a4436ad852fcb1")
        self.assertEqual(z.PINS["asoc/msm_common.c"],
                         "ece3ef53694b5141d3248d88f559ce11167257ec")
        self.assertEqual(z.PINS["asoc/codecs/aw882xx/Kbuild"],
                         "74f22651d9866b2c0383535821faed841953a2cc")
        self.assertEqual(len(z.PINS), 7)

    def test_only_two_prototypes_changed_without_touching_callers(self):
        original = b"static void msm_audio_add_qos_request()\n" + (
            b"static void msm_audio_remove_qos_request()\n"
            b"msm_audio_add_qos_request();\n"
            b"msm_audio_remove_qos_request();\n"
        )
        changed = z.fix(original)
        self.assertEqual(changed.count(b"(void)\n"), 2)
        self.assertIn(b"msm_audio_remove_qos_request();\n", changed)
        with self.assertRaises(ValueError):
            z.fix(changed)

    def test_selected_audio_is_the_only_audio_build_source(self):
        builder = (ROOT / "tools/build_mondrian_audio_video.sh").read_text()
        workflow = (ROOT / ".github/workflows/oem-coherent-wlan-compile.yml").read_text()
        verifier = (ROOT / "tools/verify_mondrian_audio_video_sources.py").read_text()
        self.assertIn("python3 tools/apply_ziyi_audio_clang23_fix.py", builder)
        self.assertIn('audio="$GITHUB_WORKSPACE/upstream/xiaomi-audio"', builder)
        self.assertIn("bash tools/build_mondrian_audio_video.sh", workflow)
        self.assertNotIn("qualify_ziyi_audio_candidate", workflow)
        self.assertNotIn("apply_xiaomi_audio_clang23_fix", workflow)
        self.assertIn('"qcom,wcn-btfm" in audio', verifier)
        self.assertIn('"qcom,cdc-dmic67-gpios" in audio', verifier)
        self.assertNotIn("marble-s-oss", builder + workflow + verifier)
        self.assertIn('"audio_hal_and_hardware_verified": False', workflow)


if __name__ == "__main__":
    unittest.main()
