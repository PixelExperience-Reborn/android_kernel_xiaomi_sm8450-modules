# Security configuration qualification for OEM mondrian Linux 5.10.81

The actual successful GitHub Actions kernel run #44947056081
(commit c67ed74ffe11bd2133b560078a20cf0c04e18d97)
published `mondrian-out/.config` in its original archived artifact.
It contains:
- `CONFIG_CC_IS_CLANG=y`, `CONFIG_ARM64_MTE=y`, and
  `CONFIG_HAVE_ARCH_KASAN_HW_TAGS=y`, proving prerequisite support.
- `CONFIG_KASAN=y`, `CONFIG_KASAN_GENERIC=y`,
  `# CONFIG_KASAN_HW_TAGS is not set`;
- `CONFIG_LTO_NONE=y`, `# CONFIG_SHADOW_CALL_STACK is not set`,
  and CFI_CLANG not enabled.
The matching build log compiles mm/kasan/generic.o and report_generic.o.
Thus the previous compiler/ABI success did **not** prove GKI hardening.

The source GKI defconfig already requests
`KASAN_HW_TAGS, LTO_CLANG_FULL, CFI_CLANG, SHADOW_CALL_STACK`.
But `lib/Kconfig.kasan` defaults to generic KASAN if the mode
cannot be maintained; generic KASAN conflicts with `HAS_LTO_CLANG`
(arch/Kconfig), which also prevents `CFI_CLANG`.
It is not sufficient to blindly rerun gki_defconfig twice:
the exact final .config must be asserted after vendor fragments.

The reviewed supplementary fragment `tools/config/mondrian_gki_hardening.config`
requests the same original GKI modes without modifying manufacturer
hardware fragments. All three current pinned kernel ABI workflows
apply the fragment after OEM config and rerun olddefconfig.
Then the new strict verifier checks the actual final settings;
on mismatch it fails closed and prints prerequisite flags rather than
removing CFI, SCS, modules, or Qualcomm drivers.

This is a **diagnostic** change until LLVM23 kernel + external module
compile succeeds with the resulting GKI hardening. A successful
compiler run alone cannot prove hardware support, runtime security,
device boot, or product OTA readiness.

## Follow-up CI evidence: 22 November 2026

The strengthened configuration **did** pass in GitHub Actions run
`#45077075060`: the evaluated `.config` retained HW-tag KASAN,
Full LTO, CFI and SCS; the build log compiled `mm/kasan/hw_tags.o`,
`kernel/cfi.o` and `kernel/scs.o`, not the old generic KASAN object.
The runner then received a shutdown signal at `LTO vmlinux.o`
(exit 143). This does not establish an LLVM compiler defect, OOM,
or a successful `vmlinux` link. Preserve all security settings and
require a completed kernel + external modules build before qualification.
Both full CI paths now record memory, disk and swap information before
starting the LTO link to help diagnose future environmental failures.

## CI resource isolation after repeated LTO termination (23 November 2026)

Two automatic full kernel links were previously launched by separate
WLAN/coherent workflows on different GitHub virtual machines. PR coherent
qualification is now the only automatic full OEM link; independent full
WLAN compilation is manual opt-in. This avoids redundant CI, not a shared
RAM conflict. Both full link paths retain HW-tag KASAN, Full LTO, CFI and
SCS, use `make -j2`, a bounded optional 3 GiB swap backed by verified free
SSD space, and a low-overhead RSS/memory monitor. No OOM assumption is
made until a completed runner log supplies conclusive diagnostics.
