#!/usr/bin/env python3
"""Canonical active PE-Reborn build pins; fail closed on inconsistent evidence metadata."""
import argparse
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def load_pins(root=ROOT):
    root = Path(root)
    read = lambda name: json.loads((root / name).read_text())
    cfg = read("modules-bsp-candidates.json")
    selected = cfg["selected_oem_source_candidates"]
    if (cfg["device"], cfg["soc"], cfg["android_base"]) != ("mondrian", "SM8475", "AOSP 17"):
        raise ValueError("Wrong product source lock")
    kernel, dt = selected["selected_kernel"], selected["selected_devicetrees"]
    for entry, repo in ((kernel, "android_kernel_xiaomi_sm8450"),
                        (dt, "android_kernel_xiaomi_sm8450-devicetrees")):
        if entry["repository"] != "PixelExperience-Reborn/" + repo or not re.fullmatch(
                r"[0-9a-f]{40}", entry["commit_sha"]):
            raise ValueError("Invalid active source pin: " + repo)
    if kernel["version"] != "5.10.81":
        raise ValueError("OEM kernel version drift")
    k, d = kernel["commit_sha"], dt["commit_sha"]
    camera = read("camera-bsp-candidate.json")["kernel"]
    policy = read("mondrian-camera-flash-policy.json")
    if (camera != {"repository": kernel["repository"], "version": kernel["version"], "commit": k}
            or policy["selected_kernel_commit"] != k
            or policy["xiaomi_device_tree"]["commit"] != d
            or policy["xiaomi_device_tree"]["repository"] != dt["repository"]
            or cfg["wlan_runtime_closure"]["kernel_commit"] != k):
        raise ValueError("Active pin and reviewed diagnostic evidence disagree; update evidence explicitly")
    return {"kernel": k, "devicetrees": d}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("check", "kernel", "devicetrees", "github"))
    a = p.parse_args()
    pins = load_pins()
    if a.mode == "github":
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            for key, value in pins.items():
                print(f"{key}={value}", file=f)
        with open(os.environ["GITHUB_ENV"], "a") as f:
            print("PE_KERNEL_SHA=" + pins["kernel"], file=f)
            print("PE_DT_SHA=" + pins["devicetrees"], file=f)
    elif a.mode == "check":
        print(json.dumps(pins, sort_keys=True))
    else:
        print(pins[a.mode])


if __name__ == "__main__":
    main()
