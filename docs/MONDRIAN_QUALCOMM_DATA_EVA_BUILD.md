# Qualcomm IPA/GSI, RMNET and EVA for mondrian

`tools/build_mondrian_data_eva.sh` compiles the selected WAIPIO 11900 sources
against the same OEM 5.10.81 Image, configuration and `Module.symvers` as the
rest of the coherent build, with the pinned Google LLVM 23 and without any
warning suppression or `KBUILD_MODPOST_WARN`.

Order: `verify_qualcomm_data_eva_sources.py` (gitlink, commit, original
blobs) → `apply_qualcomm_patch_series.py` (SHA-256 of each patch, whole
series `git apply --check` first, only the listed files may change) →
`make M=...` for dataipa, datarmnet, the seven datarmnet-ext modules and EVA
→ presence of all 15 modules and their DT `compatible` strings → the shared
`verify_external_module_abi.py` ELF/vermagic/MODPOST check. The modules are
then appended to the existing dependency-closure step (depmod + modprobe
dry run) as additional roots.

Every datarmnet-ext module links to `rmnet_core`. `rmnet_perf` also uses
`rmnet_perf_ingress_hook1`, exported by `rmnet_shs`; Qualcomm's
`perf/Makefile` and `perf/Android.mk` declare that link, so `rmnet_shs` is
built first and its `Module.symvers` is passed to `rmnet_perf`. A test reads
those Qualcomm files and fails if the build order or symbols disagree.

MODPOST only checks unresolved symbols when the kernel's own
`Module.symvers` exists; without it, it prints "Unresolved symbol check will
be entirely skipped". Local checks therefore use the `Module.symvers` and
`.config` from the coherent CI run, never a bare `modules_prepare` tree.

## Reviewed patches

| Patch | Why |
|---|---|
| `qualcomm-dataipa/0001-external-module-build-paths.patch` | The WAIPIO block of the Kbuild hard-codes `$(srctree)/../../vendor/qcom/opensource/dataipa`, the Android tree layout. It now uses `DATAIPA_ROOT`, defaulting to that same path. Trace headers use `TRACE_INCLUDE_PATH .` with the include directories the Kbuild already adds. |
| `qualcomm-dataipa/0002-llvm23-prototypes-and-explicit-enum-casts.patch` | Four definitions get `(void)` (LLVM 23 `-Wstrict-prototypes`). Two implicit QMI→IPA enum conversions in `rmnet_ipa.c` become explicit casts. The numeric values differ between the two enums (QMI IPv4 is 1, `IPA_IP_v4` is 0), so the casts deliberately keep the original numeric behaviour instead of remapping it. |
| `qualcomm-datarmnet/0001-external-module-trace-include-path.patch` | Same Android-tree trace path, replaced by `.` plus `-I$(src)`. |
| `qualcomm-eva/0001-llvm23-va-minidump-prototype.patch` | `cvp_register_va_md_region()` definition matches its own `(void)` declaration in `cvp_dump.h`. |

`datarmnet-ext` builds unchanged. Function bodies, Kconfig and compiler
warnings are not changed.

## Video and MMRM

Video and MMRM follow the same release: `8608fb2` and `69e304b` from
`VIDEO.LA.2.0.r1-03100-WAIPIO.0`. Both compile with LLVM 23; video keeps the
existing 18 reviewed declaration fixes in
`tools/apply_qualcomm_vidc_clang23_fix.py`, now bound to `8608fb2`.

The MMRM driver of this release accepts exactly five voltage corners
(`LOW_SVS, SVS, SVS_L1, NOM, TURBO`) and indexes the DT arrays by that order.
The only public Qualcomm MMRM device trees (2024+) describe WAIPIO with six or
eight corners and WAIPIO coefficients, not the SM8475/CAPE values. Feeding
them to this driver would shift the corners and miscompute peak current.
Therefore no MMRM DT node is added yet. Every MMRM client (Display, Camera,
Video, EVA) checks `mmrm_client_check_scaling_supported()` and falls back to
plain clock control when MMRM is absent, so this is a safe, documented gap
until CAPE coefficients from an original source are available.

## Pending

KMI and MODPOST against the final Full LTO Image in CI, modem/IPA firmware,
a real data call, tethering offload and EVA runtime on a physical mondrian.
