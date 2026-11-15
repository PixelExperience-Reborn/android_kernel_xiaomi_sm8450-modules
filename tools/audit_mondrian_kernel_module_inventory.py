#!/usr/bin/env python3
"""Audit the exact compiled Xiaomi mondrian kernel module inventory.

This is a strict source/ABI diagnostic; it does not create an Android 17
vendor_boot/vendor_dlkm load list or imply real device hardware success.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

EXPECTED_COUNT = 106
EXPECTED_UNIQUE = 104
OPTIONAL_UNSHIPPED = {
    "sched-walt-debug.ko": "CONFIG_SCHED_WALT_DEBUG",
    "msm_rtb.ko": "CONFIG_QCOM_RTB",
    "mem-offline.ko": "CONFIG_QCOM_MEM_OFFLINE",
}
BUILTIN_EXPECTATION = (
    "deferred-free-helper.ko", "CONFIG_DMABUF_HEAPS_DEFERRED_FREE",
    "drivers/dma-buf/heaps/deferred-free-helper.o",
)
# Compile-only gates, not a proposed first-stage load ordering.
MONDRIAN_CRITICAL_MODULES = frozenset({
    "goodix_core.ko", "goodix_fod.ko", "panel_event_notifier.ko",
    "dispcc-waipio.ko", "msm_kgsl.ko", "qti_cpufreq_cdev.ko",
    "qti_devfreq_cdev.ko", "thermal_pause.ko", "sched-walt.ko",
    "ufs_qcom.ko", "qcom_dma_heaps.ko", "qti_battery_charger.ko",
    "qcom-cpufreq-hw.ko", "qcom_wdt_core.ko",
})


def cmd(*args):
    return subprocess.check_output(list(map(str, args)), text=True).strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cfgvalues(path):
    result = {}
    for raw in path.read_text().splitlines():
        if raw.startswith("CONFIG_") and "=" in raw:
            k, v = raw.split("=", 1)
            if k in result:
                raise ValueError("duplicate config key: " + k)
            result[k] = v
    return result


def classify(expected, built, config, kernel_out):
    names = [s.strip() for s in expected if s.strip()]
    if len(names) != EXPECTED_COUNT or len(set(names)) != EXPECTED_UNIQUE:
        raise ValueError("OEM module inventory count drift: expected 106 entries / 104 unique")
    if "bt_fm_slim.ko" in names:
        raise ValueError("FM Slimbus module must not be selected by mondrian product")
    unique = set(names)
    missing = unique - set(built)
    allowed = set(OPTIONAL_UNSHIPPED) | {BUILTIN_EXPECTATION[0]}
    if missing != allowed:
        raise ValueError("unreviewed OEM missing modules: " + repr(sorted(missing ^ allowed)))
    for name, symbol in OPTIONAL_UNSHIPPED.items():
        if config.get(symbol) in ("y", "m"):
            raise ValueError(name + " unexpectedly enabled as " + symbol)
    name, flag, obj = BUILTIN_EXPECTATION
    if config.get(flag) != "y" or not (kernel_out / obj).is_file():
        raise ValueError(name + " must exist as a compiled built-in object")
    return {
        "oem_entries": len(names),
        "oem_unique_entries": len(unique),
        "compiled_oem_names": len(unique) - len(missing),
        "unshipped_builtin_object": obj,
        "unselected_optional_modules": sorted(OPTIONAL_UNSHIPPED),
        "unexpected_missing": [],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kernel", type=Path, required=True)
    p.add_argument("--kernel-out", type=Path, required=True)
    p.add_argument("--expected-kernel-commit", required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    kernel, output = a.kernel.resolve(), a.kernel_out.resolve()
    if not re.fullmatch(r"[0-9a-f]{40}", a.expected_kernel_commit):
        p.error("expected kernel commit must be an exact lowercase 40-hex SHA")
    actual = cmd("git", "-C", kernel, "rev-parse", "HEAD")
    if actual != a.expected_kernel_commit:
        p.error("kernel source SHA mismatch: " + actual)
    for fname in (".config", "Module.symvers", "modules.order", "modules.builtin",
                  "arch/arm64/boot/Image", "vmlinux"):
        file = output / fname
        if not file.is_file() or not file.stat().st_size:
            p.error("missing full compiled kernel input: " + str(file))
    originals = kernel / "modules.list.msm.mondrian"
    if not originals.is_file():
        p.error("missing original Xiaomi module inventory")
    ko_files = {}
    for path in output.rglob("*.ko"):
        if path.name in ko_files:
            p.error("duplicate compiled kernel module basename: " + path.name)
        ko_files[path.name] = path
    absent_critical = MONDRIAN_CRITICAL_MODULES - set(ko_files)
    if absent_critical:
        p.error("missing compiled mondrian boot/interactive driver(s): " +
                ", ".join(sorted(absent_critical)))
    try:
        measured = classify(originals.read_text().splitlines(), ko_files,
                            cfgvalues(output / ".config"), output)
    except ValueError as exc:
        p.error(str(exc))
    release = cmd("make", "-s", "-C", kernel, f"O={output}", "kernelrelease")
    selected = {s.strip() for s in originals.read_text().splitlines() if s.strip()}
    present = sorted(selected & set(ko_files))
    for name in sorted(set(present) | MONDRIAN_CRITICAL_MODULES):
        ko = ko_files[name]
        vermagic = cmd("modinfo", "-F", "vermagic", ko)
        if not vermagic.startswith(release + " "):
            p.error(f"compiled {name} vermagic mismatch: {vermagic}")
        elf = cmd("readelf", "-h", ko)
        if "Machine:" not in elf or "AArch64" not in elf:
            p.error(f"compiled {name} is not an AArch64 module")
    report = {
        "device": "mondrian", "android_base": "AOSP 17",
        "kernel_commit": actual, "kernel_release": release,
        "kernel_config_sha256": sha(output / ".config"),
        "module_symvers_sha256": sha(output / "Module.symvers"),
        "kernel_image_sha256": sha(output / "arch/arm64/boot/Image"),
        "original_oem_inventory_sha256": sha(originals),
        "total_in_tree_ko": len(ko_files),
        "compiled_oem_module_sha256": {n: sha(ko_files[n]) for n in present},
        "critical_mondrian_kernel_ko_sha256": {
            n: sha(ko_files[n]) for n in sorted(MONDRIAN_CRITICAL_MODULES)},
        "inventory_diagnostic": measured,
        "production_load_list_qualified": False,
        "factory_m11a_panel_qualified": False,
        "boot_img_qualified": False, "vendor_boot_qualified": False,
        "vendor_dlkm_qualified": False, "hardware_booted": False,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"[PASS] Compiled OEM inventory: {len(present)}/104 unique names, "
          f"{len(MONDRIAN_CRITICAL_MODULES)} critical drivers, "
          "4 audited built-in/optional exceptions")
    print("[PENDING] Full Android 17 module load list, M11A panel, vendor_dlkm and hardware")


if __name__ == "__main__":
    main()
