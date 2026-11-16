#!/usr/bin/env python3
"""Check actual OEM Camera ELF for Qualcomm PMIC and excluded yudi sysfs flash.

The selected MiCode Camera driver has NO cam_flash_pmic_power_ops symbol.
On the PMIC path, cam_flash_dev.c instead sets power_ops = NULL and
selects cam_flash_pmic_{pkt_parser,apply_setting,flush_request}, with the
PMIC LED prepare function in cam_flash_core.c. Check the *real* symbols.

This check is static compile evidence only, not a camera/flash runtime test.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

EXPECTED_VERMAGIC = "5.10.81-gki-g032260f7c8da"
PMIC_FUNCTIONS = frozenset({
    "cam_flash_pmic_pkt_parser",
    "cam_flash_pmic_apply_setting",
    "cam_flash_pmic_flush_request",
    "cam_flash_led_prepare",
})
GENERIC_I2C_FUNCTIONS = frozenset({
    "cam_flash_i2c_pkt_parser",
    "cam_flash_i2c_apply_setting",
    "cam_flash_i2c_power_ops",
    "cam_flash_i2c_flush_request",
})
GENERIC_I2C_DRIVER = {
    "cam_flash_i2c_driver": frozenset({"D", "d"}),
    "cam_flash_i2c_driver_probe": frozenset({"T", "t"}),
}
UNQUALIFIED_YUDI_SYMBOLS = frozenset({
    "cam_flash_i2c_driver_powerup",
    "cam_flash_i2c_driver_powerdown",
    "cam_flash_i2c_driver_set_torch",
    "cam_flash_i2c_driver_init_kobject",
    "cam_flash_i2c_driver_deinit_kobject",
    "i2c_flash_kobj",
    "i2c_flash_brightness",
    "i2c_flash_switch",
    "i2c_flash_status",
    "fctrl_flash",
    "fctrl_flash_aux",
})


def parse_nm_posix(output):
    """Parse GNU nm -P symbol rows; preserve the actual ELF type flags."""
    symbols = {}
    for row in output.splitlines():
        fields = row.split()
        if len(fields) < 2 or len(fields[1]) != 1:
            continue
        symbols.setdefault(fields[0], set()).add(fields[1])
    if not symbols:
        raise ValueError("no ELF symbols returned by nm -P")
    return symbols


def check_camera_elf(symbols):
    missing_pmic = sorted(
        f for f in PMIC_FUNCTIONS
        if not symbols.get(f, set()) & {"T", "t"})
    missing_generic_i2c = sorted(
        f for f in GENERIC_I2C_FUNCTIONS
        if not symbols.get(f, set()) & {"T", "t"})
    missing_generic_i2c.extend(sorted(
        f for f, types in GENERIC_I2C_DRIVER.items()
        if not symbols.get(f, set()) & types))
    forbidden = sorted(UNQUALIFIED_YUDI_SYMBOLS & symbols.keys())
    if missing_pmic or missing_generic_i2c or forbidden:
        raise ValueError(
            "incorrect OEM camera ELF: "
            f"missing PMIC={missing_pmic}; "
            f"missing generic I2C={missing_generic_i2c}; "
            f"unqualified yudi GPIO356/sysfs symbols={forbidden}")
    # No fictional cam_flash_pmic_power_ops: PMIC has no power_ops callback.
    return {
        "pmic_functions": sorted(PMIC_FUNCTIONS),
        "generic_i2c_functions": sorted(GENERIC_I2C_FUNCTIONS |
                                        GENERIC_I2C_DRIVER.keys()),
        "unqualified_yudi_sysfs_gpio356_symbols_present": False,
    }


def inspect(module):
    if not module.is_file() or module.stat().st_size < 4096:
        raise ValueError("missing/invalid compiled camera.ko")
    symbols = parse_nm_posix(subprocess.check_output(
        ["nm", "-P", str(module)], text=True))
    checks = check_camera_elf(symbols)
    vermagic = subprocess.check_output(
        ["modinfo", "-F", "vermagic", str(module)], text=True).strip()
    if not vermagic.startswith(EXPECTED_VERMAGIC + " "):
        raise ValueError(f"unexpected OEM kernel vermagic: {vermagic!r}")
    return {
        "status": "PASS_STATIC_CAMERA_PMIC_ELF",
        "device": "mondrian",
        "android_base": "AOSP 17",
        "module_sha256": hashlib.sha256(module.read_bytes()).hexdigest(),
        "module_vermagic": vermagic,
        "kernel_revision": "032260f7c8dacf338e1ac993e1653cd1982877d1",
        "qualcomm_pmic_static_symbols_verified": True,
        "generic_i2c_static_symbols_verified": True,
        "manufacturer_camera_dtbo_qualified": False,
        "pm8350c_channel_mask_hardware_qualified": False,
        "stock_camera_firmware_qualified": False,
        "hardware_boot_qualified": False,
        "production_flash_approved": False,
        **checks,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = inspect(args.module)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.error(f"mondrian Camera ELF qualification blocked: {exc}")
    print("[PASS] OEM Qualcomm PMIC/GPIO-independent Camera path in camera.ko")
    print("[PASS] Generic Camera I2C retained; yudi sysfs/GPIO356 code absent")
    print("[PENDING] Real mondrian stock Camera DTBO, PM8350C channels and hardware")


if __name__ == "__main__":
    main()
