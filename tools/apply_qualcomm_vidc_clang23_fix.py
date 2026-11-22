#!/usr/bin/env python3
"""Repair exact Qualcomm WAIPIO VIDC declarations rejected by LLVM23.

Use explicit int to preserve the original implicit-int semantics, including
negative error codes. The debugfs definition matches its existing header.
Never change a function body, caller, configuration or compiler warning.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

COMMIT = "707fcdb08626667663d13cfceeb2d9dfe92893e3"
DEBUG_HEADER = "driver/vidc/inc/msm_vidc_debug.h"
DEBUG_HEADER_BLOB = "89f61f62a61662bfd983c10ddaaa25ce4887880e"
DEBUG_DECL = b"struct dentry *msm_vidc_debugfs_init_drv(void);"
PATCHES = {
    "driver/vidc/inc/msm_vidc_driver.h": (
        "4aff5f019c905d3e7f5aa38f4ae792b29421379f",
        (
            (b"static inline is_decode_session(", b"static inline int is_decode_session("),
            (b"static inline is_encode_session(", b"static inline int is_encode_session("),
            (b"static inline is_image_encode_session(", b"static inline int is_image_encode_session("),
            (b"static inline is_image_decode_session(", b"static inline int is_image_decode_session("),
            (b"static inline is_image_session(", b"static inline int is_image_session("),
            (b"static inline is_secure_session(", b"static inline int is_secure_session("),
            (b"static inline is_input_buffer(", b"static inline int is_input_buffer("),
            (b"static inline is_output_buffer(", b"static inline int is_output_buffer("),
            (b"static inline is_input_meta_buffer(", b"static inline int is_input_meta_buffer("),
            (b"static inline is_output_meta_buffer(", b"static inline int is_output_meta_buffer("),
            (b"static inline is_ts_reorder_allowed(", b"static inline int is_ts_reorder_allowed("),
            (b"static inline is_scaling_enabled(", b"static inline int is_scaling_enabled("),
            (b"static inline is_rotation_90_or_270(", b"static inline int is_rotation_90_or_270("),
            (b"static inline is_internal_buffer(", b"static inline int is_internal_buffer("),
        ),
    ),
    "driver/vidc/src/msm_vdec.c": (
        "fc82dbf21259113a32a5b8934414dcd360a8783e",
        (
            (b"static msm_vdec_alloc_and_queue_additional_dpb_buffers(", b"static int msm_vdec_alloc_and_queue_additional_dpb_buffers("),
        ),
    ),
    "driver/vidc/src/msm_vidc_control.c": (
        "1db2dfd306cd82d3ae529f2a1aba53072372a604",
        (
            (b"static msm_venc_set_csc_coeff(", b"static int msm_venc_set_csc_coeff("),
        ),
    ),
    "driver/vidc/src/msm_vidc_debug.c": (
        "6d3951a59855617731f509f1f3471b6255e891c3",
        (
            (b"struct dentry* msm_vidc_debugfs_init_drv()\n", b"struct dentry* msm_vidc_debugfs_init_drv(void)\n"),
        ),
    ),
}


def blob_id(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def corrected(source, pairs):
    updated = source
    for old, new in pairs:
        pattern = rb"(?m)^" + re.escape(old)
        if len(re.findall(pattern, updated)) != 1 or new in updated:
            raise ValueError("unexpected Qualcomm declaration: " + old.decode())
        updated = re.sub(pattern, lambda _: new, updated, count=1)
    return updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    root = args.source.resolve()
    if git(root, "rev-parse", "HEAD") != COMMIT:
        raise ValueError("unreviewed Qualcomm VIDC revision")
    if git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("VIDC checkout is not pristine")
    header = (root / DEBUG_HEADER).read_bytes()
    if blob_id(header) != DEBUG_HEADER_BLOB or header.count(DEBUG_DECL) != 1:
        raise ValueError("VIDC debugfs existing prototype drift")
    planned = {}
    evidence = {}
    for path, (blob, pairs) in PATCHES.items():
        original = (root / path).read_bytes()
        if blob_id(original) != blob:
            raise ValueError("VIDC source blob drift: " + path)
        updated = corrected(original, pairs)
        planned[path] = updated
        evidence[path] = {"original_blob": blob, "patched_blob": blob_id(updated),
                          "declarations": len(pairs)}
    # Validate every input before editing any file.
    for path, updated in planned.items():
        (root / path).write_bytes(updated)
    if set(git(root, "diff", "--name-only").splitlines()) != set(PATCHES):
        raise ValueError("unexpected changed VIDC paths")
    expected = {f"{len(pairs)}\t{len(pairs)}\t{path}"
                for path, (_, pairs) in PATCHES.items()}
    if set(git(root, "diff", "--numstat").splitlines()) != expected:
        raise ValueError("VIDC patch must change exactly 17 declarations")
    if git(root, "diff", "--check"):
        raise ValueError("VIDC patch whitespace errors")
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps({
        "source_commit": COMMIT, "files": evidence,
        "total_declarations": 17, "warnings_suppressed": False,
        "hardware_qualified": False,
    }, indent=2) + "\n")
    print("[PASS] Exactly 17 Qualcomm VIDC declarations corrected; behavior unchanged")


if __name__ == "__main__":
    main()
