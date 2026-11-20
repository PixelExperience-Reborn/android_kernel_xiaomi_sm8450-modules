#!/usr/bin/env python3
"""Fail-closed PE-Reborn mondrian Camera flash backend selection.

For the *diagnostic checkout only*, retain Xiaomi Camera and generic Qualcomm
I2C/PMIC code, but require the original yudi-specific sysfs/GPIO356 branch
to remain unselected. The original manufacturer Git revision is untouched.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

CAMERA_SHA = "9ed4ce96d49c0759c6365627113c5f59c2407942"
DTS_SHA = "ccddf20d0d5f546b45e8d65df6b3c9de59825f48"
OEM_DTS_SHA = "34e6cc7d832ed9c655b9d79bc3ffe1d625146b7c"
OEM_COMMON_BLOB = "e4e321d4d54353f0243b0283647528180baa3137"
HEADER = Path("drivers/cam_sensor_module/cam_flash/cam_flash_dev.h")
HEADER_BLOB = "592f7380c157e386ea724b20078f76d2edbac94d"
DEFINITION = b"#define CONFIG_CAMERA_I2CFLASH 1\n"
NEARBY = b'#define FLASH_DRIVER_I2C "cam-i2c-flash"'
REPLACEMENT = (
    b"/* PE-Reborn mondrian: Xiaomi yudi's auxiliary I2C sysfs/flash GPIO 356\n"
    b" * is not a verified part of this board. Keep the separate generic\n"
    b" * Qualcomm PMIC and Camera I2C implementations intact. This build\n"
    b" * must not select the yudi-only CONFIG_CAMERA_I2CFLASH extension.\n"
    b" */\n"
    b"#ifdef CONFIG_CAMERA_I2CFLASH\n"
    b'#error "Unqualified yudi I2C flash backend forbidden on mondrian"\n'
    b"#endif\n"
)
ORIGINAL_CHANGED = {
    "drivers/cam_utils/cam_debug_util.c",
    "drivers/cam_sensor_module/cam_flash/cam_flash_dev.c",
}
EXPECTED_POLICY = {
    "backend": "Qualcomm PM8350C",
    "driver_configuration": "pmic_from_device_tree",
    "mondrian_diagnostic_switch0_mask": 1,
    "manufacturer_yudi_i2c_sysfs_gpio356_enabled": False,
    "mutter_flash_mask_hardware_qualified": False,
    "mondrian_oem_camera_dtbo_verified": False,
    "flash_sensor_topology_verified": False,
    "hardware_torch_test_passed": False,
    "production_camera_flash_allowed": False,
}


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True).strip()


def hashblob(blob):
    return hashlib.sha1(b"blob " + str(len(blob)).encode("ascii") +
                        b"\0" + blob).hexdigest()


def select_mondrian_flash(header):
    """Change one forced hardware define into a compile-time refusal gate."""
    if header.count(NEARBY) != 1 or header.count(DEFINITION) != 1:
        raise ValueError("unexpected Xiaomi flash header layout / forced macro")
    if REPLACEMENT in header:
        raise ValueError("source already guarded unexpectedly")
    modified = header.replace(DEFINITION, REPLACEMENT, 1)
    if DEFINITION in modified:
        raise ValueError("vendor I2C flash remains force-enabled")
    if modified.replace(REPLACEMENT, DEFINITION, 1) != header:
        raise ValueError("changed anything beyond forced hardware selection")
    return modified


def verify_policy(policy):
    expected = {
        "schema_version": 1, "project": "PixelExperience-Reborn",
        "android_base": "AOSP 17", "device": "mondrian", "soc": "SM8475",
        "selected_kernel_commit":
            "ef722b7b3773dacc805a65fd42d022206001266a",
        "manufacturer_camera": {
            "repository": "MiCode/vendor_qcom_opensource_camera-kernel",
            "commit": CAMERA_SHA, "reference_device": "yudi",
            "header_blob": HEADER_BLOB,
        },
        "xiaomi_device_tree": {
            "repository":
                "PixelExperience-Reborn/android_kernel_xiaomi_sm8450-devicetrees",
            "commit": DTS_SHA,
            "manufacturer_repository": "MiCode/kernel_devicetree",
            "manufacturer_commit": OEM_DTS_SHA,
            "common_dts_git_blob": OEM_COMMON_BLOB,
        },
        "flash_selection": EXPECTED_POLICY,
        "status": "SOURCE_ABI_PASS_HARDWARE_FLASH_UNQUALIFIED",
    }
    if policy != expected:
        raise ValueError("unreviewed mondrian PMIC, donor GPIO or release gate")


def verify_manufacturer_dts(dts):
    if git(dts, "rev-parse", "HEAD") != DTS_SHA:
        raise ValueError("wrong PE OEM Devicetrees revision")
    lock = json.loads((dts / "oem-source-lock.json").read_text())
    if (lock.get("source_repository") != "MiCode/kernel_devicetree" or
            lock.get("source_commit") != OEM_DTS_SHA or
            lock.get("original_git_blobs", {}).get(
                "qcom/xiaomi-sm8475-common.dtsi") != OEM_COMMON_BLOB):
        raise ValueError("original Xiaomi PM8350C device-tree provenance drift")
    path = "qcom/xiaomi-sm8475-common.dtsi"
    if git(dts, "hash-object", path) != OEM_COMMON_BLOB:
        raise ValueError("OEM PMIC common DTS bytes changed")
    contents = (dts / path).read_text()
    for required in (
        "&pm8350c_flash {", 'status = "ok";',
        "&pm8350c_switch0 {", "qcom,led-mask = <9>;",
        "&pm8350c_switch1 {", "&pm8350c_switch2 {",
    ):
        if required not in contents:
            raise ValueError("manufacturer PM8350C baseline changed")
    # The Xiaomi common board mask is not a validated mondrian camera mask.


def inspect_camera(root):
    if git(root, "rev-parse", "HEAD") != CAMERA_SHA:
        raise ValueError("wrong MiCode Camera source revision")
    header = (root / HEADER).read_bytes()
    if hashblob(header) != HEADER_BLOB:
        raise ValueError("original Xiaomi Camera header blob changed")
    changed = set(git(root, "diff", "--name-only").splitlines())
    if changed != ORIGINAL_CHANGED:
        raise ValueError("Camera checkout must have exactly the two LLVM23 fixes")
    cpath = root / "drivers/cam_sensor_module/cam_flash/cam_flash_dev.c"
    c = cpath.read_bytes()
    if (c.count(b"#define I2C_FLASH_GPIO_EN 356") != 1 or
            c.count(b"#ifdef CONFIG_CAMERA_I2CFLASH") < 3 or
            b"gpio_request_one(I2C_FLASH_GPIO_EN" not in c):
        raise ValueError("original donor flash/GPIO guard changed")
    return header


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--device-tree", type=Path, required=True)
    ap.add_argument("--manifest", type=Path,
                    default=Path("mondrian-camera-flash-policy.json"))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--evidence", type=Path)
    args = ap.parse_args()
    try:
        policy = json.loads(args.manifest.read_text(encoding="utf-8"))
        verify_policy(policy)
        verify_manufacturer_dts(args.device_tree.resolve())
        root = args.source.resolve()
        original = inspect_camera(root)
        adjusted = select_mondrian_flash(original)
        if args.apply:
            (root / HEADER).write_bytes(adjusted)
            if (root / HEADER).read_bytes() != adjusted:
                raise ValueError("flash backend patch did not persist")
            modified = set(git(root, "diff", "--name-only").splitlines())
            if modified != ORIGINAL_CHANGED | {HEADER.as_posix()}:
                raise ValueError("unexpected source file modified")
            if git(root, "diff", "--check"):
                raise ValueError("whitespace error in device hardware gate")
        if args.evidence:
            report = {
                "device": "mondrian",
                "oem_camera_commit": CAMERA_SHA,
                "kernel_commit": policy["selected_kernel_commit"],
                "oem_device_tree_commit": OEM_DTS_SHA,
                "flash_backend": "Qualcomm PM8350C",
                "mondrian_diagnostic_switch0_mask": policy["flash_selection"]["mondrian_diagnostic_switch0_mask"],
                "unqualified_yudi_i2c_gpio356_compiled": False
                    if args.apply else None,
                "modified_header_sha1": hashblob(adjusted),
                "generic_camera_i2c_source_preserved": True,
                "manufacturer_camera_dtbo_verified": False,
                "hardware_flash_qualified": False,
                "production_flash_allowed": False,
            }
            args.evidence.write_text(json.dumps(report, indent=2) + "\n")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        ap.error(str(exc))
    print("[PASS] " + ("Selected" if args.apply else "Validated") +
          " OEM PM8350C path; yudi auxiliary GPIO356 backend forbidden")
    print("[PENDING] PM8350C torch and flash on physical mondrian")


if __name__ == "__main__":
    main()
