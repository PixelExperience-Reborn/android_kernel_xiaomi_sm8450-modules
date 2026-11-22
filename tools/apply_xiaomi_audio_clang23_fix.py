#!/usr/bin/env python3
"""Exact Xiaomi Audio no-argument prototypes for LLVM23.

Preserve all QoS behavior, callers, hardware configuration and warning gates.
Only modify the disposable checkout after proving the original source identity.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

COMMIT = "7d174adfe5304b74889e0cf0e16132a049707710"
SOURCE = "asoc/msm_common.c"
BLOB = "3e0f74811493311487ecd32f4658939099507fe5"
FUNCTIONS = (b"msm_audio_add_qos_request", b"msm_audio_remove_qos_request")


def blob_id(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def corrected(source):
    result = source
    for name in FUNCTIONS:
        old = b"static void " + name + b"()\n"
        new = b"static void " + name + b"(void)\n"
        call = name + b"();"
        if result.count(old) != 1 or result.count(call) != 1 or new in result:
            raise ValueError("unexpected QoS definition or call: " + name.decode())
        result = result.replace(old, new, 1)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    root = args.source.resolve()
    if git(root, "rev-parse", "HEAD") != COMMIT:
        raise ValueError("unreviewed Xiaomi Audio source commit")
    if git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Xiaomi Audio checkout is not pristine")
    path = root / SOURCE
    original = path.read_bytes()
    if blob_id(original) != BLOB:
        raise ValueError("Xiaomi Audio source blob drift")
    updated = corrected(original)
    path.write_bytes(updated)
    if path.read_bytes() != updated:
        raise ValueError("Audio patch write failed")
    if git(root, "diff", "--name-only") != SOURCE:
        raise ValueError("unexpected changed Audio paths")
    if git(root, "diff", "--numstat") != "2\t2\t" + SOURCE:
        raise ValueError("Audio patch must change exactly two definitions")
    if git(root, "diff", "--check"):
        raise ValueError("Audio patch whitespace errors")
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps({
        "source_commit": COMMIT, "source_path": SOURCE,
        "original_blob": BLOB, "patched_blob": blob_id(updated),
        "functions": [n.decode() for n in FUNCTIONS],
        "warnings_suppressed": False, "hardware_qualified": False,
    }, indent=2) + "\n")
    print("[PASS] Exactly two Xiaomi Audio QoS prototypes corrected; behavior unchanged")


if __name__ == "__main__":
    main()
