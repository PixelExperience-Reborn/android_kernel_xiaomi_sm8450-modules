"""Source-only tests: vendor-origin Ziyi candidate must not replace Marble."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "ziyi", ROOT / "tools/apply_ziyi_audio_clang23_fix.py")
z = importlib.util.module_from_spec(spec)
spec.loader.exec_module(z)

class ZiyiAudioCandidateTests(unittest.TestCase):
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

    def test_candidate_separate_from_selected_marble_and_no_fm(self):
        s = (ROOT / "tools/qualify_ziyi_audio_candidate.sh").read_text()
        self.assertIn("git clone --quiet --depth 1", s)
        self.assertIn(z.REVISION.replace(z.REVISION, "expected=8b1c8d3486a7ac3349d1422201a4436ad852fcb1"), s)
        self.assertIn("--expected-kernel-commit c67ed74", s)
        self.assertIn("ziyi-audio-abi", s)
        self.assertNotIn("upstream/xiaomi-audio/", s)
        self.assertNotIn("radio", s.lower())
        wf = (ROOT / ".github/workflows/oem-coherent-wlan-compile.yml").read_text()
        self.assertIn("bash tools/qualify_ziyi_audio_candidate.sh", wf)
        main = (ROOT / "tools/verify_mondrian_audio_video_sources.py").read_text()
        self.assertIn("7d174adfe5304b74889e0cf0e16132a049707710", main)

if __name__ == "__main__":
    unittest.main()
