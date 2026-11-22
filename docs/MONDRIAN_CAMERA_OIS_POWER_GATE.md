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
