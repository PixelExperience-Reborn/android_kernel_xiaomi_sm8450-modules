#!/usr/bin/env python3
"""Validate the chosen Xiaomi WLAN source and kernel pin; no .ko PASS implied."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def main():
    record = json.loads((ROOT / "modules-bsp-candidates.json").read_text())
    pin = record["selected_oem_source_candidates"]
    wlan = ROOT / "upstream/xiaomi-wlan"
    actual = subprocess.check_output(
        ["git", "-C", str(wlan), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual != pin["wlan"]["commit_sha"]:
        raise RuntimeError(f"Unpinned Xiaomi WLAN source: {actual}")
    paths = [wlan / path for path in (
        "qcacld-3.0/Kbuild", "qcacld-3.0/Makefile",
        "qcacld-3.0/configs/qca6490_defconfig",
        "qca-wifi-host-cmn/VERSION.txt",
        "fw-api/fw", "fw-api/hw")]
    for path in paths:
        if not path.exists():
            raise RuntimeError(f"Missing Qualcomm WLAN component: {path}")
    if (wlan / "qcacld-3.0/cmn").resolve() != (wlan / "qca-wifi-host-cmn").resolve():
        raise RuntimeError("QCACLD common headers symlink does not resolve")
    if (wlan / "qcacld-3.0/.qca6490").resolve() != (wlan / "qcacld-3.0").resolve():
        raise RuntimeError("QCACLD qca6490 build symlink does not resolve")
    print("[PASS] Xiaomi mondrian WLAN sources pinned; Kbuild and API paths resolved")
    print("[PENDING] Compiled external module, symbol CRCs, firmware and hardware")

if __name__ == "__main__":
    main()
