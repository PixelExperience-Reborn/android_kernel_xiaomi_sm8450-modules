# PE-Reborn AOSP 17 — mondrian OEM three-repository integration

This report is the single source of truth for **the diagnostic integration
scope** of the current independently developed mondrian OEM BSP. The user
targets POCO F5 Pro / Redmi K60 (SM8475) only. LineageOS is an analysis
reference **only**; no Lineage driver, DTS or ROM base is selected.

## Exact sources used together

| Source | Pinned revision |
| --- | --- |
| Kernel: `PixelExperience-Reborn/android_kernel_xiaomi_sm8450` | `c9c67329b427ba21dea10d7a6e404ff422f86c1a` |
| Modules: `PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules` | current active bringup PR head, recorded by the CI run |
| Devicetrees: `PixelExperience-Reborn/android_kernel_xiaomi_sm8450-devicetrees` | `07ab1faceb058e895c8d3ec01ec37e4e7657935c` |
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
| Camera | OEM `camera.ko`/`cameralog.ko`, CCI0/1, six CSIPHY, CPAS, WL2866D and PM8350C source; compile and kernel ABI passes | Exact mondrian sensors, CSI routes, EEPROM, autofocus, camera power sequences, PM8350C physical channel and Camera HAL/hardware tests |
| Audio | Original mondrian I2C15 AW882xx pair (0x34/0x35), MI2S2 pins and TLMM mapping verified in **all three compiled OEM Cape DTBs** | Compatible source-based Audio kernel/codec driver, DSP/ALSA calibration, HAL and real speaker/mic/receiver/call tests |
| Display M11A | Qualcomm SDE/DSI and OEM display modules compile | Exact original panel description/DCS/DSC, stable LHBM state transitions and physical display test |
| UDFPS/Goodix | OEM Goodix SPI and FOD kernel modules, verified original DTS binding/firmware names | LHBM coordination, panel notifier and Goodix runtime tests, AOSP17 fingerprint HAL |
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

Next after green three-repo CI: complete missing native Camera hardware
identification and original source-based driver/ABI mapping, then
Audio kernel/codec, M11A/LHBM, UDFPS/Goodix, and final image/device
tests. Avoid repeating already confirmed Camera controller or Kernel
compilation stages without a reproducible regression.
