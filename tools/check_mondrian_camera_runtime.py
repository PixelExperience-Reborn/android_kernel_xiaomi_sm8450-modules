#!/usr/bin/env python3
"""Parse device-collected read-only mondrian Camera evidence without HW claims."""
import argparse
import hashlib
import json
from pathlib import Path
import re

FILES = ("metadata.txt", "modules.txt", "video4linux.tsv",
         "i2c_devices.tsv", "regulator_names.tsv", "README.txt")
MODULES = ("camera", "wl2866d", "msm_drm", "msm_video", "msm_mmrm",
           "aw882xx_dlkm")


def read(root, name):
    path = root / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("missing/unsafe or oversized snapshot: " + name)
    return path.read_text("utf-8")


def pairs(data, sep):
    result = {}
    for line in data.splitlines():
        if sep not in line:
            raise ValueError("malformed snapshot line")
        key, value = line.split(sep, 1)
        if not key or not value or key in result:
            raise ValueError("duplicate or incomplete snapshot line")
        result[key] = value
    return result


def inspect(path):
    root = path.resolve(strict=True)
    data = {name: read(root, name) for name in FILES}
    meta = pairs(data["metadata.txt"], "=")
    if set(meta) != {"device", "vendor_device", "kernelrelease", "sdk", "read_only"}:
        raise ValueError("unexpected Camera snapshot metadata")
    if "mondrian" not in (meta["device"], meta["vendor_device"]) or meta["read_only"] != "1":
        raise ValueError("not a read-only mondrian snapshot")
    loaded = set()
    for line in data["modules.txt"].splitlines():
        fields = line.split()
        if len(fields) < 6 or not re.fullmatch(r"[A-Za-z0-9_.+-]+", fields[0]):
            raise ValueError("invalid /proc/modules record")
        if fields[0] in loaded:
            raise ValueError("duplicate /proc/modules name")
        loaded.add(fields[0])
    v4l = pairs(data["video4linux.tsv"], "\t")
    i2c = pairs(data["i2c_devices.tsv"], "\t")
    regulators = pairs(data["regulator_names.tsv"], "\t")
    return {
        "device": "mondrian", "android_sdk_observed": meta["sdk"],
        "kernelrelease_observed": meta["kernelrelease"],
        "kernel_5_10_81_detected": bool(re.match(
            r"^5\.10\.81(?:$|[-+])", meta["kernelrelease"])),
        "modules_observed_in_proc": {name: name in loaded for name in MODULES},
        "v4l2_subdevice_names": sorted(set(v4l.values())),
        "candidate_camera_i2c_names": sorted(set(
            value for value in i2c.values()
            if re.search(r"wl2866d|camera|cam[_-]|ois|actuator|eeprom", value, re.I))),
        "candidate_regulator_names": sorted(set(
            value for value in regulators.values()
            if re.search(r"camera|cam[_-]|wl2866d", value, re.I))),
        "capture_sha256": {key: hashlib.sha256(value.encode()).hexdigest()
                           for key, value in data.items()},
        "hardware_probe_verified": False,
        "camera_hal_verified": False,
        "ak7323_ois_verified": False,
        "power_cycle_verified": False,
        "production_approved": False,
        "status": "READ_ONLY_RUNTIME_ENUMERATION_NOT_HARDWARE_QUALIFIED",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    source = args.input.resolve(strict=True)
    output = args.out.resolve()
    if source == output or source in output.parents:
        parser.error("output must be outside captured input")
    try:
        report = inspect(source)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print("[PASS] snapshot parsed; Camera/OIS hardware remains unqualified")
