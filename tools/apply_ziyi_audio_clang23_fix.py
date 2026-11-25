#!/usr/bin/env python3
"""Qualify selected Xiaomi Ziyi Audio and correct only two LLVM23 QoS prototypes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

REVISION = "8b1c8d3486a7ac3349d1422201a4436ad852fcb1"
PINS = {
    "Kbuild": "f67b0b7c9934b252600b22d960b3ccc44828fee3",
    "asoc/Kbuild": "80974f768f6ee05762301f5daa32d8345d53880a",
    "asoc/waipio.c": "208596042b00b136229d990f765782b2d630e278",
    "asoc/msm_common.c": "ece3ef53694b5141d3248d88f559ce11167257ec",
    "asoc/codecs/aw882xx/Kbuild": "74f22651d9866b2c0383535821faed841953a2cc",
    "asoc/codecs/aw882xx/src/aw882xx.c": "d431f27eb47612e628ade7731ad5f6b790d23725",
    "config/waipioauto.conf": "a8689b631dc4723d0a10d2853f50f3201ab916b7",
}
PROTOTYPES = (b"msm_audio_add_qos_request", b"msm_audio_remove_qos_request")


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def fix(text):
    original = text
    for name in PROTOTYPES:
        old = b"static void " + name + b"()\n"
        new = b"static void " + name + b"(void)\n"
        if text.count(old) != 1 or text.count(name + b"();") != 1 or new in text:
            raise ValueError("unqualified Qualcomm prototype in ziyi: " + name.decode())
        text = text.replace(old, new, 1)
    if original == text:
        raise ValueError("ziyi prototype patch made no change")
    return text


def qualify(source, evidence):
    if git(source, "rev-parse", "HEAD") != REVISION:
        raise ValueError("unexpected Xiaomi Ziyi source revision")
    if git(source, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Ziyi checkout has previously modified sources")
    for name, sha in PINS.items():
        if blob((source / name).read_bytes()) != sha:
            raise ValueError("Ziyi original Git blob mismatch: " + name)
    wide = (source / "asoc/waipio.c").read_text()
    if ("qcom,wcn-btfm" in wide or "qcom,cdc-dmic67-gpios" in wide or
            "qcom,wcn-bt" not in wide):
        raise ValueError("Ziyi WAIPIO routing unexpectedly differs")
    file = source / "asoc/msm_common.c"
    original = file.read_bytes()
    updated = fix(original)
    file.write_bytes(updated)
    if git(source, "diff", "--name-only") != "asoc/msm_common.c":
        raise ValueError("unreviewed Ziyi file changed")
    if git(source, "diff", "--numstat") != "2\t2\tasoc/msm_common.c":
        raise ValueError("Ziyi fix must change exactly 2 declarations")
    if git(source, "diff", "--check"):
        raise ValueError("Ziyi patch contains whitespace errors")
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps({
        "manufacturer_repo": "MiCode/vendor_qcom_opensource_audio-kernel",
        "ziyi_commit": REVISION, "original_files": PINS,
        "msm_common_patched_blob": blob(updated),
        "prototypes_fixed": [x.decode() for x in PROTOTYPES],
        "audio_source_selected_for_bsp_build": True,
        "audio_product_selected": False, "runtime_verified": False,
        "fm_product_feature_enabled": False,
    }, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--source", type=Path, required=True)
    cli.add_argument("--evidence", type=Path, required=True)
    a = cli.parse_args()
    qualify(a.source.resolve(), a.evidence)
    print("[PASS] Original Xiaomi Ziyi source pinned; only 2 QoS prototypes adjusted")
