#!/usr/bin/env bash
# Build a *separate* MiCode ziyi-s-oss Audio candidate against the same OEM kernel.
# Never replace/modify the proven marble submodule or Android load list.
set -euo pipefail
cd "$GITHUB_WORKSPACE"
export PATH=/tmp/google-clang/clang-r614150/bin:$PATH
export LLVM=1 LLVM_IAS=1 ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-
unset KBUILD_MODPOST_WARN
candidate="$RUNNER_TEMP/ziyi-audio-candidate"
expected=8b1c8d3486a7ac3349d1422201a4436ad852fcb1
kout="$RUNNER_TEMP/mondrian-out"
test ! -e "$candidate"
test -s "$kout/vmlinux"
test -s "$kout/Module.symvers"
git clone --quiet --depth 1 --single-branch --branch ziyi-s-oss \
  https://github.com/MiCode/vendor_qcom_opensource_audio-kernel.git "$candidate"
test "$(git -C "$candidate" rev-parse HEAD)" = "$expected"
python3 tools/apply_ziyi_audio_clang23_fix.py \
  --source "$candidate" \
  --evidence "$RUNNER_TEMP/ziyi-audio-source-evidence.json"
make -k -C kernel O="$kout" -j3 M="$candidate" AUDIO_ROOT="$candidate" \
  MODNAME=audio_dlkm BOARD_PLATFORM=taro TARGET_PRODUCT=mondrian \
  CONFIG_SND_SOC_WAIPIO=m KBUILD_EXTRA_SYMBOLS= modules \
  2>&1 | tee "$RUNNER_TEMP/ziyi-audio-compile.log"
for name in machine_dlkm aw882xx_dlkm q6_dlkm gpr_dlkm adsp_loader_dlkm swr_dlkm spf_core_dlkm; do
  mapfile -t matches < <(find "$candidate" -type f -name "$name.ko")
  test "${#matches[@]}" -eq 1
  test -s "${matches[0]}"
done
strings "$candidate/asoc/codecs/aw882xx/aw882xx_dlkm.ko" |
  grep -Fx 'awinic,aw882xx_smartpa'
strings "$candidate/asoc/machine_dlkm.ko" | grep -Fx 'qcom,waipio-asoc-snd'
mkdir -p "$RUNNER_TEMP/ziyi-audio-abi"
count=0
while IFS= read -r module; do
  name="$(modinfo -F name "$module")"
  test ! -e "$RUNNER_TEMP/ziyi-audio-abi/$name.json"
  python3 tools/verify_external_module_abi.py \
    --kernel kernel --kernel-out "$kout" --module "$module" \
    --expected-kernel-commit c67ed74ffe11bd2133b560078a20cf0c04e18d97 \
    --out "$RUNNER_TEMP/ziyi-audio-abi/$name.json"
  count=$((count + 1))
done < <(find "$candidate" -type f -name '*.ko' | sort)
test "$count" -ge 7
echo "[PASS] Ziyi candidate Audio/AW882xx source and ABI (NOT selected for product)" >> "$GITHUB_STEP_SUMMARY"
echo "[PENDING] Compare OEM WAIPIO HAL/mixer/DSP and runtime before replacing Marble" >> "$GITHUB_STEP_SUMMARY"
