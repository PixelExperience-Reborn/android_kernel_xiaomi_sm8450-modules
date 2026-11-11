#!/usr/bin/env python3
"""Byte-exact, minimal Xiaomi QCACLD Clang23 compatibility corrections.

The pinned vendor sources remain unchanged in Git. Corrections affect only
disposable CI source working trees, after checking their exact OEM blob IDs.
"""
import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WLAN = ROOT / "upstream/xiaomi-wlan"
PATCHES = (
    {
        "path": "qcacld-3.0/core/mac/src/include/parser_api.h",
        "blob": "03e33b11d583a16dd3b8666ff7764ed45f27b5ba",
        "from": b"\t\t   uint8_t mdie[]);",
        "to": b"\t\t   uint8_t mdie[SIR_MDIE_SIZE]);",
    },
    {
        "path": "qca-wifi-host-cmn/target_if/core/src/target_if_main.c",
        "blob": "35d6be02cf60fdd2300aaa9643d0ec1a8de8cf3d",
        "from": b"struct target_if_ctx *target_if_get_ctx()\n",
        "to": b"struct target_if_ctx *target_if_get_ctx(void)\n",
    },
    {
        "path": "qcacld-3.0/core/dp/htt/htt_h2t.c",
        "blob": "b85f7c7a1b19fb4b999bad907026c27ca3a0dbb8",
        "from": b"return A_ERROR; /* failure */",
        "to": b"return QDF_STATUS_E_FAILURE; /* failure */",
        "expected_occurrences": 2,
        "existing_target_occurrences": 6,
    },
    {
        "path": "qca-wifi-host-cmn/hif/src/hif_exec.c",
        "blob": "9c23342fb5fd50332d1fe78981fb85473b8a62e2",
        # The vendor helper already initializes the atomic under the
        # FEATURE_IRQ_AFFINITY feature guard. Never initialize it again
        # outside the guard, where the field is absent.
        "from": (b"\tqdf_atomic_init(&hif_ext_group->force_napi_complete);\n"
                 b"\thif_init_force_napi_complete(hif_ext_group);"),
        "to": b"\thif_init_force_napi_complete(hif_ext_group);",
        "existing_target_occurrences": 1,
    },
)
HEADER_PATH = "qca-wifi-host-cmn/target_if/core/inc/target_if.h"
HEADER_BLOB = "f56cceecbd790c8894c9556494b1d12bd8aff5ce"


def blob_id(content):
    return hashlib.sha1(
        b"blob " + str(len(content)).encode("ascii") + bytes([0]) + content
    ).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply", action="store_true",
        help="Modify only the disposable, pinned Xiaomi WLAN checkout"
    )
    args = parser.parse_args()
    # The function header already declares the correct (void) prototype.
    header = (WLAN / HEADER_PATH).read_bytes()
    if blob_id(header) != HEADER_BLOB or (
        header.count(b"struct target_if_ctx *target_if_get_ctx(void);") != 1
    ):
        parser.error("Expected original Qualcomm target_if_get_ctx(void) declaration")

    hif_header = (WLAN / "qca-wifi-host-cmn/hif/src/hif_exec.h").read_bytes()
    if (b"#ifdef FEATURE_IRQ_AFFINITY\n"
            b"\tqdf_atomic_t force_napi_complete;\n#endif" not in hif_header):
        parser.error("Qualcomm IRQ affinity struct guard differs from OEM")

    hif_source = (WLAN / "qca-wifi-host-cmn/hif/src/hif_exec.c").read_bytes()
    if (b"#ifdef FEATURE_IRQ_AFFINITY\nstatic inline void\n"
            b"hif_init_force_napi_complete(" not in hif_source):
        parser.error("Qualcomm guarded NAPI atomic initializer is absent")

    validated = []
    for spec in PATCHES:
        path = WLAN / spec["path"]
        raw = path.read_bytes()
        if blob_id(raw) != spec["blob"]:
            parser.error(f"Unexpected Xiaomi source revision: {spec['path']}")
        expected = spec.get("expected_occurrences", 1)
        existing_to = spec.get("existing_target_occurrences", 0)
        if (raw.count(spec["from"]) != expected or
                raw.count(spec["to"]) != existing_to):
            parser.error(
                f"Expected exactly {expected} original declarations: {spec['path']}"
            )
        updated = raw.replace(spec["from"], spec["to"])
        validated.append((path, raw, updated))

    if args.apply:
        for path, _, updated in validated:
            path.write_bytes(updated)
            if path.read_bytes() != updated:
                parser.error(f"Failed to update disposable checkout: {path}")
        print(f"[PASS] Applied {len(validated)} exact OEM Clang23 source fixes")
    else:
        print(f"[PASS] Validated {len(validated)} pinned OEM source edits")


if __name__ == "__main__":
    main()
