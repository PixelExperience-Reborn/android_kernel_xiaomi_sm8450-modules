#!/usr/bin/env python3
"""Stage exact mondrian WLAN/MMRM/Display module dependency closure as diagnostic modules.

Uses only Xiaomi's compiled OEM kernel modules and pinned Qualcomm MMRM/WLAN
outputs. Refuses absent/duplicate module dependencies. Does not build an
Android product image or claim hardware bootability.
"""
import argparse
import hashlib
import json
import re
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


def verify_kernel_revision(kernel, expected):
    """Refuse unreviewed kernel revisions, including ambiguous symbolic refs."""
    if re.fullmatch(r"[0-9a-f]{40}", expected) is None:
        raise ValueError("Expected kernel revision must be a lowercase 40-hex SHA")
    actual = command(["git", "-C", kernel, "rev-parse", "HEAD"])
    if actual != expected:
        raise ValueError(f"Kernel revision drift: expected {expected}, got {actual}")
    return actual


def checked_stage_directory(destination, sources):
    """Require a fresh diagnostic directory disjoint from all source inputs.

    The stage is never a reason to recursively delete existing data, even
    when a caller accidentally supplies a kernel checkout or build directory.
    """
    requested = Path(destination).expanduser()
    if requested.exists() or requested.is_symlink():
        raise ValueError(f"refusing to overwrite existing staging destination: {requested}")
    stage = requested.resolve()
    for source in sources:
        input_path = Path(source).resolve()
        if (stage == input_path or stage in input_path.parents or
                input_path in stage.parents):
            raise ValueError(f"staging destination overlaps kernel/module input: {stage}")
    return stage


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dependencies(path):
    raw = command(["modinfo", "-F", "depends", path])
    return [v.strip().replace("-", "_") for v in raw.split(",") if v.strip()]


def module_name(path):
    return command(["modinfo", "-F", "name", path]).replace("-", "_")


def insmod_basenames(commands):
    """Kernel modules that modprobe would load, excluding built-ins."""
    # `modprobe --show-depends` may print `insmod /path/module.ko ` with
    # trailing whitespace. This whitespace is not part of the module filename.
    return {Path(row.split(" ", 1)[1].strip()).name
            for row in commands if row.startswith("insmod ")}


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
    p.add_argument("--display", type=Path,
                   help="Optional Qualcomm msm_drm.ko built for this exact kernel; fail closed on its dependencies")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--expected-kernel-commit", default=KERNEL_SHA,
                   help="Exact checked-out kernel SHA (defaults to reviewed OEM-only commit)")
    args = p.parse_args()
    kernel, kout = args.kernel.resolve(), args.kernel_out.resolve()
    try:
        kernel_sha = verify_kernel_revision(kernel, args.expected_kernel_commit)
    except ValueError as error:
        p.error(str(error))
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
    display = args.display.resolve() if args.display is not None else None
    external_modules = (wlan, mmrm) + ((display,) if display is not None else ())
    for external in external_modules:
        if not external.is_file():
            p.error(f"External module must be compiled before staging: {external}")
    for external in external_modules:
        name = module_name(external)
        if name in files:
            p.error(f"External module collides with OEM in-tree module: {name}")
        files[name] = external
        vermagic = command(["modinfo", "-F", "vermagic", external])
        if not vermagic.startswith(release + " "):
            p.error(f"External module ABI version mismatch: {name}, {vermagic}")

    wlan_name = module_name(wlan)
    mmrm_name = module_name(mmrm)
    display_name = module_name(display) if display is not None else None
    if mmrm_name != "msm_mmrm":
        p.error(f"Unexpected Qualcomm MMRM module: {mmrm_name}")
    if display is not None and display_name != "msm_drm":
        p.error(f"Unexpected Qualcomm Display module: {display_name}")
    if wlan_name != "qca_cld3_qca6490":
        p.error(f"Unexpected Xiaomi WLAN kernel module name: {wlan_name}")
    present = frozenset(dependencies(wlan))
    if not ROOT_WLAN_DEPS.issubset(present):
        p.error("WLAN direct dependencies differ from audited OEM contract: " +
                ", ".join(sorted(present)))
    roots = (mmrm_name, wlan_name) + ((display_name,) if display_name else ())
    order = compute_closure(roots, files)

    try:
        dest = checked_stage_directory(
            args.out, (kernel, kout, Path(__file__).resolve().parents[1],
                       wlan.parent, mmrm.parent,
                       *((display.parent,) if display is not None else ())))
    except ValueError as error:
        p.error(str(error))
    dest.mkdir(parents=True, exist_ok=False)
    module_root = dest / "lib/modules" / release
    mapping = {}
    for name in order:
        original = files[name]
        if original in external_modules:
            target = module_root / "extra" / original.name
        else:
            target = module_root / "kernel" / original.relative_to(kout)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)
        mapping[name] = str(target.relative_to(module_root))
    # depmod must see the same built-in and ordered-module metadata that
    # belonged to the exact OEM kernel build; do not generate placeholders.
    for name in ("modules.order", "modules.builtin", "modules.builtin.modinfo"):
        original = kout / name
        if not original.is_file():
            p.error(f"Missing genuine OEM kernel metadata: {original}")
        shutil.copy2(original, module_root / name)
    subprocess.run(["depmod", "-b", str(dest), "-a", release], check=True)

    # These are TWO independent load roots. The MMRM closure is not
    # necessarily a dependency of WLAN, so checking only WLAN would falsely
    # reject transitive MMRM modules as missing.
    checked_wlan = command(["modprobe", "-d", dest, "-S", release,
                            "--show-depends", wlan_name]).splitlines()
    checked_mmrm = command(["modprobe", "-d", dest, "-S", release,
                            "--show-depends", mmrm_name]).splitlines()
    checked_display = (command(["modprobe", "-d", dest, "-S", release,
                                "--show-depends", display_name]).splitlines()
                       if display_name else [])
    expected = {Path(s).name for s in mapping.values()}
    wlan_actual = insmod_basenames(checked_wlan)
    mmrm_actual = insmod_basenames(checked_mmrm)
    display_actual = insmod_basenames(checked_display)
    if wlan.name not in wlan_actual or mmrm.name not in mmrm_actual:
        p.error("modprobe dry-run omitted the selected WLAN or MMRM root")
    if display is not None and display.name not in display_actual:
        p.error("modprobe dry-run omitted the selected Qualcomm Display root")
    actual = wlan_actual | mmrm_actual | display_actual
    missing = expected - actual
    unexpected = actual - expected
    if missing or unexpected:
        p.error("OEM modprobe closure differs: missing=" +
                ", ".join(sorted(missing)) + " unexpected=" +
                ", ".join(sorted(unexpected)))
    manifest = {
        "device": "mondrian",
        "kernel_commit": kernel_sha,
        "kernel_release": release,
        "module_symvers_sha256": sha256(kout / "Module.symvers"),
        "staged_module_order": order,
        "module_files": mapping,
        "sha256": {name: sha256(files[name]) for name in order},
        "modprobe_wlan_insmod_order": checked_wlan,
        "modprobe_mmrm_insmod_order": checked_mmrm,
        "modprobe_display_insmod_order": checked_display,
        "display_module_included": display is not None,
        "both_root_dry_run_union_matches_staged_closure": display is None,
        "all_root_dry_run_union_matches_staged_closure": True,
        "checked_module_roots": list(roots),
        "compiled_and_dependency_closure_checked": True,
        "release_vendor_dlkm_packaging": False,
        "firmware_verified": False,
        "hardware_loaded": False,
    }
    (dest / "mondrian-wlan-diagnostic-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print("[PASS] Exact kernel WLAN/MMRM" + ("/Display" if display is not None else "") +
          " depmod+modprobe dependency closure verified")
    print("[PENDING] Firmware, partition selection, SELinux, real hardware boot")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        sys.exit(1)
