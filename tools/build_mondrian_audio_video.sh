#!/usr/bin/env bash
# Build real modules using the single existing OEM Image and symbol table.
set -euo pipefail
cd "$GITHUB_WORKSPACE"
export PATH=/tmp/google-clang/clang-r614150/bin:$PATH
export LLVM=1 LLVM_IAS=1 ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-
unset KBUILD_MODPOST_WARN
kernel_sha=c67ed74ffe11bd2133b560078a20cf0c04e18d97
kout="$RUNNER_TEMP/mondrian-out"
audio="$GITHUB_WORKSPACE/upstream/xiaomi-audio"
video="$GITHUB_WORKSPACE/upstream/qualcomm/video"
mmrm_sym="$GITHUB_WORKSPACE/upstream/qualcomm/mmrm/driver/Module.symvers"
test "$(git -C kernel rev-parse HEAD)" = "$kernel_sha"
test -s "$kout/vmlinux"
test -s "$kout/Module.symvers"
test -s "$mmrm_sym"
grep -Fxq 'CONFIG_ARCH_WAIPIO=y' "$kout/.config"
grep -Fxq 'CONFIG_ARCH_CAPE=y' "$kout/.config"
python3 tools/verify_mondrian_audio_video_sources.py
# OEM Android.mk selects taro/WAIPIO. Full Kbuild visits all audio
# subdirectories in one modpost, not split Android OUT paths.
make -C kernel O="$kout" -j3 M="$audio" AUDIO_ROOT="$audio" \
    MODNAME=audio_dlkm BOARD_PLATFORM=taro TARGET_PRODUCT=mondrian \
    CONFIG_SND_SOC_WAIPIO=m KBUILD_EXTRA_SYMBOLS= modules \
    2>&1 | tee "$RUNNER_TEMP/mondrian-media-audio.log"
for name in machine_dlkm aw882xx_dlkm q6_dlkm gpr_dlkm adsp_loader_dlkm swr_dlkm spf_core_dlkm; do
    mapfile -t matches < <(find "$audio" -type f -name "$name.ko")
    test "${#matches[@]}" -eq 1
    test -s "${matches[0]}"
done
# Select WAIPIO/IRIS2 inside the external driver, keeping the kernel config.
make -C kernel O="$kout" -j3 M="$video" VIDEO_ROOT="$video" \
    MODNAME=msm_video BOARD_PLATFORM=taro CONFIG_MSM_VIDC_V4L2=m \
    CONFIG_ARCH_DIWALI=n KBUILD_EXTRA_SYMBOLS="$mmrm_sym" modules \
    2>&1 | tee "$RUNNER_TEMP/mondrian-media-video.log"
test -s "$video/msm_video.ko"
strings "$audio/asoc/codecs/aw882xx/aw882xx_dlkm.ko" | grep -Fx 'awinic,aw882xx_smartpa'
strings "$audio/asoc/machine_dlkm.ko" | grep -Fx 'qcom,waipio-asoc-snd'
find "$audio" -type f -name '*.ko' -print | sort > "$RUNNER_TEMP/mondrian-media-roots.txt"
printf '%s\n' "$video/msm_video.ko" >> "$RUNNER_TEMP/mondrian-media-roots.txt"
mkdir -p "$RUNNER_TEMP/media-abi"
while IFS= read -r module; do
    name="$(modinfo -F name "$module")"
    test ! -e "$RUNNER_TEMP/media-abi/$name.json"
    python3 tools/verify_external_module_abi.py \
        --kernel kernel --kernel-out "$kout" --module "$module" \
        --expected-kernel-commit "$kernel_sha" \
        --out "$RUNNER_TEMP/media-abi/$name.json"
done < "$RUNNER_TEMP/mondrian-media-roots.txt"
echo "[PASS] OEM Audio/AW882xx and Qualcomm WAIPIO VIDC compiled; staging follows" >> "$GITHUB_STEP_SUMMARY"
