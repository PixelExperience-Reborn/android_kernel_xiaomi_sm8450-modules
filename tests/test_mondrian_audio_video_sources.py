"""Regression tests for source-pinned Audio/Video integration."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "media", ROOT / "tools/verify_mondrian_audio_video_sources.py")
media = importlib.util.module_from_spec(spec)
spec.loader.exec_module(media)


class MediaSourceTests(unittest.TestCase):
    def test_manufacturer_and_qualcomm_urls(self):
        original = (ROOT / ".gitmodules").read_text()
        media.validate_gitmodules(original)
        for path, (url, commit, blobs) in media.PINS.items():
            self.assertRegex(commit, "^[0-9a-f]{40}$")
            self.assertTrue(blobs)
            with self.assertRaises(ValueError):
                media.validate_gitmodules(original.replace(url, "https://invalid.example/source.git"))

    def test_mondrian_audio_source_is_xiaomi_ziyi_only(self):
        audio = media.PINS["upstream/xiaomi-audio"]
        self.assertEqual(audio[1], "8b1c8d3486a7ac3349d1422201a4436ad852fcb1")
        self.assertEqual(audio[2]["asoc/waipio.c"],
                         "208596042b00b136229d990f765782b2d630e278")
        self.assertEqual(audio[2]["asoc/msm_common.c"],
                         "ece3ef53694b5141d3248d88f559ce11167257ec")
        build = (ROOT / "tools/build_mondrian_audio_video.sh").read_text()
        self.assertIn("tools/apply_ziyi_audio_clang23_fix.py", build)
        self.assertNotIn("marble-s-oss", build)

    def test_real_build_and_staging_in_same_job(self):
        workflow = (ROOT / ".github/workflows/oem-coherent-wlan-compile.yml").read_text()
        builder = (ROOT / "tools/build_mondrian_audio_video.sh").read_text()
        self.assertLess(workflow.index("Build full OEM vmlinux"), workflow.index("bash tools/build_mondrian_audio_video.sh"))
        self.assertLess(workflow.index("bash tools/build_mondrian_audio_video.sh"), workflow.index("python3 tools/stage_mondrian_wlan_kmi.py"))
        self.assertIn('--external-root "$ko"', workflow)
        for selection in ("TARGET_PRODUCT=mondrian", "CONFIG_SND_SOC_WAIPIO=m", "CONFIG_MSM_VIDC_V4L2=m", "CONFIG_ARCH_DIWALI=n"):
            self.assertIn(selection, builder)
        self.assertIn('KBUILD_EXTRA_SYMBOLS="$mmrm_sym"', builder)
        self.assertNotIn("-Wno-error", builder)
        self.assertIn('"audio_hal_and_hardware_verified": False', workflow)
        self.assertIn('"production_boot_dtbo_and_modules_load_approved": False', workflow)


if __name__ == "__main__":
    unittest.main()
