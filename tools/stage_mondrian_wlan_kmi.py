#!/usr/bin/env python3
"""Stage exact mondrian WLAN/MRR M runtime dependency closure as diagnostic modules.

Uses only Xiaomi's compiled OEM kernel modules and pinned Qualcomm MMRM/WLAN
outputs. Refuses absent/duplicate module dependencies. Does not build an
Android product image or claim hardware bootability.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

KERNEL_SHA = "2466406b9beac724960b0c88e6e794421d0466e7"
ROOT_WLAN_DEPS = frozenset(
    ("icnss2", "mi_cnss_statistic", "cfg80211",
     "cnss_prealloc", "cnss_nl", "cnss_utils")
)
REQUIRED_CONFIG = (
    "ICNSS2", "MI_CNSS_STATISTIC", "CFG80211",
    "WCNSS_MEM_PRE_ALLOC", "CNSS_GENL", "CNSS_UTILS"
)


def command(argv):
    return subprocess.check_output(list(map(str, argv)), text=True).strip()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dependencies(path):
    raw = command(["modinfo", "-F", "depends", path])
    return [v.strip().replace("-", "_") for v in raw.split(",") if v.strip()]


def module_name(path):
    return command(["modinfo", "-F", "name", path]).replace("-", "_")


def parse_config(path):
    return {row.split("=", 1)[0]: row.split("=", 1)[1]
            for row in path.read_text().splitlines()
            if row.startswith("CONFIG_") and "=" in row}


def compute_closure(roots, files):
    """Map named modules to their direct dependency order, rejecting cycles."""
    ordered = []
    visited = set()
    active = set()

    def visit(name):
        if name in visited:
            return
        if name in active:
            raise RuntimeError("Kernel module dependency cycle: " + name)
        if name not in files:
            raise RuntimeError("Required OEM kernel module missing: " + name)
        active.add(name)
        for dep in dependencies(files[name]):
            visit(dep)
        active.remove(name)
        visited.add(name)
        ordered.append(name)
    for root in roots:
        visit(root)
    return ordered


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--kernel", type=Path, required=True)
    p.add_argument("--kernel-out", type=Path, required=True)
    p.add_argument("--wlan", type=Path, required=True)
    p.add_argument("--mmrm", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    kernel, kout = args.kernel.resolve(), args.kernel_out.resolve()
    if command(["git", "-C", kernel, "rev-parse", "HEAD"]) != KERNEL_SHA:
        p.error("Kernel revision does not match approved Xiaomi OEM revision")
    if not (kout / "Module.symvers").is_file() or not (kout / "vmlinux").is_file():
        p.error("Missing fully compiled OEM vmlinux and Module.symvers")
    config = parse_config(kout / ".config")
    for symbol in REQUIRED_CONFIG:
        if config.get("CONFIG_" + symbol) != "m":
            p.error("Manufacturer kernel config not built as module: CONFIG_" + symbol)
    release = command(["make", "-s", "-C", kernel, f"O={kout}", "kernelrelease"])

    files = {}
    for path in sorted(kout.rglob("*.ko")):
        name = module_name(path)
        if name in files:
            p.error(f"Ambiguous compiled OEM module {name}: {path} and {files[name]}")
        files[name] = path
    wlan, mmrm = args.wlan.resolve(), args.mmrm.resolve()
    if not wlan.is_file() or not mmrm.is_file():
        p.error("External Xiaomi WLAN and Qualcomm MMRM .ko must be compiled first")
    for external in (wlan, mmrm):
        name = module_name(external)
        if name in files:
            p.error(f"External module collides with OEM in-tree module: {name}")
        files[name] = external
        vermagic = command(["modinfo", "-F", "vermagic", external])
        if not vermagic.startswith(release + " "):
            p.error(f"External module ABI version mismatch: {name}, {vermagic}")

    wlan_name = module_name(wlan)
    mmrm_name = module_name(mmrm)
    if wlan_name != "qca_cld3_qca6490":
        p.error(f"Unexpected Xiaomi WLAN kernel module name: {wlan_name}")
    present = frozenset(dependencies(wlan))
    if not ROOT_WLAN_DEPS.issubset(present):
        p.error("WLAN direct dependencies differ from audited OEM contract: " +
                ", ".join(sorted(present)))
    order = compute_closure((mmrm_name, wlan_name), files)

    dest = args.out.resolve()
    if dest.exists():
        shutil.rmtree(dest)
    module_root = dest / "lib/modules" / release
    mapping = {}
    for name in order:
        original = files[name]
        if original == wlan or original == mmrm:
            target = module_root / "extra" / original.name
        else:
            target = module_root / "kernel" / original.relative_to(kout)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)
        mapping[name] = str(target.relative_to(module_root))
    # Build depmod tables using the complete transitive compiled-module closure.
    subprocess.run(["depmod", "-b", str(dest), "-a", release], check=True)
    checked = command(["modprobe", "-d", dest, "-S", release,
                       "--show-depends", wlan_name]).splitlines()
    expected = {Path(s).name for s in mapping.values()}
    actual = {Path(s.split(" ", 1)[1]).name for s in checked
              if s.startswith("insmod ")}
    if not expected.issubset(actual | {mmrm.name}):
        p.error("modprobe dry-run did not resolve complete WLAN dependency graph")
    manifest = {
        "device": "mondrian",
        "kernel_commit": KERNEL_SHA,
        "kernel_release": release,
        "module_symvers_sha256": sha256(kout / "Module.symvers"),
        "staged_module_order": order,
        "module_files": mapping,
        "sha256": {name: sha256(files[name]) for name in order},
        "modprobe_wlan_insmod_order": checked,
        "compiled_and_dependency_closure_checked": True,
        "release_vendor_dlkm_packaging": False,
        "firmware_verified": False,
        "hardware_loaded": False,
    }
    (dest / "mondrian-wlan-diagnostic-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print("[PASS] All OEM WLAN dependencies present; depmod+modprobe closure verified")
    print("[PENDING] Firmware, partition selection, SELinux, real hardware boot")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        sys.exit(1)
