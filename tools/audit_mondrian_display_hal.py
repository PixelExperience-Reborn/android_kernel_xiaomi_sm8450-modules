#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read-only inventory of extracted mondrian stock vendor HAL binaries.

This identifies binaries for subsequent ARM disassembly; it cannot prove ioctl
arguments, read lengths, driver selection, firmware authenticity or hardware.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess

MAX_BYTES = 128 * 1024 * 1024
NAME_HINT = re.compile(r"display|composer|fingerprint|goodix|(?:^|[_.-])sdm(?:[_.-]|$)|libdrm|gralloc|hwc", re.I)
IO_NAMES = {"open", "open64", "openat", "read", "__read_chk", "readv", "pread64",
            "ioctl", "__ioctl", "poll", "ppoll", "epoll_wait", "epoll_pwait"}


def identify(data, name):
    if len(data) < 20 or data[:4] != b"\x7fELF" or data[5] != 1:
        return None
    arch = { (2, 183): "AArch64", (1, 40): "ARM" }.get(
        (data[4], int.from_bytes(data[18:20], "little")))
    if not arch:
        return None
    direct = b"/dev/mi_display/disp_feature" in data
    split = b"mi_display" in data and b"disp_feature" in data
    if not (direct or split or NAME_HINT.search(name)):
        return None
    return {"architecture": arch, "full_disp_feature_path_literal": direct,
            "mi_display_and_disp_feature_literals": split,
            "filename_hint": bool(NAME_HINT.search(name))}


def parse_readelf(dynamic, symbols):
    needed = sorted(set(re.findall(r"\(NEEDED\).*?\[([^\]]+)\]", dynamic)))
    imports = set()
    for line in symbols.splitlines():
        match = re.search(r"\bUND\s+(\S+)", line)
        if match:
            name = match.group(1).split("@", 1)[0]
            if name in IO_NAMES:
                imports.add(name)
    return {"needed": needed, "io_imports": sorted(imports)}


def inventory(root, readelf):
    records, skipped = [], []
    scanned = 0
    for sub in ("bin", "lib", "lib64"):
        top = root / sub
        if top.is_symlink() or not top.is_dir():
            continue
        for directory, dirs, names in os.walk(top, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink())
            for name in sorted(names):
                path = Path(directory) / name
                rel = path.relative_to(root).as_posix()
                try:
                    info = path.lstat()
                    if not stat.S_ISREG(info.st_mode):
                        continue
                    with path.open("rb") as stream:
                        if stream.read(4) != b"\x7fELF":
                            continue
                        if info.st_size > MAX_BYTES:
                            skipped.append({"path": rel, "reason": "ELF exceeds size limit"})
                            continue
                        stream.seek(0)
                        data = stream.read(MAX_BYTES + 1)
                    if len(data) != info.st_size:
                        skipped.append({"path": rel, "reason": "file changed during read"})
                        continue
                    scanned += 1
                    flags = identify(data, name)
                    if flags is None:
                        continue
                    record = {"path": rel, "sha256": hashlib.sha256(data).hexdigest(),
                              "size_bytes": len(data), **flags}
                    try:
                        def run(*args):
                            return subprocess.check_output(
                                [readelf, "--wide", *args, str(path)],
                                stderr=subprocess.DEVNULL, text=True,
                                errors="replace", timeout=30)
                        record.update(parse_readelf(run("--dynamic"), run("--dyn-syms")))
                        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
                            raise ValueError("file changed during readelf")
                    except (OSError, subprocess.SubprocessError, ValueError):
                        record["readelf_complete"] = False
                    else:
                        record["readelf_complete"] = True
                    records.append(record)
                except OSError:
                    skipped.append({"path": rel, "reason": "unreadable"})
    return {"elf_files_scanned": scanned, "candidates": sorted(records, key=lambda v: v["path"]),
            "skipped": sorted(skipped, key=lambda v: v["path"])}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--vendor-root", required=True, type=Path,
                   help="Extracted original vendor partition; not a custom ROM vendor")
    p.add_argument("--firmware-build", required=True)
    p.add_argument("--firmware-sha256", help="Optional caller-supplied archive SHA256")
    p.add_argument("--out", required=True, type=Path, help="New JSON file outside vendor")
    a = p.parse_args()
    root, out = a.vendor_root.resolve(), a.out.resolve()
    if not root.is_dir() or not (root / "lib64").is_dir():
        p.error("expected an extracted vendor directory with lib64")
    if root == out or root in out.parents:
        p.error("output must be outside the vendor tree")
    if out.exists() or not out.parent.is_dir():
        p.error("output must be a new file in an existing directory")
    if a.firmware_sha256 and not re.fullmatch(r"[0-9a-fA-F]{64}", a.firmware_sha256):
        p.error("invalid archive SHA256 syntax")
    readelf = shutil.which("readelf")
    if not readelf:
        p.error("readelf is required (host binutils)")
    report = {"device_expected": "mondrian", "android_base": "AOSP 17",
              "caller_firmware_build": a.firmware_build,
              "caller_firmware_archive_sha256": a.firmware_sha256,
              **inventory(root, readelf),
              "qualification": {
                  "firmware_authenticity_verified": False,
                  "hal_call_sites_verified": False,
                  "sde_payload_layout_verified": False,
                  "fod_read_protocol_verified": False,
                  "hardware_verified": False,
                  "production_display_approved": False}}
    with out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(f"Inventory: {len(report['candidates'])} candidates; HAL protocol remains unverified.")


if __name__ == "__main__":
    main()
