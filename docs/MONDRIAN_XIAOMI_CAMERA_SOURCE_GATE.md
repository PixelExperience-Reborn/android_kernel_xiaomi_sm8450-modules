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

## 16 November 2026 — second Camera compiler failure

Full diagnostic GitHub Actions #43952612008 again compiled the exact
OEM kernel vmlinux/Image/Module.symvers and Qualcomm MMRM successfully.
Camera compilation advanced past cam_debug_util.c but failed at
drivers/cam_sensor_module/cam_flash/cam_flash_dev.c lines 38, 74 and
288. Three manufacturer function definitions used empty parameter
lists, triggering LLVM23 -Wstrict-prototypes under -Werror.

The next exact source correction additionally turns these three
zero-argument function definitions into (void) without changing
their implementations or existing no-argument call sites. The one
previous cam_debug_get_settings() correction remains. Source revision
and original file SHA-1 IDs remain pinned and any unexpected difference
stops CI before changes are applied. The disposable checkout must
report exactly four changed lines across two C files.

SAFETY: cam_flash_dev.c in the reference yudi tree contains a
hard-coded I2C flash GPIO (I2C_FLASH_GPIO_EN = 356). This is not
qualified for mondrian; the CI fix must not alter, enable or ship this
board-specific hardware path. Camera/sensor topology, camera.ko,
cameralog.ko, driver dependencies and actual boot remain pending.

## 17 November 2026 — own mondrian PM8350C flash hardware safety gate

The exact Xiaomi/Qualcomm Camera build #43961463487 passed both camera.ko
and cameralog.ko ABI verification with the selected OEM kernel, but was
only a compile test, not a safe flash implementation.

The Xiaomi yudi Camera header forcibly defines CONFIG_CAMERA_I2CFLASH,
which compiles a separate sysfs/CCI bridge and hard-coded GPIO356.
This feature is not established for mondrian. A new PE-Reborn
*build-time selector* replaces that single forced define in the
disposable manufacturer checkout with a fail-closed prohibition on
enabling CONFIG_CAMERA_I2CFLASH for mondrian. The original vendor code
is preserved for other properly documented hardware; the generic
Qualcomm I2C Flash path, PMIC path, CCI, sensor driver, and all non-flash
Camera functionality stay intact. CI checks compiled symbols for the
correct generic and PMIC functionality and absence of yudi's sysfs GPIO.

The selector additionally checks the exact OEM MiCode Device Tree
provenance in our own independent device-trees repo and confirms that
PM8350C flash/switch nodes are already declared and enabled in the
Xiaomi SM8475 common DTS. **Caution:** that OEM common DTS currently
specifies switch0 LED mask 9 (channels 1 & 4); a separate mondrian
reference uses mask 1. Neither is a verified factory flash layout
for the device revision in hand. Do not guess a mask, change hardware
pins or ship a mondrian Camera DTBO without original Xiaomi stock
DTBO evidence and real device testing. The reference ROM is not
a source or code dependency in PE-Reborn.

The new JSON policy marks hardware readiness and product selection
false. This step changes no Kernel, DTS, OTA, product module load list,
ROM AOSP 17 sources, FM components, or default `seventeen` branch.

Next independent task after CI: recover original Xiaomi *mondrian*
Camera DTBO/firmware and verify sensor wiring, PM8350C channel
selection and camera HAL compatibility before building an own
qualified Camera overlay for the exact bootloader/SKU.


## 17 November 2026 — fix a false-negative ELF qualification gate

Camera diagnostic [run #43970062439](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/43970062439)
compiled the selected Xiaomi OEM kernel/Qualcomm MMRM and both Camera
modules. The PM8350C selector passed and the yudi-specific GPIO356
sysfs branch was excluded. CI then **falsely failed** because an
additional check demanded \`cam_flash_pmic_power_ops\`: this function
is absent from the manufacturer Camera implementation. The real
PMIC binding deliberately sets \`fctrl->func_tbl.power_ops = NULL\`;
it selects the PMIC packet parser, apply function, and flush function.
The generic I2C path has a separate \`cam_flash_i2c_power_ops\`
callback and remains intact.

The revised gate parses the **actual camera.ko ELF with nm -P** and
requires the manufacturer's real PMIC parse/apply/flush/LED symbols,
generic I2C functions and I2C probe/driver registration. It rejects
any compiled symbols from the unqualified yudi GPIO356/sysfs extension,
requires exact OEM kernel vermagic, and emits SHA256/ELF evidence.
Negative regression tests ensure neither disappearing PMIC/generic
I2C functions nor re-enabling the donor-specific branch can pass.

The corrections do not touch Xiaomi/Qualcomm driver code, kernel config,
Device Trees, product modules.load, firmware, board masks, Android 17
build flags, the \`seventeen\` branch, or the successful source-based
PM8350C selection gate. This fixes the static ABI *test*, not any
unverified physical Camera functionality.


## 17 November 2026 — unify Camera into the same real OEM BSP closure

The separate Xiaomi Camera and ABI run
[GitHub Actions #43974526537](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/43974526537)
already passed, as did the separate coherent OEM WLAN/Display/MMRM run
[#43974526644](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/43974526644).
Those separate builds do not by themselves prove that all Camera
dependencies can be staged alongside WLAN/Display at once.

The main coherent build now **compiles the exact MiCode Camera at
9ed4ce96d49c0759c6365627113c5f59c2407942** against the same
OEM 032260f full vmlinux/Module.symvers as WLAN, MMRM and
Qualcomm Display. It uses the reviewed LLVM23 prototype adjustments
and own mondrian PM8350C selector that prevents the donor GPIO356
sysfs branch. All external modules must pass exact kernel AArch64
and vermagic checks. The staging program accepts camera.ko and
cameralog.ko as **two additional independent roots**, includes
their required dependency closure through depmod/modprobe dry-run,
refuses duplicates, and records hashes and loading dependencies.

This stage deliberately does not fabricate camera sensor registers,
actuator/eeprom power sequences, manufacturer PM8350C LED mask,
CamX/CHI HAL bindings, stock software blobs, or a production
vendor_dlkm/modules.load. Camera, Flash and UDFPS remain subject to
real device bring-up once the independent source tree is complete.
An optional OEM firmware image may aid verification but is NOT
a condition for writing, building and testing the Qualcomm/Xiaomi BSP.

The original MiCode source and the default `seventeen` branches
are not edited. No LineageOS source, FM support, or other device
targets are introduced. Failure of any Camera compile, dependency
or static ABI gate blocks this combined build instead of allowing a
false green from unrelated subsystem tests.


## 17 November 2026 — include original MiCode Camera as pinned BSP source

The coherent OEM Image + WLAN + MMRM + Display + Camera build passed at
[GitHub Actions #43980510503](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/43980510503).
Before this stage, all three Camera CI workflows made independent
`actions/checkout` calls against the same manufacturer SHA, leaving
Camera outside the actual BSP Git tree. Other OEM/Qualcomm components
(WLAN, MMRM) already used pinned submodules.

`xiaomi-camera-source` is now a **Git submodule** pointing directly to
`MiCode/vendor_qcom_opensource_camera-kernel` at the validated manufacturer
commit `9ed4ce96d49c0759c6365627113c5f59c2407942`, with unchanged
upstream tree `e8fadfd2127cb9e12696273e1661ead9f9a70c89`.
All existing camera source-only, standalone ABI, and coherent OEM build
workflows now use the *same recursively initialized Gitlink* instead of
cloning another Camera revision. A fail-closed check verifies the submodule
URL, recorded SHA, checked-out HEAD/tree, original file blobs, and
provenance. Xiaomi's unmodified source remains available; the four LLVM23
C-prototype fixes and the mondrian PM8350C safety selector remain
reviewed, isolated build-time adaptations.

This is **reproducible OEM source integration**, not a transfer of
yudi-specific sensor wiring to mondrian. Neither the Xiaomi manufacturer
repository nor any LineageOS source is changed. No Camera HAL, DTS sensor
powers, production modules.load, boot/vendor_dlkm packaging or physical
flash behavior is claimed ready by this source pin. Subsequent work can
build a native camera board configuration against precisely this input.
