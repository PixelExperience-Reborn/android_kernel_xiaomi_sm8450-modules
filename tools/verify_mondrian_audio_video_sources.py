#!/usr/bin/env python3
"""Verify immutable OEM Audio and Qualcomm VIDC inputs before build."""
import configparser
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    "upstream/xiaomi-audio": (
        "https://github.com/MiCode/vendor_qcom_opensource_audio-kernel.git",
        "7d174adfe5304b74889e0cf0e16132a049707710",
        {
            "Kbuild": "f67b0b7c9934b252600b22d960b3ccc44828fee3",
            "asoc/Kbuild": "69e3e7f123cbf2e369bdc9300df5bcbc8f967d6f",
            "asoc/codecs/aw882xx/Kbuild": "74f22651d9866b2c0383535821faed841953a2cc",
            "asoc/codecs/aw882xx/src/aw882xx.c": "52c8501343681552874eb6a5430fdd1a94dab8fd",
            "config/waipioauto.conf": "a8689b631dc4723d0a10d2853f50f3201ab916b7",
        },
    ),
    "upstream/qualcomm/video": (
        "https://git.codelinaro.org/clo/la/platform/vendor/opensource/video-driver.git",
        "707fcdb08626667663d13cfceeb2d9dfe92893e3",
        {
            "Kbuild": "c7538fa337f94d89969eefa72f5f5efa35296fb5",
            "config/waipio_video.conf": "227440fb21bf6ae5723daccb10c682ffb86030c9",
            "driver/vidc/inc/msm_vidc_dt.h": "6e05636eec0f248f6b481b483ba5d44e21c68328",
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
    print("[PASS] Xiaomi Audio and Qualcomm VIDC exact source pins")


if __name__ == "__main__":
    verify_checkout(ROOT)
