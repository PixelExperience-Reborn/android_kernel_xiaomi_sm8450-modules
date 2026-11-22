# Mondrian camera OIS and power audit — diagnostic

This stage follows the successful unified Audio/Video build
[GitHub Actions #45013252607](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/45013252607).

The pinned native mondrian DeviceTrees and two Xiaomi global stock-dump
CamX manifests identify OV64B40 + DW9800V + a named AK7323 profile for
the wide camera. Those profiles have two zero-filled OIS power entries and
13 zero-filled register-data entries; the board DTB has **no standalone
OIS subdevice** and no `ois-src`. Adding `qcom,ois`, guessing a power
sequence or enabling an AK7323 bus is not supported by the evidence.

The new fail-closed build gate validates the four exact factory Camera
sensor and EEPROM identities, the factory CamX EEPROM power records,
and regulator order/links in **all three real compiled** Cape+mondrian
diagnostic DTBs, including the wide actuator and ultrawide EEPROM reset.
In particular, three factory EEPROM profiles request WL2866D AVDD1 with
3ms enable delay; the macro EEPROM has a separate VIO record.
This does *not* establish their entire sensor or OIS power sequence,
or claim that these vendor power records are identical to the DTS supplies.

All kernel/Audio/VIDC/Camera source revisions, WL2866D ABI and DTS
regulators remain unchanged. No Lineage tree, donor wiring, FM,
unverified OIS/flash GPIO commands, production DTBO or modules.load
selection is added. Camera HAL probing, EEPROM reads, real AK7323
control, stabilization, power-cycle timing and physical testing remain
pending before Stage 2 can be considered hardware-ready.

## 22 November 2026 — correct a test-only fdtget format error

Both coherent builds [#45029755654](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/45029755654) and [#45029907370](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/45029907370) compiled the full OEM Image, Camera, AW882xx, Qualcomm VIDC, DTBs and M11A. Both failed solely in this **new** OIS/power check because the fdtget CLI used `-t d` for the ultrawide sensor's `gpio-reset` cell. The official Android 17 external/dtc implementation accepts `-t u` for unsigned cells, not `-t d`. The pre-existing independent compiled Camera board FDT verifier had already confirmed the reset index is 1 and that the EEPROM deliberately has no reset property.

The fix changes only the checker to read the exact 32-bit unsigned value, explicitly rejects unsupported formatting, and reports the underlying libfdt stderr on future failures. Added positive/negative CLI tests and a three-variant compiled-board mock exercise. The manufacturer DTS, sensor configuration, power sequencing, OIS driver, original kernel, modules, firmware and product packaging remain untouched.

Android 17 authoritative CLI reference: https://android.googlesource.com/platform/external/dtc/+/refs/heads/android17-release/fdtget.c
