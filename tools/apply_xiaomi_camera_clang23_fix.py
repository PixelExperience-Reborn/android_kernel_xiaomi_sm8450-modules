#!/usr/bin/env python3
"""Exact OEM Camera Clang23 prototype fix in disposable Xiaomi checkout only.

The manufacturer Git revision is never rewritten. The script corrects precisely
four empty-parameter C definitions in two Xiaomi files, retaining the original
function bodies, compile flags and hardware GPIO logic. Fail closed on source
SHA, header SHA, tracked modifications or unexpected code.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

OEM_COMMIT = "9ed4ce96d49c0759c6365627113c5f59c2407942"
SOURCE = Path("drivers/cam_utils/cam_debug_util.c")
HEADER = Path("drivers/cam_utils/cam_debug_util.h")
SOURCE_BLOB = "70a252d6a819fc2dd3467744d282dcb4a4c49965"
HEADER_BLOB = "64115ca74986c1716badfc6ab9f305fa70ebe930"
OLD = b"const struct camera_debug_settings *cam_debug_get_settings()\n"
NEW = b"const struct camera_debug_settings *cam_debug_get_settings(void)\n"
HEADER_DECL = b"const struct camera_debug_settings *cam_debug_get_settings(void);"
FLASH_SOURCE = Path("drivers/cam_sensor_module/cam_flash/cam_flash_dev.c")
FLASH_BLOB = "3a7514facf01022e628e2e59613fd980978f9358"
FLASH_SIGNATURES = (
    b"static int cam_flash_i2c_driver_powerup()\n",
    b"static int cam_flash_i2c_driver_powerdown()\n",
    b"static void cam_flash_i2c_driver_deinit_kobject()\n",
)
# These are the three exact lines rejected by LLVM23 in Actions #43952612008.
# The functions already have exclusively no-argument callers in this OEM tree.
FLASH_CALLS = (
    b"cam_flash_i2c_driver_powerup();",
    b"cam_flash_i2c_driver_powerdown();",
    b"cam_flash_i2c_driver_deinit_kobject();",
)
FLASH_GPIO_CONTRACT = b"#define I2C_FLASH_GPIO_EN 356"


def blob_id(content):
    prefix = b"blob " + str(len(content)).encode("ascii") + bytes([0])
    return hashlib.sha1(prefix + content).hexdigest()


def patch_definition(source, header):
    if header.count(HEADER_DECL) != 1:
        raise ValueError("original Xiaomi header no longer declares (void)")
    if source.count(OLD) != 1 or NEW in source:
        raise ValueError("expected one unpatched OEM Camera definition")
    updated = source.replace(OLD, NEW, 1)
    if updated == source:
        raise ValueError("OEM Camera definition unchanged unexpectedly")
    return updated


def patch_flash_definitions(source):
    # Do not alter flash wiring/enablement; this candidate is NOT approved for
    # actual mondrian hardware. Rewriting a yudi GPIO is not a compiler fix.
    if source.count(FLASH_GPIO_CONTRACT) != 1:
        raise ValueError("Xiaomi flash GPIO contract changed")
    patched = source
    for old, call in zip(FLASH_SIGNATURES, FLASH_CALLS):
        if patched.count(old) != 1 or patched.count(call) != 1:
            raise ValueError("Expected a single no-argument Xiaomi flash definition/call")
        new = old.replace(b"()\n", b"(void)\n")
        if new in patched:
            raise ValueError("Flash function already fixed or edited")
        patched = patched.replace(old, new, 1)
    if patched.count(FLASH_GPIO_CONTRACT) != 1:
        raise ValueError("Flash GPIO unexpectedly changed")
    return patched


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True).strip()


def inspect_checkout(root):
    if not root.is_dir():
        raise ValueError("Xiaomi Camera source checkout is absent")
    if git(root, "rev-parse", "HEAD") != OEM_COMMIT:
        raise ValueError("unapproved Xiaomi Camera source commit")
    if git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Xiaomi Camera checkout has tracked changes")
    source = (root / SOURCE).read_bytes()
    header = (root / HEADER).read_bytes()
    if blob_id(source) != SOURCE_BLOB:
        raise ValueError("Xiaomi Camera C definition Git blob changed")
    if blob_id(header) != HEADER_BLOB:
        raise ValueError("Xiaomi Camera declaration Git blob changed")
    flash = (root / FLASH_SOURCE).read_bytes()
    if blob_id(flash) != FLASH_BLOB:
        raise ValueError("Xiaomi flash source Git blob changed")
    return source, header, flash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=Path("xiaomi-camera-source"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    root = args.source.resolve()
    try:
        original, header, flash = inspect_checkout(root)
        corrected = patch_definition(original, header)
        corrected_flash = patch_flash_definitions(flash)
        if args.apply:
            # Both blobs are fully validated before touching the disposable
            # checkout. Never relax warnings to bypass real build failures.
            (root / SOURCE).write_bytes(corrected)
            (root / FLASH_SOURCE).write_bytes(corrected_flash)
            if ((root / SOURCE).read_bytes() != corrected or
                    (root / FLASH_SOURCE).read_bytes() != corrected_flash):
                raise ValueError("Camera source patch write failed")
            changed = set(git(root, "diff", "--name-only").splitlines())
            if changed != {SOURCE.as_posix(), FLASH_SOURCE.as_posix()}:
                raise ValueError("Unexpected Xiaomi source modified")
            numstat = git(root, "diff", "--numstat")
            expected_numstat = {
                "1\t1\t" + SOURCE.as_posix(),
                "3\t3\t" + FLASH_SOURCE.as_posix(),
            }
            if set(numstat.splitlines()) != expected_numstat:
                raise ValueError("Camera patch must change exactly four lines")
            if git(root, "diff", "--check"):
                raise ValueError("Camera patch whitespace errors")
        if args.evidence:
            report = {
                "source": "MiCode/vendor_qcom_opensource_camera-kernel",
                "source_commit": OEM_COMMIT,
                "paths": [SOURCE.as_posix(), FLASH_SOURCE.as_posix()],
                "original_blob": SOURCE_BLOB,
                "patched_blob": blob_id(corrected),
                "flash_original_blob": FLASH_BLOB,
                "flash_patched_blob": blob_id(corrected_flash),
                "header_blob_unchanged": HEADER_BLOB,
                "changes": "four C no-argument definitions () to (void)",
                "flash_gpio_unchanged": True,
                "applied": args.apply,
                "compiler_warnings_suppressed": False,
                "camera_module_abi_qualified": False,
                "hardware_validated": False,
            }
            args.evidence.parent.mkdir(parents=True, exist_ok=True)
            args.evidence.write_text(json.dumps(report, indent=2) + "\n")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print("[PASS] " + ("Applied" if args.apply else "Validated") +
          " exact OEM Camera Clang23 prototype corrections (four C lines)")


if __name__ == "__main__":
    main()
