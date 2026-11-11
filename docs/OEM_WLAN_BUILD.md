# Qualcomm external module development for mondrian

The primary source is the pinned Xiaomi manufacturer kernel. This repository links the actual manufacturer WLAN source as a versioned Git submodule (MiCode/vendor_qcom_opensource_wlan, mondrian-s-oss commit 334e5943b77af50dfd1fc7eb872a26b79ae5119f). The prior contract and module list are preserved. No sources from LineageOS are included.

Run git submodule update --init --recursive and python3 tools/verify_oem_wlan.py. The new CI compiles the same OEM Linux 5.10.81 kernel and module symbol table using the pinned Google Android Clang r614150, then attempts a strict build of Xiaomi QCACLD QCA6490. A pass of the source test is not a pass of the external-module compile. Display, Camera, MMRM, Audio and mobile networking sources remain pending release-matched Qualcomm revisions.

We do not package modules into Android 17 vendor_dlkm before actual Module.symvers/vermagic/dependency and firmware validation. No FM radio or unrelated-device build target is selected.

## Additional compiler compatibility correction (2026-11-11)

In [run #43016121681](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/43016121681) the full OEM kernel and Qualcomm MMRM module built successfully. Xiaomi QCACLD stopped on `target_if_get_ctx()` in `qca-wifi-host-cmn/target_if/core/src/target_if_main.c`: Clang23 rejects an old-style empty-argument C function definition with `-Wstrict-prototypes`. The corresponding original `target_if.h` already declares `target_if_get_ctx(void)`. This change makes the definition match the declaration; it does not alter arguments, return type, function behavior, calling convention, or KMI.

The single older `parser_api.h` array bound correction is retained. Both edits are verified against source Git blob SHA-1 before being applied to a disposable vendor checkout. No source is copied from LineageOS, no warning suppression and no changes to the OEM kernel.

## Additional Clang23 enumeration type mismatch — htt_h2t.c

The latest exact-OEM-kernel external WLAN CI [#43018421487](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/43018421487) passed the full OEM kernel and Qualcomm MMRM module but stopped compiling the original Xiaomi QCACLD at `core/dp/htt/htt_h2t.c` lines 631 and 647. The `htt_h2t_rx_ring_cfg_msg_hl` function returns `QDF_STATUS` but previously returned the incompatible `A_STATUS` enum constant `A_ERROR` in two allocation failure paths. The *same source file already uses* `QDF_STATUS_E_FAILURE` for identical failure paths in other `QDF_STATUS` functions. Preserve the complete error branches and replace **only those two return values** with `QDF_STATUS_E_FAILURE`. The patch verifier checks the pinned Xiaomi blob `b85f7c7a...` and exact count of two; no blanket `-Wno-error`, no unrelated code, and no kernel changes.
