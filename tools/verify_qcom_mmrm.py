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
    for path in ("Kbuild", "driver/Kbuild", "driver/src/msm_mmrm.c"):
        if not (source / path).is_file():
            raise RuntimeError(f"Missing official Qualcomm MMRM source: {path}")
    print("[PASS] Qualcomm CodeLinaro MMRM source pinned to VIDEO.LA.2.0 Waipio")
    print("[PENDING] MMRM .ko, KMI, display/camera/video and boot")

if __name__ == "__main__":
    main()
