#!/usr/bin/env python3
"""Verify immutable OEM Audio and Qualcomm VIDC inputs before build."""
import configparser
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    "upstream/xiaomi-audio": (
        "https://github.com/MiCode/vendor_qcom_opensource_audio-kernel.git",
        "8b1c8d3486a7ac3349d1422201a4436ad852fcb1",
        {
            "Kbuild": "f67b0b7c9934b252600b22d960b3ccc44828fee3",
            "asoc/Kbuild": "80974f768f6ee05762301f5daa32d8345d53880a",
            "asoc/waipio.c": "208596042b00b136229d990f765782b2d630e278",
            "asoc/msm_common.c": "ece3ef53694b5141d3248d88f559ce11167257ec",
            "asoc/codecs/aw882xx/Kbuild": "74f22651d9866b2c0383535821faed841953a2cc",
            "asoc/codecs/aw882xx/src/aw882xx.c": "d431f27eb47612e628ade7731ad5f6b790d23725",
            "config/waipioauto.conf": "a8689b631dc4723d0a10d2853f50f3201ab916b7",
        },
    ),
    "upstream/qualcomm/video": (
        "https://git.codelinaro.org/clo/la/platform/vendor/opensource/video-driver.git",
        "8608fb23bcb1cbffdc96b33eea3a79cb0228b72f",
        {
            "Kbuild": "b4ab16ddce97f2d4d0b44ce025397168bd2810b5",
            "config/waipio_video.conf": "227440fb21bf6ae5723daccb10c682ffb86030c9",
            "driver/vidc/inc/msm_vidc_dt.h": "d0e31aa49b2d66ccf3c6e542a6c31153007c66cd",
        },
    ),
}


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def validate_gitmodules(text):
    config = configparser.ConfigParser(interpolation=None)
    config.read_string(text)
    for path, (url, _, _) in PINS.items():
        section = 'submodule "' + path + '"'
        if section not in config or dict(config[section]) != {"path": path, "url": url}:
            raise ValueError("Audio/Video source URL or path drift: " + path)


def verify_checkout(root):
    validate_gitmodules((root / ".gitmodules").read_text())
    for path, (_, commit, blobs) in PINS.items():
        checkout = root / path
        if git(root, "ls-tree", "HEAD", path) != "160000 commit " + commit + "\t" + path:
            raise ValueError("Audio/Video gitlink drift: " + path)
        if git(checkout, "rev-parse", "HEAD") != commit:
            raise ValueError("Audio/Video checkout drift: " + path)
        if git(checkout, "status", "--porcelain", "--untracked-files=no"):
            raise ValueError("Unexpected tracked source changes: " + path)
        for name, sha in blobs.items():
            if git(checkout, "hash-object", "--no-filters", name) != sha:
                raise ValueError("Audio/Video original blob drift: " + path + "/" + name)
    audio = (root / "upstream/xiaomi-audio/asoc/waipio.c").read_text()
    if ("qcom,wcn-btfm" in audio or "qcom,cdc-dmic67-gpios" in audio or
            "qcom,wcn-bt" not in audio):
        raise ValueError("Selected Ziyi WAIPIO routing no longer matches mondrian")
    print("[PASS] Xiaomi Ziyi WAIPIO/AW882xx and Qualcomm VIDC exact source pins")


if __name__ == "__main__":
    verify_checkout(ROOT)
