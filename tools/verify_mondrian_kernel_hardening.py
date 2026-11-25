#!/usr/bin/env python3
"""Fail closed on security mode downgrade after OEM/GKI Kconfig resolution."""
import argparse
import json
from pathlib import Path
import re

REQUIRED = {
    "CONFIG_CC_IS_CLANG": "y",
    "CONFIG_ARM64_MTE": "y",
    "CONFIG_KASAN": "y",
    "CONFIG_KASAN_HW_TAGS": "y",
    "CONFIG_KASAN_GENERIC": "n",
    "CONFIG_KASAN_SW_TAGS": "n",
    "CONFIG_LTO_CLANG_FULL": "y",
    "CONFIG_LTO_NONE": "n",
    "CONFIG_CFI_CLANG": "y",
    "CONFIG_SHADOW_CALL_STACK": "y",
}
DIAG_KEYS = (
    "CONFIG_ARCH_SUPPORTS_LTO_CLANG", "CONFIG_CC_HAVE_SHADOW_CALL_STACK",
    "CONFIG_ARCH_SUPPORTS_SHADOW_CALL_STACK", "CONFIG_KALLSYMS",
    "CONFIG_HAS_LTO_CLANG", "CONFIG_HAVE_ARCH_KASAN_HW_TAGS",
    "CONFIG_AS_HAS_ARMV8_5", "CONFIG_ARM64_AS_HAS_MTE",
)


def parse(text):
    found = {}
    for line in text.splitlines():
        m = re.fullmatch(r"(CONFIG_[A-Za-z0-9_]+)=(.*)", line)
        disabled = re.fullmatch(r"# (CONFIG_[A-Za-z0-9_]+) is not set", line)
        if m:
            key, value = m.groups()
        elif disabled:
            key, value = disabled.group(1), "n"
        else:
            continue
        if key in found:
            raise ValueError("duplicate generated Kconfig key: " + key)
        found[key] = value
    if "CONFIG_ARM64" not in found or "CONFIG_CC_IS_CLANG" not in found:
        raise ValueError("not an evaluated ARM64 Clang kernel configuration")
    return found


def verify(text):
    cfg = parse(text)
    wrong = {key: {"expected": wanted, "actual": cfg.get(key, "UNSET")}
             for key, wanted in REQUIRED.items()
             if cfg.get(key, "n") != wanted}
    details = {
        "device": "mondrian", "kernel": "OEM Xiaomi 5.10.81",
        "source": "generated .config after GKI + OEM fragment + hardening + olddefconfig",
        "requirements": dict(sorted(REQUIRED.items())),
        "actual": {key: cfg.get(key, "UNSET") for key in sorted(REQUIRED)},
        "dependency_evidence": {key: cfg.get(key, "UNSET") for key in DIAG_KEYS},
        "mismatch": wrong,
        "pass": not wrong,
        "hardware_boot_verified": False,
    }
    if wrong:
        raise ValueError(json.dumps(details, sort_keys=True))
    return details


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--generated-config", type=Path, required=True)
    cli.add_argument("--out", type=Path)
    args = cli.parse_args()
    try:
        result = verify(args.generated_config.read_text())
        if args.out is not None:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    except (OSError, ValueError) as exc:
        cli.error("GKI security downgrade: " + str(exc))
    print("[PASS] OEM kernel .config: HW MTE KASAN, Full LTO, CFI, SCS retained")


if __name__ == "__main__":
    main()
