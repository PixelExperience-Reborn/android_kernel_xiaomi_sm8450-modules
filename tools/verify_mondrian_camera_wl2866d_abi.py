#!/usr/bin/env python3
"""Prove the actual OEM Xiaomi Camera -> WL2866D power module ABI.

Camera must depend on the exact separately built Xiaomi WL2866D .ko. A
standalone successful build or a separately staged regulator root is NOT
enough: modprobe camera must load WL2866D before camera. Diagnostic only;
does not infer any sensor wiring or authorize product modules.load.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

POWER_SYMBOLS = ("wl2866d_camera_power_up", "wl2866d_camera_power_down")


def nm_symbols(output):
    result = {}
    for row in output.splitlines():
        fields = row.split()
        if len(fields) >= 2 and len(fields[1]) == 1:
            result.setdefault(fields[0], set()).add(fields[1])
    if not result:
        raise ValueError("missing ELF symbol records")
    return result


def check_contract(config, camera_symbols, ldo_symbols, depends, manifest):
    if config.get("CONFIG_WL2866D") != "y":
        raise ValueError("Camera WL2866D call path is not enabled in OEM config")
    if config.get("CONFIG_LDO_WL2866D") != "m":
        raise ValueError("Xiaomi WL2866D provider was not built as a module")
    for sym in POWER_SYMBOLS:
        if "U" not in camera_symbols.get(sym, set()):
            raise ValueError("camera.ko does not import OEM power symbol " + sym)
        if not ldo_symbols.get(sym, set()) & {"T", "W"}:
            raise ValueError("wl2866d.ko does not export OEM power symbol " + sym)
    if "wl2866d" not in {x.strip() for x in depends.split(",") if x.strip()}:
        raise ValueError("camera.ko modinfo does not depend on wl2866d")

    if not manifest.get("camera_modules_included"):
        raise ValueError("Camera module not in the staged diagnostic closure")
    if manifest.get("production_boot_load_order_qualified") is not False:
        raise ValueError("diagnostic manifest illegally claims production readiness")
    names = manifest.get("module_files", {})
    if names.get("camera") != "extra/camera.ko":
        raise ValueError("camera.ko is not staged as the original external module")
    if names.get("wl2866d") != "kernel/drivers/misc/wl2866d.ko":
        raise ValueError("WL2866D does not originate from OEM kernel module tree")
    if "wl2866d" not in manifest.get("audited_oem_roots", []):
        raise ValueError("WL2866D diagnostic root was not independently audited")

    loaded = []
    for raw in manifest.get("modprobe_camera_insmod_order", []):
        parts = raw.split()
        if len(parts) == 2 and parts[0] == "insmod":
            loaded.append(Path(parts[1]).name)
    if "wl2866d.ko" not in loaded or "camera.ko" not in loaded:
        raise ValueError("modprobe camera does not load OEM WL2866D and Camera")
    if loaded.index("wl2866d.ko") >= loaded.index("camera.ko"):
        raise ValueError("Camera loads before its WL2866D power provider")
    return {"verified_power_symbols": list(POWER_SYMBOLS),
            "camera_modprobe_order": loaded,
            "production_qualified": False}


def command(*argv):
    return subprocess.check_output(argv, text=True).strip()


def inspect(camera, ldo, config_path, manifest_path):
    config = {}
    for line in config_path.read_text().splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            if key in config:
                raise ValueError("duplicate kernel config key: " + key)
            config[key] = value
    if not camera.is_file() or not ldo.is_file():
        raise ValueError("missing actually compiled OEM Camera or WL2866D ELF")
    if command("modinfo", "-F", "name", str(camera)) != "camera":
        raise ValueError("unexpected Camera ELF module name")
    if command("modinfo", "-F", "name", str(ldo)) != "wl2866d":
        raise ValueError("unexpected OEM regulator ELF module name")
    camera_vermagic = command("modinfo", "-F", "vermagic", str(camera))
    ldo_vermagic = command("modinfo", "-F", "vermagic", str(ldo))
    if camera_vermagic != ldo_vermagic:
        raise ValueError("Camera/WL2866D modules have mismatched kernel vermagic")
    manifest = json.loads(manifest_path.read_text())
    report = check_contract(
        config, nm_symbols(command("nm", "-P", str(camera))),
        nm_symbols(command("nm", "-P", str(ldo))),
        command("modinfo", "-F", "depends", str(camera)), manifest)
    if manifest.get("sha256", {}).get("camera") != hashlib.sha256(camera.read_bytes()).hexdigest():
        raise ValueError("staged Camera SHA256 differs from compiled ELF")
    if manifest.get("sha256", {}).get("wl2866d") != hashlib.sha256(ldo.read_bytes()).hexdigest():
        raise ValueError("staged WL2866D SHA256 differs from compiled ELF")
    return {"device": "mondrian", "android_base": "AOSP 17",
            "status": "PASS_DIAGNOSTIC_CAMERA_OEM_POWER_ABI",
            "camera_sha256": hashlib.sha256(camera.read_bytes()).hexdigest(),
            "wl2866d_sha256": hashlib.sha256(ldo.read_bytes()).hexdigest(),
            "vermagic": camera_vermagic, **report}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--camera", required=True, type=Path)
    p.add_argument("--wl2866d", required=True, type=Path)
    p.add_argument("--config", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    try:
        report = inspect(a.camera, a.wl2866d, a.config, a.manifest)
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        p.error("Camera/WL2866D ABI not qualified: " + str(exc))
    print("[PASS] Camera imports both OEM WL2866D power symbols and loads the provider first")
    print("[PENDING] Mondrian sensor wiring, rail allocations, Camera HAL and runtime")


if __name__ == "__main__":
    main()
