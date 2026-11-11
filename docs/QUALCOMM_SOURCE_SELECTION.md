# Qualcomm source selection survey

The selected kernel is Xiaomi OEM `mondrian-s-oss`, 5.10.81. For external modules not present in that source drop, locate the exact Qualcomm CodeLinaro source revision for the manufacturer's Waipio/Cape release. Different subsystem tags (DISPLAY.LA, CAMERA.LA, VIDEO.LA, LA.VENDOR) are NOT interchangeable. A later release may need a kernel API backport before integration.

The scripted source survey checks **candidate tags only**, with no automatic module imports: `tools/qualcomm_release_survey.py`. A discovered SHA is not approval to compile or package it. Each candidate must match our OEM kernel export list and the selected product's firmware, device tree and userspace HAL. The survey never updates the source lock or product manifest.

GitHub Actions retains the survey's machine-readable output for review. The strict WLAN ABI check records exact compiler/kernel/config/symbol metadata when the external Xiaomi module successfully compiles; failed compilation does not qualify the module.

## 2026-11-11 verified Qualcomm tag refs

A successful direct CodeLinaro `git ls-remote` CI survey [#43008080914](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/43008080914) resolved source commit SHAs for MMRM, Display, Camera and Video. The pinned results are in `qualcomm_official_candidates` in `modules-bsp-candidates.json`. Only MMRM is selected as a Git submodule for a strict external module compile. Display/Camera/Video remain read-only version candidates; they have not been imported, built or qualified.
