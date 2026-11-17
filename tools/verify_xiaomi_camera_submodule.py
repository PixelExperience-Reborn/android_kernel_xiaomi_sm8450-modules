#!/usr/bin/env python3
"""Validate the real Xiaomi Camera source selected by the PE BSP Gitlink.

The MiCode driver is a pinned vendor source, not a LineageOS tree. This
verifier fails if a CI clone secretly switches Git revision, repository,
source tree, or even a checked-out tracked file before reviewed build-time
patches are applied. Hardware flash and sensor qualification is separate.
"""
import configparser
import json
from pathlib import Path
import subprocess
import sys

SUBMODULE = "xiaomi-camera-source"
URL = "https://github.com/MiCode/vendor_qcom_opensource_camera-kernel.git"
COMMIT = "9ed4ce96d49c0759c6365627113c5f59c2407942"
TREE = "e8fadfd2127cb9e12696273e1661ead9f9a70c89"
MANIFEST = "camera-bsp-candidate.json"


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True).strip()


def validate_gitmodules(text):
    config = configparser.ConfigParser(interpolation=None)
    config.read_string(text)
    name = 'submodule "' + SUBMODULE + '"'
    if name not in config:
        raise ValueError("missing original Xiaomi Camera submodule")
    section = config[name]
    if dict(section) != {"path": SUBMODULE, "url": URL}:
        raise ValueError("non-Xiaomi Camera submodule URL or checkout path")
    # This change must not rewire existing WLAN or Qualcomm MMRM inputs.
    for key, path, url in (
        ('submodule "upstream/xiaomi-wlan"', "upstream/xiaomi-wlan",
         "https://github.com/MiCode/vendor_qcom_opensource_wlan.git"),
        ('submodule "upstream/qualcomm/mmrm"', "upstream/qualcomm/mmrm",
         "https://git.codelinaro.org/clo/la/platform/vendor/opensource/mmrm-driver.git"),
    ):
        if key not in config or dict(config[key]) != {"path": path, "url": url}:
            raise ValueError("existing OEM WLAN/MMRM source selection changed")
    if len(config.sections()) != 3:
        raise ValueError("unexpected extra Git submodules in mondrian BSP")


def verify_pinned_metadata(candidate):
    manufacturer = candidate.get("manufacturer_candidate", {})
    if (candidate.get("device") != "mondrian" or
            candidate.get("soc") != "SM8475" or
            candidate.get("android_base") != "AOSP 17" or
            manufacturer.get("repository") !=
            "MiCode/vendor_qcom_opensource_camera-kernel" or
            manufacturer.get("reference_device") != "yudi" or
            manufacturer.get("commit") != COMMIT or
            manufacturer.get("tree_sha") != TREE or
            candidate.get("policy", {}).get("lineage_code_imported") is not False or
            candidate.get("policy", {}).get("fm_radio_selected") is not False):
        raise ValueError("Camera OEM selection drifts from pinned PE candidate")


def verify_gitlink_row(line):
    if line != "160000 commit " + COMMIT + "\t" + SUBMODULE:
        raise ValueError("Camera Gitlink SHA or path differs from Xiaomi pin")


def verify_checkout(root):
    validate_gitmodules((root / ".gitmodules").read_text())
    verify_pinned_metadata(json.loads((root / MANIFEST).read_text()))
    verify_gitlink_row(git(root, "ls-tree", "HEAD", SUBMODULE))
    camera = root / SUBMODULE
    if not camera.is_dir():
        raise ValueError("Xiaomi Camera Gitlink is not initialized")
    if git(camera, "rev-parse", "HEAD") != COMMIT:
        raise ValueError("Xiaomi Camera checkout commit drift")
    if git(camera, "rev-parse", "HEAD^{tree}") != TREE:
        raise ValueError("Xiaomi Camera source tree changed")
    if git(camera, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("reviewed Xiaomi Camera checkout has tracked edits")
    blobs = json.loads((root / MANIFEST).read_text())["manufacturer_candidate"][
        "file_blob_sha1"]
    for path, sha in blobs.items():
        if git(camera, "hash-object", path) != sha:
            raise ValueError("Xiaomi original Camera blob changed: " + path)
    return True


def main():
    try:
        verify_checkout(Path(__file__).resolve().parents[1])
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print("[FAIL] Pinned MiCode Camera submodule: " + str(exc),
              file=sys.stderr)
        raise SystemExit(1) from exc
    print("[PASS] Xiaomi Camera Gitlink URL, 40-hex SHA, tree and blobs pinned")
    print("[PENDING] Camera DTS/HAL, product load list and hardware tests")


if __name__ == "__main__":
    main()
