# PE-Reborn AOSP 17 — mondrian OEM three-repository integration

This report is the single source of truth for **the diagnostic integration
scope** of the current independently developed mondrian OEM BSP. The user
targets POCO F5 Pro / Redmi K60 (SM8475) only. LineageOS is an analysis
reference **only**; no Lineage driver, DTS or ROM base is selected.

## Exact sources used together

| Source | Pinned revision |
| --- | --- |
| Kernel: `PixelExperience-Reborn/android_kernel_xiaomi_sm8450` | `c67ed74ffe11bd2133b560078a20cf0c04e18d97` |
| Modules: `PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules` | current active bringup PR head, recorded by the CI run |
| Devicetrees: `PixelExperience-Reborn/android_kernel_xiaomi_sm8450-devicetrees` | `a0db12120fc6c29cc5855d3e1699c9ef73594ee3` |
| Xiaomi original kernel DT: `MiCode/kernel_devicetree` | `34e6cc7d832ed9c655b9d79bc3ffe1d625146b7c` |
| Xiaomi original Camera Kernel | `9ed4ce96d49c0759c6365627113c5f59c2407942` |
| Xiaomi original Cape Camera platform | `a59a63bd498b94074c41357a466874b99aec62a8` |

The main coherent Modules workflow compiles the OEM Image/vmlinux/in-tree
modules using Google LLVM 23, Qualcomm MMRM and Display, Xiaomi WLAN,
Camera and CameraLog, and validates their genuine `Module.symvers`,
ELF/vermagic and dependency closure. The added three-repository gate
then compiles **the same Kernel revision** with the original Xiaomi
Cape/mondrian DTB source and native PE-Reborn Camera platform overlay.
It reads the DTB evidence and records exact hashes. CI must fail if a
foreign board, module, SHA or driver ABI is substituted.

**A green diagnostic build does not equal a bootable ROM.** The combined
report explicitly keeps production `modules.load`, `boot.img`,
`dtbo.img` and runtime flags false.

## Hardware tracks — evidence versus unresolved work

| Track | Source and static build evidence | Still blocking completion |
| --- | --- | --- |
| Camera | Seven factory CamX profiles map to four slots. The ultrawide P24C64F uses WL2866D AVDD1 for power. Its DT node no longer aliases MCLK1 as EEPROM reset. The wide actuator and three rear flash consumers are linked. | Wide AK7323 OIS hookup, sensor ID and EEPROM reads, autofocus, power transitions and flash on physical mondrian |
| Audio | Original mondrian I2C15 AW882xx pair (0x34/0x35), MI2S2 pins and TLMM mapping verified in **all three compiled OEM Cape DTBs** | Compatible source-based Audio kernel/codec driver, DSP/ALSA calibration, HAL and real speaker/mic/receiver/call tests |
| Display M11A | The corrected 90 Hz ON table and the M11A primary panel build on all three boards. At 60/90/120 Hz the normal FOD and seven low-power command streams match both reviewed global firmware entries. The paired driver restores normal brightness on doze exit. | Confirm the installed panel revision, screen initialization and suspend/resume on mondrian. |
| UDFPS/Goodix | OEM Goodix G3S SPI driver and DT binding. The native M11A driver handles the Xiaomi display request and event ABI, per-unit white calibration and the four-frame readiness delay. | Confirm the Android 17 fingerprint service can open the node, then enroll and unlock on the phone with the display on and in doze. |
| WLAN/thermal/boot | Selected OEM critical drivers compiled; Xiaomi QCACLD and Qualcomm MMRM/Display module diagnostic closure | Real RF/thermal transitions; firmware, vendor_boot, vendor_dlkm staging, SELinux and partition/bootloader-aware image creation |

## Implementation rules

1. Work in the ordered source-gated checklist. Finish a compile/error
   before modifying further components. Report concrete commit/CI links.
2. Manufacturer Xiaomi mondrian source is authoritative for board pins,
   sensor rails and SKUs. Use compatible Qualcomm code as a separately
   reviewed input; do not infer hardware from donor devices.
3. No FM radio. No lineage/CLO-based ROM fork, donor DTS, unverified
   feature flags, stubs to silence build errors or image-ready claim.
4. Preserve pristine Xiaomi revision checks and genuine OEM/Qualcomm
   dependencies; use disposable workspaces for audited compiler fixes.
5. Hardware validation must occur on a physical mondrian before release.

Both wide CamX profiles select AK7323 optical stabilization. Identify its
actual board connection and power sequence before adding the wide sensor's
`ois-src` reference. The expected sensor IDs and EEPROM wire addresses
for hardware bring-up are in the camera DT build artifact.
