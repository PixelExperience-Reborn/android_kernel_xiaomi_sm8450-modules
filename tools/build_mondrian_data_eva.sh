#!/usr/bin/env bash
# Build the Qualcomm WAIPIO 11900 data (IPA/GSI, RMNET core/ext) and EVA
# external modules against the single OEM Image and its real Module.symvers.
# Diagnostic qualification only: no vendor_dlkm or modules.load is produced.
set -euo pipefail
cd "$GITHUB_WORKSPACE"
export PATH=/tmp/google-clang/clang-r614150/bin:$PATH
export LLVM=1 LLVM_IAS=1 ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-
unset KBUILD_MODPOST_WARN
kernel_sha="$(python3 tools/mondrian_source_pins.py kernel)"
kout="$RUNNER_TEMP/mondrian-out"
qcom="$GITHUB_WORKSPACE/upstream/qualcomm"
dataipa="$qcom/dataipa"
rmnet="$qcom/datarmnet"
rmnet_ext="$qcom/datarmnet-ext"
eva="$qcom/eva"
mmrm_sym="$qcom/mmrm/driver/Module.symvers"
test "$(git -C kernel rev-parse HEAD)" = "$kernel_sha"
test -s "$kout/vmlinux"
test -s "$kout/Module.symvers"
test -s "$mmrm_sym"
grep -Fxq 'CONFIG_ARCH_WAIPIO=y' "$kout/.config"
grep -Fxq 'CONFIG_IPA3=m' "$kout/.config"
grep -Fxq 'CONFIG_MSM_GLOBAL_SYNX=m' "$kout/.config"
# The in-kernel IPA framework and SYNX are the only providers these
# external modules link against; refuse a second IPA/RMNET implementation.
grep -q 'ipa_fmwk_register_ipa' "$kout/Module.symvers"
grep -q 'synx_initialize' "$kout/Module.symvers"
if grep -Eq '^CONFIG_(QCOM_IPA|RMNET|MSM_CVP)=[ym]$' "$kout/.config"; then
    echo "::error::A second in-tree IPA, RMNET or CVP implementation is enabled"
    exit 1
fi
python3 tools/verify_qualcomm_data_eva_sources.py
for project in dataipa datarmnet datarmnet-ext eva-kernel; do
    case "$project" in
        dataipa) source="$dataipa" ;;
        datarmnet) source="$rmnet" ;;
        datarmnet-ext) source="$rmnet_ext" ;;
        eva-kernel) source="$eva" ;;
    esac
    python3 tools/apply_qualcomm_patch_series.py --project "$project" \
        --source "$source" --evidence "$RUNNER_TEMP/qcom-$project-patch.json"
done

status=0
build() {
    local name="$1"; shift
    make -k -C kernel O="$kout" -j3 "$@" modules \
        2>&1 | tee "$RUNNER_TEMP/mondrian-qcom-$name.log" || status=1
}
# IPA/GSI: Qualcomm Kbuild selects the WAIPIO vendor-DLKM configuration.
build dataipa M="$dataipa/drivers/platform/msm" DATAIPA_ROOT="$dataipa"
# RMNET core links to IPA only through the in-kernel ipa_fmwk exports.
build datarmnet M="$rmnet/core"
for ext in offload perf perf_tether shs wlan aps sch; do
    build "datarmnet-ext-$ext" M="$rmnet_ext/$ext" \
        RMNET_CORE_INC_DIR="$rmnet/core" RMNET_CORE_PATH="$rmnet/core" \
        KBUILD_EXTRA_SYMBOLS="$rmnet/core/Module.symvers"
done
# EVA uses the same Qualcomm MMRM symbols as Display, Camera and Video.
build eva M="$eva" EVA_ROOT="$eva" KBUILD_EXTRA_SYMBOLS="$mmrm_sym"
if (( status != 0 )); then
    echo "::error::Qualcomm data/EVA compile or MODPOST failed"
    exit 1
fi

expected=(
    "$dataipa/drivers/platform/msm/gsi/gsim.ko"
    "$dataipa/drivers/platform/msm/ipa/ipam.ko"
    "$dataipa/drivers/platform/msm/ipa/ipanetm.ko"
    "$dataipa/drivers/platform/msm/ipa/ipa_clients/rndisipam.ko"
    "$dataipa/drivers/platform/msm/ipa/ipa_clients/ipa_clientsm.ko"
    "$rmnet/core/rmnet_core.ko"
    "$rmnet/core/rmnet_ctl.ko"
    "$rmnet_ext/offload/rmnet_offload.ko"
    "$rmnet_ext/perf/rmnet_perf.ko"
    "$rmnet_ext/perf_tether/rmnet_perf_tether.ko"
    "$rmnet_ext/shs/rmnet_shs.ko"
    "$rmnet_ext/wlan/rmnet_wlan.ko"
    "$rmnet_ext/aps/rmnet_aps.ko"
    "$rmnet_ext/sch/rmnet_sch.ko"
    "$eva/msm/msm-eva.ko"
)
for module in "${expected[@]}"; do
    test -s "$module"
done
test "$(find "$dataipa" "$rmnet" "$rmnet_ext" "$eva" -type f -name '*.ko' | wc -l)" -eq "${#expected[@]}"
# DT contracts the drivers must serve on mondrian.
strings "$dataipa/drivers/platform/msm/ipa/ipam.ko" | grep -Fxq 'qcom,ipa'
strings "$dataipa/drivers/platform/msm/ipa/ipam.ko" | grep -Fxq 'qcom,rmnet-ipa3'
strings "$dataipa/drivers/platform/msm/gsi/gsim.ko" | grep -Fxq 'qcom,msm_gsi'
strings "$eva/msm/msm-eva.ko" | grep -Fxq 'qcom,waipio-cvp'

mkdir -p "$RUNNER_TEMP/qcom-data-eva-abi"
for module in "${expected[@]}"; do
    name="$(modinfo -F name "$module")"
    test ! -e "$RUNNER_TEMP/qcom-data-eva-abi/$name.json"
    python3 tools/verify_external_module_abi.py \
        --kernel kernel --kernel-out "$kout" --module "$module" \
        --expected-kernel-commit "$kernel_sha" \
        --out "$RUNNER_TEMP/qcom-data-eva-abi/$name.json"
done
# The shared dependency-closure step stages these as additional roots.
printf '%s\n' "${expected[@]}" >> "$RUNNER_TEMP/mondrian-media-roots.txt"
echo "[PASS] Qualcomm WAIPIO 11900 IPA/GSI, RMNET core+ext and EVA compiled with real MODPOST" >> "$GITHUB_STEP_SUMMARY"
echo "[PENDING] modem/IPA firmware, data call and EVA runtime on hardware" >> "$GITHUB_STEP_SUMMARY"
