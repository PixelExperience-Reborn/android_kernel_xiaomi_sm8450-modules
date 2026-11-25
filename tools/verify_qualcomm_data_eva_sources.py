#!/usr/bin/env python3
"""Verify the pinned Qualcomm WAIPIO 11900 data and EVA sources before build.

Checks the .gitmodules URL, the committed gitlink, the checked-out commit and
original Git blob IDs of the build-defining files, so that a silent upstream
or local change cannot reach the coherent kernel build.
"""
import configparser
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "qualcomm-mondrian-waipio-11900-candidates.json"
CLO = "https://git.codelinaro.org/clo/la/"
URLS = {
    "dataipa": CLO + "platform/vendor/opensource/dataipa.git",
    "datarmnet": CLO + "platform/vendor/qcom/opensource/datarmnet.git",
    "datarmnet-ext": CLO + "platform/vendor/qcom/opensource/datarmnet-ext.git",
    "eva-kernel": CLO + "platform/vendor/opensource/eva-kernel.git",
}
BLOBS = {
    "dataipa": {
        "drivers/platform/msm/Kbuild": "7814f8298a90e1b585a4e6ff6a4ea3c1c50452b2",
        "config/dataipa_vendor.h": "ef6bfe02a6592e1cd2aae0151c78c4a50398bb4b",
        "config/dataipa_GKI.conf": "516dcf224baceadd2ef1d2f3836b7b8f1c1fe783",
    },
    "datarmnet": {
        "core/Kbuild": "e041a738c4379d5001dc1a35e6b87eb71f3514ee",
    },
    "datarmnet-ext": {
        "shs/Kbuild": "fc420cb476ecc76b21ba5613f25fb266f01c483e",
    },
    "eva-kernel": {
        "Kbuild": "b7d758983695f40347c18c4ccb365ffeb4f9b6b1",
        "msm/Kbuild": "ad7c7555201bedf5588766a6cef5a3d174d49ab7",
    },
}


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def verify(root=ROOT, require_checkout=True):
    lock = json.loads((root / LOCK.name).read_text())
    config = configparser.ConfigParser(interpolation=None)
    config.read_string((root / ".gitmodules").read_text())
    for project, url in URLS.items():
        selection = lock["selection"][project]
        if not selection["selected"]:
            raise ValueError("Qualcomm project not selected: " + project)
        path = selection["gitlink"]
        commit = lock["projects"][project]["commit"]
        section = 'submodule "' + path + '"'
        if section not in config or dict(config[section]) != {"path": path, "url": url}:
            raise ValueError("Qualcomm source URL or path drift: " + path)
        if git(root, "ls-tree", "HEAD", path) != "160000 commit " + commit + "\t" + path:
            raise ValueError("Qualcomm gitlink drift: " + path)
        if not require_checkout:
            continue
        checkout = root / path
        if git(checkout, "rev-parse", "HEAD") != commit:
            raise ValueError("Qualcomm checkout drift: " + path)
        if git(checkout, "status", "--porcelain", "--untracked-files=no"):
            raise ValueError("Unexpected tracked source changes: " + path)
        for name, blob in BLOBS[project].items():
            if git(checkout, "hash-object", "--no-filters", name) != blob:
                raise ValueError("Qualcomm original blob drift: " + path + "/" + name)
    if lock["selection"]["cvp-kernel"]["selected"]:
        raise ValueError("cvp-kernel must not be selected alongside eva-kernel")
    print("[PASS] Qualcomm WAIPIO 11900 IPA/GSI, RMNET core+ext and EVA exact source pins")


if __name__ == "__main__":
    verify()
