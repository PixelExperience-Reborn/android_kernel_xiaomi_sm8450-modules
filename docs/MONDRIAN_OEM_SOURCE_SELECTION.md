# OEM-first external module source selection — mondrian

This stage selects **MiCode Xiaomi manufacturer** and ultimately matching **Qualcomm BSP** source, not a LineageOS module tree. The previously pinned LineageOS repository remains **read-only comparison metadata** in `modules-bsp-candidates.json`.

## Verified OEM source

- Kernel: `MiCode/Xiaomi_Kernel_OpenSource@mondrian-s-oss`, commit `989b27aa8391a2ede9b067b53877c4c3343955fe`, manufacturer module list blob `1ee612bfd4090af12f88629a66b069eec9192825`.
- WLAN: [`MiCode/vendor_qcom_opensource_wlan@mondrian-s-oss`](https://github.com/MiCode/vendor_qcom_opensource_wlan/tree/mondrian-s-oss) commit `334e5943b77af50dfd1fc7eb872a26b79ae5119f`, with `qcacld-3.0`, `qca-wifi-host-cmn`, `fw-api`. The upstream qcacld `Kbuild` and `Makefile` blob hashes are pinned. `sigma-dut` is not chosen as a runtime kernel module.
- Original Xiaomi Audio has no `mondrian-s-oss` branch. The device-matched source for our diagnostic WAIPIO/AW882xx build is manufacturer `ziyi-s-oss` at `8b1c8d3486a7ac3349d1422201a4436ad852fcb1`, compared with Xiaomi mondrian audio DTS and LineageOS mondrian mixer **for analysis only**. ABI, DSP/HAL and firmware remain subject to successful qualification. FM radio and unrelated donor routes are excluded.
- Qualcomm MMRM, Camera, Display, Video/CVP/EVA and networking IPA/RMNET sources still need a **specific Qualcomm release** matching the manufacturer's `LA.VENDOR.1.0.r1-11900-r1.0.r1_00029.0` baseline, followed by API/ABI evaluation against our selected OEM kernel.

## Required before integration

Do not import WLAN wholesale until matching kernel `.config`, compiler, kernel `Module.symvers`, internal CNSS/CFG80211 APIs, Wi-Fi chipset/device selection and firmware inventory have been checked. Compile selected sources against **our** kernel, not against LineageOS. Validate `vermagic`, undefined symbols, exported KMI/CRCs, module dependency order and the actual `vendor_boot`/`vendor_dlkm` split. A module repository that contains source but has no successful external module build is **not ready**.

No FM radio and no support for any other Xiaomi device in the PE-Reborn product. `seventeen` stays untouched until all gates pass.
