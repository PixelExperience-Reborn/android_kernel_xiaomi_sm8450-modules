# Reproducible Ubuntu tool installation for mondrian OEM CI

The full AOSP17 PE-Reborn `mondrian` external-module build is pinned to our Xiaomi OEM Linux 5.10 kernel at `2466406b9beac724960b0c88e6e794421d0466e7` and Google Android LLVM23 `clang-r614150`.

## Resolved CI infrastructure failure

GitHub Actions [run #43039341050](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/43039341050) failed before compiling: the Ubuntu runner's `mirror+file` list preferred `azure.archive.ubuntu.com`, which failed DNS and prevented installing `libelf-dev`, `dwarves`, `pahole`, and the AArch64 binutils. Blind `apt-get update` retries against the same Azure mirror are not sufficient.

`tools/install_ci_prerequisites.sh` now:

- Uses the exact Ubuntu **24.04 (noble)** package set already required by our kernel. Skips network access only if **all** packages are already installed.
- Uses isolated, temporary APT package indexes and explicit Ubuntu repository URLs, completely bypassing the runner's Azure mirror selection. Official `archive.ubuntu.com` and `security.ubuntu.com` are first; a kernel.org Ubuntu mirror is the fallback.
- Checks package signatures against the **existing Ubuntu archive signing key**; never uses `trusted=yes`, ignores signature errors or changes the global resolver.
- Enforces per-request timeouts, one limited retry and hard total timeouts per mirror. Fails clearly after both mirrors rather than waiting indefinitely.
- Verifies `pahole`, `modinfo`, `aarch64-linux-gnu-ld` and other required tools before continuing, and records installed package versions.

The source/PR job performs only shell syntax and source URL checks; **it is not a successful `.ko` build**. Only the full push job can qualify the external MMRM and Xiaomi QCACLD drivers by actually compiling them against `Module.symvers`.

The upstream Xiaomi and Qualcomm source submodules remain pinned and unmodified. Android17 packaging, firmware availability and hardware boot remain unqualified independently of this infrastructure change.
