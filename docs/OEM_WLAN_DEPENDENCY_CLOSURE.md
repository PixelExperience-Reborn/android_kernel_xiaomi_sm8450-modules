# Verified Xiaomi WLAN runtime module dependency closure

The full exact-kernel OEM + Qualcomm MMRM + Xiaomi WLAN [build #43088150435](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/43088150435) passed both external module Kbuild and the strict kernel `vermagic` gate, under Google LLVM23. This does not establish vendor_DLKM or hardware functionality.

## New evidence from actual compiled WLAN `modinfo`

`qca_cld3_qca6490.ko` depends on these six kernel modules:

- `icnss2.ko`
- `mi_cnss_statistic.ko`
- `cfg80211.ko`
- `cnss_prealloc.ko`
- `cnss_nl.ko`
- `cnss_utils.ko`

The selected Xiaomi OEM kernel at `2466406b9beac724960b0c88e6e794421d0466e7` contains the full source and Makefile for each module and has all six configuration symbols set to `m` in `arch/arm64/configs/vendor/mondrian_GKI.config`. The OEM reference `modules.list.msm.mondrian` includes `cfg80211.ko` but omits the other five. **It is not safe to use that list unchanged** for our new AOSP 17 product.

## Strict diagnostic dependency stage

The new `tools/stage_mondrian_wlan_kmi.py` runs only after a full kernel, MMRM and WLAN compile. It discovers the actual compiled in-tree `.ko` outputs; rejects missing required dependencies, duplicate module names and dependency cycles; copies the transitive closure to a temporary staged `lib/modules/<kernelrelease>`; runs `depmod` and a `modprobe --show-depends` dry-run; and emits SHA256 hashes and a reproducible dependency order. These are diagnostic inputs for a later `vendor_dlkm` or `vendor_boot` decision, **not shipping images**.

The final placement, module load trigger, filesystem image, firmware, SELinux labels and runtime modprobe are separate release gates. Do not copy anything from a LineageOS module tree. No FM radio and no unrelated hardware targets.
