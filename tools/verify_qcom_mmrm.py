#!/usr/bin/env python3
"""Check pinned original Qualcomm MMRM source, not its compiled ABI."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def main():
    data = json.loads((ROOT / "modules-bsp-candidates.json").read_text())
    pin = data["qualcomm_official_candidates"]["mmrm"]
    source = ROOT / "upstream/qualcomm/mmrm"
    actual = subprocess.check_output(["git", "-C", str(source),
                                      "rev-parse", "HEAD"], text=True).strip()
    if actual != pin["commit_sha"]:
        raise RuntimeError(f"Qualcomm MMRM commit drift: {actual}")
    for path in ("Kbuild", "driver/Kbuild", "driver/src/msm_mmrm.c",
                 "config/waipiommrmconf.h"):
        if not (source / path).is_file():
            raise RuntimeError(f"Missing official Qualcomm MMRM source: {path}")
    # An isolated driver build must include Qualcomm's MMRM config header
    # and set CONFIG_MSM_MMRM, because the original root Kbuild is bypassed.
    driver = (source / "driver/Kbuild").read_text()
    conf = (source / "config/waipiommrmconf.h").read_text()
    if "ifdef CONFIG_MSM_MMRM" not in driver or "obj-m += msm-mmrm.o" not in driver:
        raise RuntimeError("Unsupported production MMRM Kbuild: driver target missing")
    if "#define CONFIG_MSM_MMRM 1" not in conf:
        raise RuntimeError("Unsupported MMRM feature configuration")
    print("[PASS] Qualcomm CodeLinaro MMRM source pinned to VIDEO.LA.2.0 Waipio")
    print("[PENDING] MMRM .ko, KMI, display/camera/video and boot")

if __name__ == "__main__":
    main()
