# Mondrian Audio and Video integrated diagnostic build

PE-Reborn AOSP 17, Xiaomi OEM Linux 5.10.81 at `c67ed74ffe11bd2133b560078a20cf0c04e18d97`.
Preserves the successful three-repository Display/Camera/WLAN/MMRM baseline.
The existing bringup CI now attempts both real external drivers with LLVM 23
and the same OEM configuration, vmlinux and Module.symvers.

- Audio: original Xiaomi `MiCode/vendor_qcom_opensource_audio-kernel`, **ziyi-s-oss**
  `8b1c8d3486a7ac3349d1422201a4436ad852fcb1` is now the only audio gitlink in the
  diagnostic BSP build. Xiaomi WAIPIO/taro ASoC with Awinic AW882xx is checked against
  mondrian I2C 0x34/0x35 and MI2S2 factory pinout. The original Xiaomi Kbuild and
  7 source blobs are pinned, with only 2 reviewed LLVM23 QoS prototype fixes.
  No unrelated donor DTS, FM route, FM HAL or ROM source is introduced.
- Video: official Qualcomm CodeLinaro video-driver, VIDEO.LA.2.0.r1-10200-WAIPIO.0,
  `707fcdb08626667663d13cfceeb2d9dfe92893e3`, same release as the present MMRM driver.
  WAIPIO/IRIS2 is selected for this external build; kernel config unchanged.
- Both source pins are actual Gitlinks; original Git blob IDs are checked.
  Compiled media modules are checked by the existing AArch64/vermagic gate
  and included in the shared dependency closure. No changes to display, camera,
  device trees, default branches or release manifest.
- Diagnostic only: no vendor_dlkm load list, HAL/firmware or hardware approval,
  no donor speaker enabled and no FM support.
- Status: first integrated CI required; fix actual compile or modpost errors
  before moving on to Camera/OIS.

## LLVM23 compilation correction

Historical builds with the previous comparison-only Audio revision, #44962227027 / #44962231537, both reached the same
manufacturer Audio failure after successfully compiling the existing kernel,
WLAN, MMRM, Display and Camera. In asoc/msm_common.c:602 and :633,
LLVM23 rejects two static QoS functions declared with empty parameter lists.
Both have exactly one existing no-argument caller. The reviewed byte-exact
adaptation changes only those two definitions to (void), with original Git
blob verification, exact diff checks and regression tests. The function bodies,
callers, power behavior and warning settings remain untouched.

The build now uses make -k and captures both Audio and VIDC compiler results,
so a failure in one driver does not prevent diagnostics in the other. Either
nonzero status stops the job before staging and any successful qualification.
No compiler warning is suppressed. Compilation and hardware remain pending.

## Qualcomm VIDC LLVM23 declaration correction

Both CI runs #44975428940 and #44975433568 passed Audio compilation (34
modules including AW882xx and machine_dlkm). VIDC alone returned 2.
The complete diagnostic logs contain 17 distinct declaration failures:
14 implicit-int predicates in msm_vidc_driver.h, two implicit-int static
functions (DPB allocation and CSC coefficients), and one empty-parameter
DebugFS definition whose existing header already declares (void).
Use explicit int to preserve the original implicit return type and error
codes, and (void) for DebugFS. Verify the exact original Git blobs of all
four edited files and the unchanged debug header; require precisely 17
changed lines. No changes to function bodies, firmware, device tree,
compiler warning gates, kernel configuration or Audio code. Integrated
module staging and physical hardware remain unqualified until verified.

## VIDC MMRM const-field initialization (22 November 2026)

Both full coherent runs [#44977003402](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/44977003402) and [#44977007875](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/44977007875) compiled the original 34 audio modules and all VIDC translation units except `venus_hfi.c`. Clang 23's warning gate reports `-Wdefault-const-init-field-unsafe` at line 1509 because Qualcomm's MMRM descriptor has a `const char name[]` field and was declared without an initializer.

The existing exact-source adaptation now initializes the whole descriptor with `{ 0 }` before the original clock-domain/ID/name/clock/priority/notifier assignments and MMRM registration. No MMRM API, kernel header, function body, clock name, or compile warning is removed. Strict byte-exact source SHA verification now covers 18 changes in five VIDC source files, including the original Qualcomm `venus_hfi.c` blob. Hardware/production readiness remains unclaimed until full CI and device validation.

## Device-specific Audio source decision (23 November 2026)

The manufacturer mondrian audio-overlay has `qcom,wcn-bt` but no
`qcom,wcn-btfm` or `qcom,cdc-dmic67-gpios`. MiCode Ziyi WAIPIO lacks the
extra BT/FM PCM route and GPIO DMIC6/7 processing present in the earlier
donor branch. LineageOS mondrian `mixer_paths_waipio_mtp.xml` is used
only as read-only comparison. The selected main source and its AW882xx
modules now come from the pinned original Xiaomi Ziyi commit; the former
duplicate Ziyi candidate compilation was removed. Retain unqualified
Audio HAL/DSP/firmware/runtime flags until full LLVM23 Image, modules,
ABI and dependency closure succeed. Do not enable FM radio.
