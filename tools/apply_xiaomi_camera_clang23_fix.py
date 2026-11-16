#!/usr/bin/env python3
"""Exact OEM Camera Clang23 prototype fix in disposable Xiaomi checkout only.

The manufacturer Git revision is never rewritten; this tool only corrects one
C definition to match its already-correct header prototype. Fail closed on
source SHA, header SHA, uncommitted source changes or unexpected code.
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
    return source, header


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=Path("xiaomi-camera-source"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    root = args.source.resolve()
    try:
        original, header = inspect_checkout(root)
        corrected = patch_definition(original, header)
        if args.apply:
            (root / SOURCE).write_bytes(corrected)
            if (root / SOURCE).read_bytes() != corrected:
                raise ValueError("Camera source patch write failed")
            if git(root, "diff", "--name-only") != SOURCE.as_posix():
                raise ValueError("Unexpected Xiaomi source modified")
            if git(root, "diff", "--numstat", "--", SOURCE.as_posix()) != (
                "1\t1\t" + SOURCE.as_posix()
            ):
                raise ValueError("Camera change must be one line only")
        if args.evidence:
            report = {
                "source": "MiCode/vendor_qcom_opensource_camera-kernel",
                "source_commit": OEM_COMMIT,
                "path": SOURCE.as_posix(),
                "original_blob": SOURCE_BLOB,
                "patched_blob": blob_id(corrected),
                "header_blob_unchanged": HEADER_BLOB,
                "change": "C no-arg definition () to (void)",
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
          " exact OEM Camera Clang23 prototype correction (one C line)")


if __name__ == "__main__":
    main()
