# OEM ziyi-s-oss Audio candidate audit — mondrian (not product source)

Exact manufacturer options from MiCode/vendor_qcom_opensource_audio-kernel:
- Selected working **marble-s-oss** commit 7d174adfe5304b74889e0cf0e16132a049707710
- Independent candidate **ziyi-s-oss** commit 8b1c8d3486a7ac3349d1422201a4436ad852fcb1

Compared original asoc/waipio.c, asoc/Kbuild, asoc/msm_common.c
and the Awinic AW882xx source. Marble WAIPIO includes an optional
qcom,wcn-btfm route, DMIC6/7 GPIO logic and additional AW882xx DSM
debug handlers. Ziyi does not include the BT/FM PCM route or DMIC6/7
GPIO handling, although its DAPM table still has Digital Mic6 and Mic7
with NULL events; ziyi also contains a bt_fm_slim soft dependency.
Therefore 'Ziyi has no FM anywhere' is too broad.

Xiaomi's factory qcom/waipio-audio-overlay.dtsi has qcom,wcn-bt=<1>
but no qcom,wcn-btfm or qcom,cdc-dmic67-gpios. The dedicated mondrian
manufacturer DTS has dual Awinic AW882xx at I2C 0x34/0x35 and MI2S2.
This **favors inspecting** ziyi routing but does not by itself prove
the replacement audio machine/codec correct.

The candidate diagnostic clones ONLY MiCode, checks its exact pinned
Git SHA and seven original blob IDs, patches the same two LLVM23 QoS
prototype errors already fixed in Marble, then compiles **all** Ziyi
Audio/AW882xx modules against the same selected 5.10.81 Image and
Module.symvers and verifies every compiled .ko's ABI. Ziyi is NOT
installed in the product, substituted for Marble in the manifest,
or included in the staged diagnostic closure. No FM service, HAL or
application is enabled. Real AOSP17 HAL/mixer/DSP and board tests
are necessary before switching the selected Audio branch.
