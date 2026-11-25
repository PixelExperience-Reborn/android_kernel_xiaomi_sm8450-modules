# Qualcomm WAIPIO 11900 — the release under Xiaomi mondrian

The public Qualcomm manifest at `4ada7dbba74eacc651b1a0852ec90d7801c8199c`, tag
`LA.VENDOR.1.0.r1-11900-WAIPIO.0` (2022-03-14), was fetched from CodeLinaro
and all project revisions were independently fetched there by GitHub Actions
[run 45432312156](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/45432312156).
The lock is `qualcomm-mondrian-waipio-11900-candidates.json`.

## Why this release matches Xiaomi mondrian-s-oss

The vendor manifest delegates kernel, display, video and camera to four AU
images. CodeLinaro published the matching public tags on the same day:

| Image | Public tag | Key commit |
|---|---|---|
| Kernel platform | `KERNEL.PLATFORM.1.0.r1-07800-kernel.0` | msm-5.10 `f8b2ec6` (Linux 5.10.81) |
| Display | `DISPLAY.LA.2.0.r1-05500-WAIPIO.0` | display-drivers `dcaec35` |
| Video | `VIDEO.LA.2.0.r1-03100-WAIPIO.0` | video-driver `8608fb2`, mmrm-driver `69e304b` |
| Camera | `CAMERA.LA.2.0.r1-04400-WAIPIO.0` | camera-kernel `2180be9` |

The Xiaomi kernel is the same Linux 5.10.81, and its Qualcomm driver
directories (soc, clk, pinctrl, thermal, regulator, WALT) contain no file
that is missing from msm-5.10 `f8b2ec6`; the differences are Xiaomi
additions and edits. Tag numbers of the separate image lines are independent:
`VIDEO.LA.2.0.r1-11900-WAIPIO.0` is a 2025 release and unrelated.

## Selected for the build

| Project | Commit | Modules |
|---|---|---|
| dataipa | `17561e5` | gsim, ipam, ipanetm, rndisipam, ipa_clientsm |
| datarmnet | `cc9cb62` | rmnet_core, rmnet_ctl |
| datarmnet-ext | `5aa3b6c` | rmnet_offload, rmnet_perf, rmnet_perf_tether, rmnet_shs, rmnet_wlan, rmnet_aps, rmnet_sch |
| eva-kernel | `8613d42` | msm-eva |

These are exactly the WAIPIO/taro module lists in Qualcomm's own
`*_vendor_board.mk` files. `cvp-kernel` (`7bc10dd`) stays unselected: only
`eva-kernel` serves the mondrian DT node `qcom,waipio-cvp`, and building both
would create two `qcom,msm-cvp` drivers.

IPA/GSI does not add a second IPA stack: RMNET reaches IPA only through the
in-kernel `ipa_fmwk` exports, and dataipa registers into that framework via
`ipa_fmwk_register_ipa()`. The in-tree `QCOM_IPA`, `RMNET` and `MSM_CVP`
options stay disabled and the build script fails if any is enabled.

The build and the reviewed patches are described in
`docs/MONDRIAN_QUALCOMM_DATA_EVA_BUILD.md`. KMI against the final Full LTO
Image and hardware remain pending.
