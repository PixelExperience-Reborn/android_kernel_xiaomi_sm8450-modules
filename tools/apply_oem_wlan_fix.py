#!/usr/bin/env python3
"""Reproducible one-line Xiaomi WLAN ABI-neutral C prototype correction."""
import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "upstream/xiaomi-wlan/qcacld-3.0/core/mac/src/include/parser_api.h"
OEM_BLOB = "03e33b11d583a16dd3b8666ff7764ed45f27b5ba"
FROM = b"\t\t   uint8_t mdie[]);"
TO = b"\t\t   uint8_t mdie[SIR_MDIE_SIZE]);"

def blob_id(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + bytes([0]) + data).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Mutate only the disposable vendor submodule working tree")
    args = parser.parse_args()
    original = FILE.read_bytes()
    if blob_id(original) != OEM_BLOB:
        parser.error("The original Xiaomi WLAN header has changed; refusing a speculative edit")
    if original.count(FROM) != 1 or original.count(TO) != 0:
        parser.error("Expected exactly one original populate_mdie declaration")
    updated = original.replace(FROM, TO)
    if args.apply:
        FILE.write_bytes(updated)
        if FILE.read_bytes() != updated:
            parser.error("Failed to update disposable OEM source checkout")
        print("[PASS] One ABI-neutral header parameter bound corrected")
    else:
        print("[PASS] Exact source blob and single reviewed prototype correction verified")

if __name__ == "__main__":
    main()
