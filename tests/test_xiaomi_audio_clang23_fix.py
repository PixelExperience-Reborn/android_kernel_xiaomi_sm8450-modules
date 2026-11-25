"""Regression tests for the exact OEM Audio QoS prototype correction."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "audio_fix", ROOT / "tools/apply_ziyi_audio_clang23_fix.py")
fix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fix)

SOURCE = (
    b"static void msm_audio_add_qos_request()\n{\n\tadd_qos();\n}\n"
    b"static void msm_audio_remove_qos_request()\n{\n\tremove_qos();\n}\n"
    b"void init(void) { msm_audio_add_qos_request(); }\n"
    b"void exit(void) { msm_audio_remove_qos_request(); }\n"
)


class AudioPrototypeTests(unittest.TestCase):
    def test_only_two_definitions_changed(self):
        expected = SOURCE.replace(b"request()\n", b"request(void)\n")
        self.assertEqual(fix.fix(SOURCE), expected)
        self.assertIn(b"msm_audio_add_qos_request();", expected)
        self.assertIn(b"msm_audio_remove_qos_request();", expected)

    def test_unexpected_source_rejected(self):
        for invalid in (
            SOURCE.replace(b"static void msm_audio_add_qos_request()", b"static void msm_audio_add_qos_request(int arg)"),
            SOURCE.replace(b"msm_audio_remove_qos_request();", b"msm_audio_remove_qos_request(1);"),
            SOURCE + b"static void msm_audio_add_qos_request()\n",
            fix.fix(SOURCE),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                fix.fix(invalid)

    def test_independent_compilation_does_not_bypass_failure(self):
        build = (ROOT / "tools/build_mondrian_audio_video.sh").read_text()
        self.assertIn("apply_ziyi_audio_clang23_fix.py", build)
        self.assertIn('if (( audio_status != 0 || video_status != 0 )); then', build)
        self.assertIn("exit 1", build)
        self.assertLess(build.index("video_status=$?"), build.index("for name in machine_dlkm"))
        self.assertLess(build.index("python3 tools/verify_mondrian_audio_video_sources.py"),
                        build.index("python3 tools/apply_ziyi_audio_clang23_fix.py"))
        self.assertNotIn("-Wno-error", build)


if __name__ == "__main__":
    unittest.main()
