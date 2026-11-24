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

- module-contract.yml owns regular source validation (including recursive
  submodules). Same-repository pull requests use the existing push check;
  fork pull requests run the source gate on GitHub-hosted runners.
- Standalone WLAN is manual-only. CodeLinaro source discovery is path-filtered.
- The coherent workflow supports manual scope=display or scope=full-bsp.
  Its tightly restricted, explicit trusted bringup push mechanism remains
  available because workflow_dispatch may be unavailable before workflows
  exist on the default branch. A normal push never requests ServerHive.
- Display mode validates the reviewable Xiaomi patch series before allocating
  ServerHive and compiles the candidate with the same freshly built vmlinux,
  Module.symvers and official MMRM as the Qualcomm baseline in that job.
  No cross-host configuration replay or temporary artifact dependency remains.
- Candidate output is diagnostic only. It does not replace the Qualcomm
  production driver or establish userspace ABI, Goodix, LHBM or hardware readiness.

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

The current active OEM kernel is `2efda4cf1afa2a7098d5abd4806769903e181f73` in both workflow checkouts,
the WLAN dependency closure and the modules candidate manifest.
The generic external-module ABI verifier requires an explicit expected
kernel SHA rather than defaulting to obsolete `2466406b9beac724960b0c88e6e794421d0466e7`.
Previously successful build #43088150435 and its original pinned
inputs remain historical evidence, not proof of the new hardening
configuration or full Audio/Video integration. Current ABI and boot
approval flags stay false until a complete linked Image/modules and
reproducible diagnostic artifacts exist.
