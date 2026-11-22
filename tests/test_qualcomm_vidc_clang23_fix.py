"""Fail-closed checks for exact Qualcomm VIDC declaration fixes."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "vidc_fix", ROOT / "tools/apply_qualcomm_vidc_clang23_fix.py")
fix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fix)


class VideoDeclarationTests(unittest.TestCase):
    def test_all_18_declarations(self):
        self.assertEqual(len(fix.PATCHES), 5)
        self.assertEqual(sum(len(pairs) for _, pairs in fix.PATCHES.values()), 18)
        for path, (blob, pairs) in fix.PATCHES.items():
            self.assertRegex(blob, "^[0-9a-f]{40}$")
            for old, new in pairs:
                with self.subTest(path=path, declaration=old):
                    suffix = b"" if old.endswith(b"\n") else b"void)\n"
                    source = old + suffix + b"{\n\treturn -22;\n}\n"
                    updated = fix.corrected(source, ((old, new),))
                    self.assertEqual(updated, new + suffix + b"{\n\treturn -22;\n}\n")
                    for invalid in (source + source, updated, b"/* unrelated */\n"):
                        with self.assertRaises(ValueError):
                            fix.corrected(invalid, ((old, new),))

    def test_mmrm_descriptor_initialized_without_changing_registration(self):
        path = "driver/vidc/src/venus_hfi.c"
        blob, pairs = fix.PATCHES[path]
        self.assertEqual(blob, "0b167473b05195e8e8a35b0bb5a0fd3dec84d331")
        self.assertEqual(pairs, ((
            b"\t\tstruct mmrm_client_desc desc;\n",
            b"\t\tstruct mmrm_client_desc desc = { 0 };\n",
        ),))
        source = (
            b"static int register_client(void)\n{\n"
            b"\t\tstruct mmrm_client_desc desc;\n"
            b"\t\tchar *name = (char *)desc.client_info.desc.name;\n"
            b"\t\tdesc.client_type = MMRM_CLIENT_CLOCK;\n"
            b"\t\tstrlcpy(name, cl->name, sizeof(desc.client_info.desc.name));\n"
            b"\t\treturn mmrm_client_register(&desc) ? 0 : -EINVAL;\n}\n"
        )
        expected = source.replace(*pairs[0])
        self.assertEqual(fix.corrected(source, pairs), expected)
        self.assertIn(b"strlcpy(name, cl->name, sizeof(desc.client_info.desc.name));", expected)
        self.assertIn(b"mmrm_client_register(&desc)", expected)
        with self.assertRaises(ValueError):
            fix.corrected(expected, pairs)

    def test_applied_after_pins_before_compilation(self):
        build = (ROOT / "tools/build_mondrian_audio_video.sh").read_text()
        self.assertLess(build.index("python3 tools/verify_mondrian_audio_video_sources.py"),
                        build.index("python3 tools/apply_qualcomm_vidc_clang23_fix.py"))
        self.assertLess(build.index("python3 tools/apply_qualcomm_vidc_clang23_fix.py"),
                        build.index('M="$video"'))
        self.assertNotIn("-Wno-error", build)


if __name__ == "__main__":
    unittest.main()
