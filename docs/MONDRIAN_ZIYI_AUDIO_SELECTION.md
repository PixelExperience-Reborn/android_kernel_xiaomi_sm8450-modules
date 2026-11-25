# Xiaomi Ziyi WAIPIO/AW882xx — selected Audio source for mondrian

Only manufacturer `MiCode/vendor_qcom_opensource_audio-kernel` branch
`ziyi-s-oss` commit `8b1c8d3486a7ac3349d1422201a4436ad852fcb1` is selected in
`upstream/xiaomi-audio` for the PE-Reborn AOSP 17 OEM Linux 5.10.81 /
Google LLVM23 diagnostic integration build.

## Manufacturer and device checks
- Xiaomi factory WAIPIO audio DTS has `qcom,wcn-bt=<1>` but not
  `qcom,wcn-btfm` or `qcom,cdc-dmic67-gpios`.
- Mondrian OEM DTS has AW882xx at I2C 0x34/0x35 and MI2S2 connectivity.
  The original WAIPIO ASoC machine and AW882xx Kbuild are pinned to
  seven original Xiaomi Git blob hashes.
- The previously used donor Audio was only a comparison source;
  it included an optional BT/FM PCM route and extra DMIC6/7 GPIO
  handlers not present in mondrian manufacturer DTS. It is no longer
  selected or compiled in the active modules workflow.
- LineageOS mondrian mixer XML is a read-only comparison for mapping;
  no Lineage source is selected for this ROM or kernel.
- Some upstream internal identifiers may still mention BT/FM;
  no FM app, FM HAL, FM radio service or FM build target is enabled.

## Fail-closed source and ABI checks
The selected Git SHA, gitlink, original manufacturer blob IDs, WAIPIO
routing and the two reviewed LLVM23 QoS function declarations are
checked. Audio/AW882xx modules compile once through
`tools/build_mondrian_audio_video.sh` against the exact same kernel
`vmlinux` and `Module.symvers` as Qualcomm MMRM/VIDC and Xiaomi WLAN.
The resulting modules require ELF, ABI/vermagic and depmod validation.

Source selection does not prove completed Full LTO linking, full AOSP 17
Audio HAL/DSP and calibration, product packaging or audio hardware.
Unverified approval flags remain false until their own checks pass.
No FM, donor device tree, kernel version update or unrelated features.
