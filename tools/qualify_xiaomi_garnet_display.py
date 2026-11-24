#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Isolated Xiaomi garnet-t-oss display candidate; never selects a product driver.

Run with three local Git checkouts: pinned PE kernel, Xiaomi candidate and
Google Clang, plus the pinned Xiaomi display DT for builds. With --build, also supply the completed Kernel #31 output,
its display-abi-evidence.json, and MMRM Module.symvers from the same build.
Source-only is the default. No full kernel build, flashing, or packaging.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
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
DISPLAY_DT = "ab5bc7b921d3d4072ce11eecfde984382e3ec695"
DISPLAY_DT_BLOB = "8c955d4cb960935631a3e6efcf70bf3e3f2c2573"
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


def replace_once(text, old, new):
    require(text.count(old) == 1, "Candidate patch context changed: " + old[:80])
    return text.replace(old, new, 1)


def adapt_optional_led(text):
    """Keep actual LED support when reachable; reject absent hardware explicitly."""
    text = replace_once(text, "#include <misc/isl97900_led.h>",
                        "#if IS_REACHABLE(CONFIG_ISL97900_LED)\n"
                        "#include <misc/isl97900_led.h>\n#endif")
    old = ("\tcase DSI_BACKLIGHT_I2C:\n"
           "\t\tif (panel->rgb_left_led_node)\n"
           "\t\t\tisl97900_led_event(panel->rgb_left_led_node,\n"
           "\t\t\t\t\t0, bl_lvl);\n\n"
           "\t\tif (panel->rgb_right_led_node)\n"
           "\t\t\tisl97900_led_event(panel->rgb_right_led_node,\n"
           "\t\t\t\t\t0, bl_lvl);\n"
           "\t\tbreak;")
    new = old.replace("\n\t\tif (panel->rgb_left_led_node)",
                      "\n#if IS_REACHABLE(CONFIG_ISL97900_LED)\n"
                      "\t\tif (panel->rgb_left_led_node)", 1)
    new = new.replace("\n\t\tbreak;",
                      "\n#else\n\t\treturn -EOPNOTSUPP;\n#endif\n\t\tbreak;")
    text = replace_once(text, old, new)
    # Fail registration, not just parsing: the original caller ignores most
    # parse errors. An unexpected I2C panel must not appear operational.
    start = text.index("static int dsi_panel_bl_register(struct dsi_panel *panel)")
    end = text.index("static void dsi_panel_pwm_unregister", start)
    register = replace_once(text[start:end],
                            "\tcase DSI_BACKLIGHT_I2C:\n\t\tbreak;",
                            "\tcase DSI_BACKLIGHT_I2C:\n"
                            "#if !IS_REACHABLE(CONFIG_ISL97900_LED)\n"
                            "\t\treturn -EOPNOTSUPP;\n#endif\n\t\tbreak;")
    return text[:start] + register + text[end:]


def verify_mondrian_dcs(dt):
    pinned(dt, DISPLAY_DT)
    path = dt / "display/mondrian-sde-display-mtp.dtsi"
    require(git(dt, "hash-object", str(path)) == DISPLAY_DT_BLOB,
            "Re-audit manufacturer mondrian display DTS")
    source = path.read_text()
    blocks = re.findall(r"&dsi_m11a_42_02_0a_dsc_cmd\s*\{([^{}]*)\}", source)
    require(any('qcom,mdss-dsi-bl-pmic-control-type = "bl_ctrl_dcs";' in b
                for b in blocks), "M11A DCS backlight not proven")
    require("bl_ctrl_i2c" not in source and "qcom,panel-rgb-" not in source,
            "Re-audit I2C LED requirement")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kernel", required=True, type=Path)
    p.add_argument("--xiaomi-display", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path, help="New diagnostic output directory")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--build", action="store_true")
    mode.add_argument("--objects-only", action="store_true",
                      help="Compile candidate dsi_panel.o only, with modules_prepare output")
    p.add_argument("--xiaomi-display-dt", type=Path)
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
    if not (a.build or a.objects_only):
        return
    require(all((a.kernel_out, a.clang_root, a.xiaomi_display_dt)),
            "Compilation requires kernel output, pinned Clang and Xiaomi display DT")
    verify_mondrian_dcs(a.xiaomi_display_dt.resolve())
    report["manufacturer_m11a_dcs_backlight"] = True
    report["xiaomi_display_dt_commit"] = DISPLAY_DT
    ko, clang = (v.resolve() for v in (a.kernel_out, a.clang_root))
    for root in (kernel, vendor, ko):
        require(root != out and root not in out.parents,
                "Build diagnostic output must remain separate")
    pinned(clang, CLANG)
    for f in (ko / ".config", ko / "include/generated/autoconf.h"):
        nonempty(f)
    if a.build:
        require(all((a.baseline_evidence, a.mmrm_symvers)),
                "--build requires baseline evidence and MMRM symbols")
        evidence, mmrm = (v.resolve() for v in (a.baseline_evidence, a.mmrm_symvers))
        for f in (ko / "vmlinux", ko / "Module.symvers", mmrm, evidence):
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
    require(not re.search(r"^CONFIG_ISL97900_LED=[ym]$", config, re.M),
            "Unexpected LED configuration; re-audit actual driver and header")
    report["prepared_config_sha256"] = sha256(ko / ".config")
    if a.build:
        report["mmrm_symvers_sha256"] = sha256(mmrm)
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
        panel = display / "msm/dsi/dsi_panel.c"
        panel.write_text(adapt_optional_led(panel.read_text()))
        kbuild = display / "msm/Kbuild"
        kbuild.write_text(replace_once(kbuild.read_text(),
                                       "-Iinclude/linux \\", "-I$(KERNEL_SRC)/include/linux \\")
                          .replace("-Iinclude/linux/drm\n", "-I$(KERNEL_SRC)/include/linux/drm\n", 1))
        report["adapted_panel_sha256"] = sha256(panel)
        report["adapted_kbuild_sha256"] = sha256(kbuild)
        save(out / "source-evidence.json", report)
        cmd = ["make", "-C", str(kernel), f"O={ko}", "-j3",
               f"M={display / 'msm'}", f"DISPLAY_ROOT={display}",
               f"KERNEL_SRC={kernel}", f"KERNEL_ROOT={kernel}", f"OUT={ko}",
               "KBUILD_MODPOST_WARN=", "KBUILD_MODPOST_NOFINAL="]
        if a.objects_only:
            cmd += ["dsi/dsi_panel.o"]
        else:
            cmd += [f"KBUILD_EXTRA_SYMBOLS={mmrm}", "modules"]
        with (out / "candidate-build.log").open("w") as log:
            result = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
        require(result.returncode == 0, "Candidate compile failed; inspect candidate-build.log")
        if a.objects_only:
            obj = display / "msm/dsi/dsi_panel.o"
            nonempty(obj)
            shutil.copy2(obj, out / "dsi_panel.o")
            report["candidate_dsi_panel_object_compiled"] = True
            report["candidate_object_sha256"] = sha256(obj)
            save(out / "source-evidence.json", report)
            print("Candidate DSI panel object compiled; full module and ABI NOT qualified.")
            return
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
        shutil.copy2(module, out / "candidate-msm_drm.ko")
        save(out / "source-evidence.json", report)
    print("Candidate compile/ELF/vermagic checked; SDE userspace ABI and runtime NOT qualified.")


if __name__ == "__main__":
    main()
