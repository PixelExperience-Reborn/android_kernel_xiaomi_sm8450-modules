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

## 16 Nov 2026 — separate OEM Camera compilation diagnostic

The previous source-only MiCode yudi SM8475 Camera audit finished SUCCESS:
https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/43929588930 .
A distinct \`xiaomi-camera-compile-abi.yml\` workflow now attempts to compile
the unmodified manufacturer \`camera.ko\` and \`cameralog.ko\` using:

- kernel PixelExperience-Reborn/android_kernel_xiaomi_sm8450 at
  \`032260f7c8dacf338e1ac993e1653cd1982877d1\` (Xiaomi OEM 5.10.81);
- original MiCode Camera tree \`yudi-t-oss\` commit
  \`9ed4ce96d49c0759c6365627113c5f59c2407942\`;
- exactly the same Google Android clang-r614150 / LLVM23, OEM
  \`mondrian_GKI.config\` and full built \`vmlinux\` / \`Module.symvers\`;
- pinned existing Qualcomm MMRM production driver and its exported symbols.

Compilation errors are not suppressed and full compiler diagnostics are
retained for inspection. The release manifest, \`modules.load\`, Kernel and
Devicetrees source, \`seventeen\` branches, Camera HAL and panel hardware
are not changed. Successful CI would prove only static compilation/ABI,
**not** that yudi camera firmware/sensors work on mondrian.

On failure the next action is to fix the *specific* incompatibility in
reviewed Xiaomi/Qualcomm code; do not replace the entire OEM base,
drop functional drivers, or import code from LineageOS.

## 16 November 2026 — first Camera compile failure (LLVM23)

The real diagnostic run #43938037278 built the exact Xiaomi OEM 5.10.81
kernel, Image, Module.symvers and Qualcomm MMRM successfully. It stopped
on the original Xiaomi Camera source at drivers/cam_utils/cam_debug_util.c:82:
the definition of cam_debug_get_settings() lacks an explicit void.
Clang 23 reports -Wstrict-prototypes and treats it as an error with -Werror.

The original header already declares cam_debug_get_settings(void). A
separate, byte-exact correction script validates both manufacturer Git blobs
and the unchanged Xiaomi commit, then changes only the disposable Camera
checkout's function definition from () to (void). It does not modify the
return type, function body, export, call sites, or binary ABI, and it does
not suppress any warnings. The applied-source SHA is recorded separately.

The next diagnostic CI attempts the same full camera.ko and cameralog.ko
compile again; any further compiler or modpost failure remains a blocker.
The Xiaomi upstream Git source, Kernel, Devicetrees and production module
selection are untouched. No working Camera or hardware tests are claimed.
