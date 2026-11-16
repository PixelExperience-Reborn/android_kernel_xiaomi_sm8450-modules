# Xiaomi OEM SM8475 Camera source qualification — PixelExperience-Reborn Android 17

Status: manufacturer-source-only audit. No Camera driver has been compiled or installed by this stage.

Source: Xiaomi MiCode vendor_qcom_opensource_camera-kernel, branch yudi-t-oss,
at immutable commit 9ed4ce96d49c0759c6365627113c5f59c2407942.
Yudi (Xiaomi Pad 6 Max 14) has Snapdragon 8+ Gen 1 / SM8475, like mondrian.
A common SoC does not prove identical camera sensor, actuator, flash, EEPROM,
voltage, secure Camera, firmware or board wiring.

Camera Kbuild from the manufacturer contains Qualcomm CAPE and WAIPIO branches,
two module targets camera.ko and cameralog.ko, and configuration requiring
Qualcomm MMRM. Manufacturer Android.mk for taro requires mmrm-module-symvers.
The new CI audits source commit/tree, original Git blobs and those contracts.

Selected target remains Xiaomi OEM kernel Linux 5.10.81 at
032260f7c8dacf338e1ac993e1653cd1982877d1, AOSP 17, mondrian only.
No LineageOS source is imported; only Xiaomi sources and verified official
Qualcomm dependencies may form the target BSP. FM remains excluded.

Next separate task: compile both original Xiaomi camera modules with LLVM23,
the exact kernel Module.symvers and the compatible Qualcomm MMRM symbols,
identify actual compile/ABI mismatches, and fix them without deleting drivers,
suppressing failures or using another ROM's source. After compile, establish
mondrian OEM sensor topology, Qualcomm HAL compatibility and physical runtime.
No production vendor_dlkm/modules.load, boot.img, dtbo.img, HAL, or hardware
qualification is asserted by this document.
