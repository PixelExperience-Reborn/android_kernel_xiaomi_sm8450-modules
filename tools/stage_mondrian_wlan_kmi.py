#!/usr/bin/env python3
"""Stage exact mondrian WLAN/MMRM/Display/Camera module dependency closure as diagnostic modules.

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



def verify_oem_diagnostic_roots(basenames, compiled_by_basename, occupied_roots):
    """Select only existing OEM .ko files for extra diagnostic load checks.

    These independent roots are NOT an Android vendor_dlkm load list.
    """
    roots = []
    for basename in basenames:
        if not re.fullmatch(r"[A-Za-z0-9_+.-]+[.]ko", basename) or "/" in basename or ".." in basename:
            raise ValueError("invalid OEM diagnostic module basename: " + repr(basename))
        path = compiled_by_basename.get(basename)
        if path is None:
            raise ValueError("required OEM diagnostic module is not compiled: " + basename)
        name = module_name(path)
        if name in occupied_roots or name in roots:
            raise ValueError("duplicate/colliding OEM diagnostic root: " + name)
        roots.append(name)
    return tuple(roots)


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
    p.add_argument("--camera", type=Path,
                   help="Optional OEM Xiaomi camera.ko, only with --cameralog")
    p.add_argument("--cameralog", type=Path,
                   help="Optional OEM Xiaomi cameralog.ko, only with --camera")
    p.add_argument("--audit-oem-root", action="append", default=[], metavar="BASENAME.ko",
                   help="Independently verify one compiled OEM module's diagnostic depmod closure")
    p.add_argument("--external-root", type=Path, action="append", default=[],
                   help="Additional compiled external diagnostic root (repeatable)")
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
    oem_by_basename = {}
    for path in sorted(kout.rglob("*.ko")):
        name = module_name(path)
        if name in files:
            p.error(f"Ambiguous compiled OEM module {name}: {path} and {files[name]}")
        if path.name in oem_by_basename:
            p.error("Duplicate compiled OEM module filename: " + path.name)
        files[name] = path
        oem_by_basename[path.name] = path
    wlan, mmrm = args.wlan.resolve(), args.mmrm.resolve()
    display = args.display.resolve() if args.display is not None else None
    if (args.camera is None) != (args.cameralog is None):
        p.error("Xiaomi camera.ko and cameralog.ko must be selected together")
    camera = args.camera.resolve() if args.camera is not None else None
    cameralog = args.cameralog.resolve() if args.cameralog is not None else None
    camera_modules = (camera, cameralog) if camera is not None else ()
    extra_roots = tuple(path.resolve() for path in args.external_root)
    external_modules = (wlan, mmrm) + ((display,) if display is not None else ()) + camera_modules + extra_roots
    if len(set(external_modules)) != len(external_modules):
        p.error("Duplicate external module path")
    if len({path.name for path in external_modules}) != len(external_modules):
        p.error("Duplicate external module filename")
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
    camera_name = module_name(camera) if camera is not None else None
    cameralog_name = module_name(cameralog) if cameralog is not None else None
    if camera is not None and (camera_name != "camera" or cameralog_name != "cameralog"):
        p.error("Unexpected Xiaomi Camera module names, refusing diagnostic selection")
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
    initial_roots = (
        (mmrm_name, wlan_name) +
        ((display_name,) if display_name else ()) +
        ((camera_name, cameralog_name) if camera is not None else ())
    )
    extra_names = tuple(module_name(path) for path in extra_roots)
    initial_roots += extra_names
    try:
        audited_roots = verify_oem_diagnostic_roots(
            args.audit_oem_root, oem_by_basename, set(initial_roots))
    except ValueError as error:
        p.error(str(error))
    roots = initial_roots + audited_roots
    order = compute_closure(roots, files)

    try:
        dest = checked_stage_directory(
            args.out, (kernel, kout, Path(__file__).resolve().parents[1],
                       wlan.parent, mmrm.parent,
                       *((display.parent,) if display is not None else ()),
                       *((camera.parent, cameralog.parent)
                         if camera is not None else ()),
                       *(path.parent for path in extra_roots)))
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
    checked_camera = (
        command(["modprobe", "-d", dest, "-S", release,
                 "--show-depends", camera_name]).splitlines()
        if camera is not None else [])
    checked_cameralog = (
        command(["modprobe", "-d", dest, "-S", release,
                 "--show-depends", cameralog_name]).splitlines()
        if cameralog is not None else [])
    checked_oem = {
        root: command(["modprobe", "-d", dest, "-S", release,
                       "--show-depends", root]).splitlines()
        for root in audited_roots
    }
    checked_extra = {
        root: command(["modprobe", "-d", dest, "-S", release,
                       "--show-depends", root]).splitlines()
        for root in extra_names
    }
    expected = {Path(s).name for s in mapping.values()}
    wlan_actual = insmod_basenames(checked_wlan)
    mmrm_actual = insmod_basenames(checked_mmrm)
    display_actual = insmod_basenames(checked_display)
    camera_actual = insmod_basenames(checked_camera)
    cameralog_actual = insmod_basenames(checked_cameralog)
    if camera is not None and (
            camera.name not in camera_actual or
            cameralog.name not in cameralog_actual):
        p.error("modprobe dry-run omitted Xiaomi Camera/cameralog roots")
    if wlan.name not in wlan_actual or mmrm.name not in mmrm_actual:
        p.error("modprobe dry-run omitted the selected WLAN or MMRM root")
    if display is not None and display.name not in display_actual:
        p.error("modprobe dry-run omitted the selected Qualcomm Display root")
    actual = wlan_actual | mmrm_actual | display_actual | camera_actual | cameralog_actual
    for root, dry_run in checked_oem.items():
        loaded = insmod_basenames(dry_run)
        if files[root].name not in loaded:
            p.error("modprobe dry-run omitted critical OEM root: " + root)
        actual.update(loaded)
    for root, dry_run in checked_extra.items():
        loaded = insmod_basenames(dry_run)
        if files[root].name not in loaded:
            p.error("modprobe dry-run omitted external root: " + root)
        actual.update(loaded)
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
        "modprobe_camera_insmod_order": checked_camera,
        "modprobe_cameralog_insmod_order": checked_cameralog,
        "camera_modules_included": camera is not None,
        "camera_modules_are_diagnostic_only": True,
        "audited_oem_roots": list(audited_roots),
        "additional_external_roots": list(extra_names),
        "modprobe_additional_external_roots": checked_extra,
        "modprobe_oem_diagnostic_roots": checked_oem,
        "production_boot_load_order_qualified": False,
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
    print("[PASS] Exact kernel WLAN/MMRM" +
          ("/Display" if display is not None else "") +
          ("/Camera/cameralog" if camera is not None else "") +
          f" plus {len(audited_roots)} OEM diagnostic root(s) depmod+modprobe closure verified")
    print("[PENDING] Firmware, partition selection, SELinux, real hardware boot")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        sys.exit(1)
