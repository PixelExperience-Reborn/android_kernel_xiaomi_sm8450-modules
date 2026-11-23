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
