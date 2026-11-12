#!/usr/bin/env python3
"""Strict evidence gate for Xiaomi external module built against the selected OEM kernel."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

def command(args):
    return subprocess.check_output(args, text=True).strip()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--kernel", type=Path, required=True)
    p.add_argument("--kernel-out", type=Path, required=True)
    p.add_argument("--module", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    kernel = args.kernel.resolve()
    output = args.kernel_out.resolve()
    module = args.module.resolve()
    if command(["git", "-C", str(kernel), "rev-parse", "HEAD"]) != (
        "2466406b9beac724960b0c88e6e794421d0466e7"
    ):
        p.error("kernel commit drift")
    for file in (output / "vmlinux", output / "Module.symvers",
                 output / ".config", module):
        if not file.is_file() or file.stat().st_size == 0:
            p.error(f"missing required compiled file: {file}")
    version = command(["make", "-s", "-C", str(kernel), f"O={output}", "kernelrelease"])
    vermagic = command(["modinfo", "-F", "vermagic", str(module)])
    if not vermagic.startswith(version + " "):
        p.error(f"external module vermagic mismatch: {vermagic} versus {version}")
    machine = command(["readelf", "-h", str(module)])
    if "Machine:" not in machine or "AArch64" not in machine:
        p.error("external module module is not AArch64 ELF")
    if command(["modinfo", "-F", "license", str(module)]) == "":
        p.error("external module module lacks license metadata")
    deps = command(["modinfo", "-F", "depends", str(module)])
    # Symbol errors are rejected by kbuild/modpost; capture the exact symvers
    # and source hashes, not a false claim of real Wi-Fi firmware readiness.
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    evidence = {
        "device": "mondrian",
        "kernel_commit": "2466406b9beac724960b0c88e6e794421d0466e7",
        "kernelrelease": version,
        "module": module.name,
        "vermagic": vermagic,
        "depends": deps.split(",") if deps else [],
        "kernel_config_sha256": sha(output / ".config"),
        "module_symvers_sha256": sha(output / "Module.symvers"),
        "external_module_module_sha256": sha(module),
        "module_compile": True,
        "vendor_dlkm_packaging": False,
        "firmware_validated": False,
        "hardware_booted": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, indent=2) + "\n")
    print("[PASS] External QCACLD .ko, AArch64 ELF and exact OEM vermagic")
    print("[PENDING] Firmware and device integration")

if __name__ == "__main__":
    main()
