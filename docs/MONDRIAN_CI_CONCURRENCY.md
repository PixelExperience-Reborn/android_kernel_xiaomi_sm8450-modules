# Mondrian CI ownership: one automatic OEM Full LTO link

Before 23 November 2026, two workflows independently compiled the same pinned
Xiaomi OEM 5.10.81 kernel with HW-tag KASAN, Full LTO, CFI and SCS:

- `oem-coherent-wlan-compile.yml` full PR and push jobs
- `oem-wlan-compile.yml` full push job

This produced competing long-running jobs and redundant checks. GitHub-hosted
runners are **separate virtual machines**; their RAM is not pooled. Therefore
removing concurrent jobs does not by itself fix any Full LTO single-runner
memory exhaustion. Do not claim an OOM without kernel/runner evidence.

## Current automatic path

- `oem-coherent-wlan-compile.yml` runs on the active bringup PR or when
  manually dispatched. Its `source` job gates the comprehensive pinned
  Xiaomi/Qualcomm sources; its only full `external-wlan` job compiles the
  OEM Image, vmlinux, in-tree modules, then Qualcomm MMRM, QCA6490 PCIe
  QCACLD, Display, Xiaomi Camera, Ziyi WAIPIO/AW882xx Audio and VIDC.
  The same exact OEM `.config`, vmlinux and Module.symvers underpin all
  external modules; each ABI and dependency-closure gate remains required.
- `oem-wlan-compile.yml` keeps cheap push/PR source-only checks. Its
  independent full WLAN build is retained as **manual-only**
  `workflow_dispatch`, so it can be used for targeted investigations
  without duplicating every regular PR full build. Do not manually start it
  while the coherent full job is linking the kernel.
- `module-contract.yml` remains source-only. No diagnostic CI result
  is a shipping kernel or Android product image.

## Full LTO memory guard

GitHub standard public Ubuntu runners advertise 4 vCPUs, 16 GiB RAM and
14 GiB SSD. `tools/prepare_mondrian_lto_resources.sh` logs RAM, disk
and swap, optionally enables 3 GiB swap **only** if at least 4 GiB of
additional disk headroom remains, and warns clearly if allocation or
`swapon` fails. It never modifies Kconfig, compiler warnings, kernel
source or any boot image. Kernel build parallelism is bounded to `-j2`;
a lightweight diagnostic loop prints process RSS and headroom every
90 seconds, including when `LTO vmlinux.o` is running.

No proven OOM root cause is asserted yet: the previous GitHub runner
received TERM/143 at Full LTO and another run displayed `Terminated`.
A completed fresh build must determine whether the full LTO link now
finishes; if not, use runner logs and resource telemetry to distinguish
SIGTERM, OOM, disk exhaustion and actual linker errors. Keep all four
requested GKI hardening choices enabled; do not silently switch to ThinLTO
or LTO_NONE to make CI green.

## Full LTO interrupted again on 23 November 2026

PR coherent build [#45087055771](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/45087055771)
reached `LTO vmlinux.o` after compiling in-tree objects. Its visible step
ended with `Terminated`, `Killed` and `The operation was canceled`.
The run did **not** prove a compiler error, actual OOM, completed kernel
link, or external Qualcomm module compatibility. Earlier manually cancelled
jobs #45083328397 and #45083324835 stopped at the same broad kernel stage.
Do not ascribe one cause to all three without runner annotations.

The retry now retains the exact OEM kernel, GKI hardening fragment, Google
LLVM23 toolchain and every module check, but uses the selected `ld.lld`
with its supported `--threads=1` concurrency bound for the Full LTO
kernel link. This changes linker scheduling, **not** the LTO mode,
Kconfig or manufacturer drivers. The monitor also records cgroup
`memory.events` and memory PSI where available. Workflow concurrency
queues subsequent runs instead of cancelling an active Full LTO build.

These safeguards are diagnostic and may not suffice if monolithic Full
LTO exceeds the standard runner memory. If the retry still loses the
runner, use the GitHub cancellation annotations and latest RSS/PSI
measurements; a larger compatible x86_64 runner may be required for
this exact diagnostic build. Do not silently disable Full LTO, CFI,
SCS or HW-tag KASAN just to report SUCCESS.

## Kernel SHA and ABI provenance

The current active OEM kernel is `c67ed74ffe11bd2133b560078a20cf0c04e18d97` in both workflow checkouts,
the WLAN dependency closure and the modules candidate manifest.
The generic external-module ABI verifier requires an explicit expected
kernel SHA rather than defaulting to obsolete `2466406b9beac724960b0c88e6e794421d0466e7`.
Previously successful build #43088150435 and its original pinned
inputs remain historical evidence, not proof of the new hardening
configuration or full Audio/Video integration. Current ABI and boot
approval flags stay false until a complete linked Image/modules and
reproducible diagnostic artifacts exist.
