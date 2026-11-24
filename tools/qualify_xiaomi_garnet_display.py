#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Isolated Xiaomi garnet-t-oss display candidate; never selects a product driver.

Run with three local Git checkouts: pinned PE kernel, Xiaomi candidate and
Google Clang. With --build, also supply the completed Kernel #31 output,
its display-abi-evidence.json, and MMRM Module.symvers from the same build.
Source-only is the default. No full kernel build, flashing, or packaging.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

KERNEL = "2efda4cf1afa2a7098d5abd4806769903e181f73"
XIAOMI = "bf0d5e23be5457001a18aa9dcd68cb17994ae36a"
CLANG = "c9ed23e2ba198658b630d4b10e09fa980cd43119"
BLOBS = {
    "msm/Kbuild": "7bd79b7c178bb7bcbad9ed1089f3583879181b5a",
    "config/gki_waipiodisp.conf": "6822eb3116a5b220ca3ce8850c28ab35f0e6eb52",
    "msm/dsi/dsi_panel.c": "4bbf5d4a7e5f1060f290f29aa4dbcd4f5d1e43d5",
    "msm/mi_disp/mi_panel_id.h": "97ccded25b9531f398a665fc7d7bc5ce4310c493",
    "msm/mi_disp/mi_disp_lhbm.c": "b758c3f73e24637e359d82488e4541318954de45",
    "msm/mi_disp/mi_disp_feature.c": "14136033374c4c8ea78dfbd6342aff4ca98b718a",
    "include/uapi/display/drm/sde_drm.h": "95615480dc72ffc6244870f777051d2ad76ade8d",
    "include/uapi/display/drm/mi_disp.h": "e6ce0e2d17728872e40dde6d5138505b307edfd2",
}
BASE = "techpack/display"
SDE = "include/uapi/display/drm/sde_drm.h"


def require(ok, message):
    if not ok:
        raise SystemExit(message)


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def pinned(repo, commit):
    require(git(repo, "rev-parse", "HEAD") == commit, f"Unexpected revision: {repo}")
    require(not git(repo, "status", "--porcelain", "--untracked-files=no"),
            f"Tracked source modified: {repo}")


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def nonempty(path):
    require(path.is_file() and path.stat().st_size > 0, f"Missing file: {path}")


def save(path, report):
    path.write_text(json.dumps(report, indent=2) + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kernel", required=True, type=Path)
    p.add_argument("--xiaomi-display", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path, help="New diagnostic output directory")
    p.add_argument("--build", action="store_true")
    p.add_argument("--kernel-out", type=Path)
    p.add_argument("--baseline-evidence", type=Path)
    p.add_argument("--mmrm-symvers", type=Path)
    p.add_argument("--clang-root", type=Path)
    a = p.parse_args()
    kernel, vendor, out = (v.resolve() for v in (a.kernel, a.xiaomi_display, a.out))
    for root in (kernel, vendor):
        require(root != out and root not in out.parents,
                "Keep diagnostic output outside both source trees")
    pinned(kernel, KERNEL)
    pinned(vendor, XIAOMI)
    for path, blob in BLOBS.items():
        require(git(vendor, "hash-object", str(vendor / path)) == blob,
                f"Xiaomi source mismatch: {path}")
    require(git(kernel, "hash-object", str(kernel / BASE / SDE))
            == "2b1dd7a0ee0b5ccb9b7dda58cfc3a8fe4c44ffa7", "PE SDE UAPI drift")
    require(git(kernel, "hash-object", str(kernel / BASE / "msm/mondrian/mondrian_fod.c"))
            == "84256f4a9e5b32690f16f9b2810249693d0662b0", "PE FOD drift")
    require((vendor / "config/gki_waipiodisp.conf").read_bytes()
            == (kernel / BASE / "config/gki_waipiodisp.conf").read_bytes(),
            "WAIPIO profile mismatch")
    old = (vendor / SDE).read_text()
    pe = (kernel / BASE / SDE).read_text()
    require(re.search(r"#define SDE_MAX_DS_COUNT\s+2\b", old)
            and re.search(r"#define SDE_MAX_DS_COUNT\s+4\b", pe),
            "Re-audit SDE scaler layout")
    require("merge_mode" not in old and "merge_mode" in pe
            and "roi_feature_flags" not in old and "roi_feature_flags" in pe
            and "spr_roi" not in old and "spr_roi" in pe,
            "Re-audit SDE UAPI differences")
    require("0x4D31314100420200" in
            (vendor / "msm/mi_disp/mi_panel_id.h").read_text(), "M11A ID missing")
    require("#include <misc/isl97900_led.h>" in
            (vendor / "msm/dsi/dsi_panel.c").read_text(), "Re-audit LED dependency")
    require(not (kernel / "include/misc/isl97900_led.h").exists(),
            "Re-audit newly available LED header")
    out.mkdir(parents=True, exist_ok=False)
    report = {
        "device": "mondrian", "soc": "SM8475", "android_base": "AOSP 17",
        "kernel_commit": KERNEL, "xiaomi_display_commit": XIAOMI,
        "baseline_ci_run": 45431700528, "source_blobs": BLOBS,
        "waipio_profile_equal": True, "m11a_id_present": True,
        "sde_uapi_layout_differs": True,
        "missing_oem_led_header": "include/misc/isl97900_led.h",
        "candidate_module_compiled": False, "hardware_validated": False,
        "product_driver_selected": False, "production_images_ready": False,
    }
    save(out / "source-evidence.json", report)
    print("Source audit complete; Xiaomi Display remains an unselected candidate.")
    if not a.build:
        return
    require(all((a.kernel_out, a.baseline_evidence, a.mmrm_symvers, a.clang_root)),
            "--build requires kernel output, baseline evidence, MMRM symbols, Clang")
    ko, evidence, mmrm, clang = (v.resolve() for v in
        (a.kernel_out, a.baseline_evidence, a.mmrm_symvers, a.clang_root))
    for root in (kernel, vendor, ko):
        require(root != out and root not in out.parents,
                "Build diagnostic output must remain separate")
    pinned(clang, CLANG)
    for f in (ko / ".config", ko / "vmlinux", ko / "Module.symvers",
              ko / "include/generated/autoconf.h", mmrm, evidence):
        nonempty(f)
    baseline = json.loads(evidence.read_text())
    require(baseline.get("kernel_commit") == KERNEL
            and baseline.get("module_compile") is True
            and baseline.get("module") == "msm_drm.ko"
            and baseline.get("kernel_config_sha256") == sha256(ko / ".config")
            and baseline.get("module_symvers_sha256") == sha256(ko / "Module.symvers"),
            "Kernel output differs from the successful baseline")
    # MMRM symbols must come from the same prepared build; their hash is
    # recorded, but this input alone cannot establish MMRM build provenance.
    config = (ko / ".config").read_text()
    require("CONFIG_ARCH_WAIPIO=y" in config
            and not re.search(r"^CONFIG_DRM_MSM=[ym]$", config, re.M),
            "Incorrect WAIPIO or conflicting in-tree DRM config")
    toolchain = clang / "clang-r614150/bin"
    nonempty(toolchain / "clang")
    env = os.environ.copy()
    for key in ("MAKEFLAGS", "MFLAGS", "KBUILD_MODPOST_WARN", "KBUILD_MODPOST_NOFINAL",
                "KBUILD_EXTRA_SYMBOLS", "KCFLAGS", "KCPPFLAGS", "CFLAGS_MODULE"):
        env.pop(key, None)
    env.update(PATH=str(toolchain) + os.pathsep + env["PATH"],
               ARCH="arm64", LLVM="1", LLVM_IAS="1", CROSS_COMPILE="aarch64-linux-gnu-")
    report["mmrm_symvers_sha256"] = sha256(mmrm)
    report["baseline_config_sha256"] = sha256(ko / ".config")
    report["baseline_symvers_sha256"] = sha256(ko / "Module.symvers")
    report["candidate_compile_attempted"] = True
    save(out / "source-evidence.json", report)
    with tempfile.TemporaryDirectory(prefix="xiaomi-display-", dir=out) as tmp:
        candidate = Path(tmp)
        # Export only the pinned tracked source. Never write into production Display.
        archive = candidate / "source.tar"
        subprocess.run(["git", "-C", str(vendor), "archive", "--format=tar",
                        "-o", str(archive), XIAOMI], check=True)
        display = candidate / "display"
        display.mkdir()
        with tarfile.open(archive) as tar:
            tar.extractall(display, filter="data")
        cmd = ["make", "-C", str(kernel), f"O={ko}", "-j3",
               f"M={display / 'msm'}", f"DISPLAY_ROOT={display}",
               f"KERNEL_SRC={kernel}", f"KERNEL_ROOT={kernel}", f"OUT={ko}",
               f"KBUILD_EXTRA_SYMBOLS={mmrm}", "KBUILD_MODPOST_WARN=",
               "KBUILD_MODPOST_NOFINAL=", "modules"]
        with (out / "candidate-build.log").open("w") as log:
            result = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
        require(result.returncode == 0, "Candidate compile failed; inspect candidate-build.log")
        module = display / "msm/msm_drm.ko"
        nonempty(module)
        validator = Path(__file__).resolve().with_name("verify_external_module_abi.py")
        subprocess.run(["python3", str(validator), "--kernel", str(kernel),
                        "--kernel-out", str(ko), "--module", str(module),
                        "--expected-kernel-commit", KERNEL,
                        "--out", str(out / "candidate-abi-evidence.json")],
                       env=env, check=True)
        report["candidate_module_compiled"] = True
        report["candidate_module_sha256"] = sha256(module)
        save(out / "source-evidence.json", report)
    print("Candidate compile/ELF/vermagic checked; SDE userspace ABI and runtime NOT qualified.")


if __name__ == "__main__":
    main()
