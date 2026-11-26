#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Package the mondrian kernel release for device/xiaomi/mondrian-kernel.

Inputs are the outputs of one CI run: the kernel Image, every module it
built (in-tree and external), the base DTBs and dtbo.img of the DT chain.
Modules are placed and ordered as in the stock OS3.0.8.0.VMNCNXM firmware
(stock/os3.0.8.0/: the names of the modules of its vendor_boot ramdisk and
vendor_dlkm and their load lists):

* vendor_ramdisk/: the modules stock has in its vendor_boot ramdisk, plus
  every module they depend on; modules.load and modules.load.recovery are
  the stock lists, in stock order, limited to the modules we ship;
* vendor_dlkm/: every other module; modules.load is the stock list of
  vendor_dlkm (which also names the modules Xiaomi keeps in /vendor, such
  as the WLAN driver), limited to the modules we ship.

Every module must carry the vermagic of the Image's kernel release and
every dependency must be shipped. The stock modules we do not build are
recorded in provenance.json, as are the exact sources, compiler and CI run.
"""
import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "stock/os3.0.8.0"
REPOSITORY = "https://github.com/PixelExperience-Reborn/"
SOURCES = {
    "kernel": "android_kernel_xiaomi_sm8450",
    "modules": "android_kernel_xiaomi_sm8450-modules",
    "devicetrees": "android_kernel_xiaomi_sm8450-devicetrees",
}
DTBS = ("cape", "capep", "cape-v2")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def modinfo(path):
    """Fields of the .modinfo section of a kernel module (ELF64 LE)."""
    data = Path(path).read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        raise ValueError(f"{path}: not a little-endian ELF64 module")
    shoff, = struct.unpack_from("<Q", data, 0x28)
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x3A)
    sections = [struct.unpack_from("<IIQQQQIIQQ", data, shoff + i * shentsize) for i in range(shnum)]
    names = sections[shstrndx]
    fields = {}
    for name, _type, _flags, _addr, offset, size, *_ in sections:
        end = data.index(b"\0", names[4] + name)
        if data[names[4] + name:end] != b".modinfo":
            continue
        for item in data[offset:offset + size].split(b"\0"):
            if b"=" in item:
                key, value = item.decode(errors="replace").split("=", 1)
                fields.setdefault(key, value)
        return fields
    raise ValueError(f"{path}: no .modinfo section")


def kernel_release(image):
    """The release string of an arm64 Image (as printed by uname -r)."""
    data = Path(image).read_bytes()
    match = re.search(rb"Linux version (\d[^\s\x00]*) ", data)
    if not match:
        raise ValueError(f"{image}: no Linux version banner")
    return match.group(1).decode()


def read_list(name):
    return [line.strip() for line in (STOCK / name).read_text().splitlines()
            if line.strip() and not line.startswith("#")]


def collect(paths):
    """{module file name: path}; the same name must be the same file."""
    modules = {}
    for root in paths:
        root = Path(root)
        candidates = [root] if root.is_file() else sorted(root.rglob("*.ko"))
        for path in candidates:
            name = path.name
            if name in modules and sha256(modules[name]) != sha256(path):
                raise ValueError(f"two different modules named {name}: {modules[name]} and {path}")
            modules.setdefault(name, path)
    if not modules:
        raise ValueError("no kernel modules found")
    return modules


def closure(names, deps):
    out, todo = set(), list(names)
    while todo:
        name = todo.pop()
        if name in out:
            continue
        out.add(name)
        todo.extend(deps[name])
    return out


def package(image, module_roots, dt_dir, out, provenance, strip=None):
    release = kernel_release(image)
    modules = collect(module_roots)
    info = {name: modinfo(path) for name, path in modules.items()}
    by_module_name = {}
    for name, fields in info.items():
        magic = fields.get("vermagic", "").split()
        if not magic or magic[0] != release:
            raise ValueError(f"{name}: vermagic {fields.get('vermagic')!r} is not {release}")
        by_module_name[fields.get("name", name[:-3]).replace("-", "_")] = name
    deps = {}
    for name, fields in info.items():
        wanted = [d for d in fields.get("depends", "").split(",") if d]
        missing = [d for d in wanted if d.replace("-", "_") not in by_module_name]
        if missing:
            raise ValueError(f"{name}: depends on modules that were not built: {missing}")
        deps[name] = [by_module_name[d.replace("-", "_")] for d in wanted]

    stock_ramdisk = set(read_list("vendor_ramdisk.modules"))
    ramdisk = closure([n for n in modules if n in stock_ramdisk], deps)
    dlkm = set(modules) - ramdisk

    if out.exists():
        shutil.rmtree(out)
    (out / "vendor_ramdisk").mkdir(parents=True)
    (out / "vendor_dlkm").mkdir()
    (out / "dtbs").mkdir()
    shutil.copyfile(image, out / "Image")
    for name in modules:
        dest = out / ("vendor_ramdisk" if name in ramdisk else "vendor_dlkm") / name
        shutil.copyfile(modules[name], dest)
        if strip:
            subprocess.run([strip, "--strip-debug", str(dest)], check=True)
    loads = {
        "vendor_ramdisk/modules.load": [n for n in read_list("vendor_ramdisk.modules.load") if n in ramdisk],
        "vendor_ramdisk/modules.load.recovery":
            [n for n in read_list("vendor_ramdisk.modules.load.recovery") if n in ramdisk],
        "vendor_dlkm/modules.load": [n for n in read_list("vendor_dlkm.modules.load") if n in dlkm],
    }
    for rel, names in loads.items():
        if not names:
            raise ValueError(f"{rel}: no stock module of this list was built")
        (out / rel).write_text("".join(n + "\n" for n in names))
    for directory in ("vendor_ramdisk", "vendor_dlkm"):
        shutil.copyfile(STOCK / "modules.blocklist", out / directory / "modules.blocklist")
    for base in DTBS:
        shutil.copyfile(dt_dir / "dtbs" / (base + ".dtb"), out / "dtbs" / (base + ".dtb"))
    shutil.copyfile(dt_dir / "dtbo.img", out / "dtbo.img")

    stock_all = set()
    for name in ("vendor_ramdisk.modules", "vendor_ramdisk.modules.load",
                 "vendor_ramdisk.modules.load.recovery", "vendor_dlkm.modules", "vendor_dlkm.modules.load"):
        stock_all |= set(read_list(name))
    files = {str(p.relative_to(out)): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}
    prov = dict(provenance)
    prov.update({
        "schema": 1,
        "device": "mondrian",
        "kernel_release": release,
        "stock_reference": "OS3.0.8.0.VMNCNXM",
        "modules": {
            "vendor_ramdisk": len(ramdisk),
            "vendor_dlkm": len(dlkm),
            "stock_not_built": sorted(stock_all - set(modules)),
            "built_not_in_stock_lists": sorted(set(modules) - stock_all),
        },
        "files": files,
    })
    (out / "provenance.json").write_text(json.dumps(prov, indent=2, sort_keys=True) + "\n")
    return prov


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--modules", type=Path, action="append", required=True,
                        help="a module file or a directory searched for *.ko (repeatable)")
    parser.add_argument("--dt", type=Path, required=True, help="output of build_mondrian_dtbo.py")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--strip", help="llvm-strip used with --strip-debug")
    for name in SOURCES:
        parser.add_argument(f"--{name}-commit", required=True)
    parser.add_argument("--clang", required=True)
    parser.add_argument("--clang-prebuilt-commit", required=True)
    parser.add_argument("--ci-repository", required=True)
    parser.add_argument("--ci-workflow", required=True)
    parser.add_argument("--ci-run-id", type=int, required=True)
    args = parser.parse_args()
    provenance = {
        "sources": {name: {"repository": REPOSITORY + repo, "commit": getattr(args, f"{name}_commit")}
                    for name, repo in SOURCES.items()},
        "toolchain": {"clang": args.clang, "prebuilt_commit": args.clang_prebuilt_commit},
        "ci": {"repository": args.ci_repository, "workflow": args.ci_workflow, "run_id": args.ci_run_id},
    }
    try:
        prov = package(args.image, args.modules, args.dt, args.out, provenance, args.strip)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        return 1
    m = prov["modules"]
    print(f"[PASS] {prov['kernel_release']}: {m['vendor_ramdisk']} modules in vendor_ramdisk, "
          f"{m['vendor_dlkm']} in vendor_dlkm; stock modules not built: {len(m['stock_not_built'])}")
    for name in m["stock_not_built"]:
        print(f"  not built: {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
