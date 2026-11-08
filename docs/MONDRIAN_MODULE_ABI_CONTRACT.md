# Qualcomm module BSP gate — mondrian / SM8475 / AOSP 17

**State:** read-only source qualification, no modules copied and no build.

The PE-Reborn `seventeen` branch is intentionally unchanged. The
later LineageOS Qualcomm module tree is a *public source reference*, not the
selected PE source and not a ROM dependency. Its inspected audio
`qcom/opensource/audio-kernel/asoc/Kbuild` contains
`CONFIG_TARGET_PRODUCT_MONDRIAN` — generic Qualcomm modules cannot be
assumed board-identical.

## Source provenance

The machine-readable manifest `modules-bsp-candidates.json` pins the
reference commit, root tree, OEM ordered module-list blob and unresolved
build inputs. The Xiaomi OEM list has **106 rows and 104 distinct names**.
`gh_virt_wdt.ko` and `qcom_wdt_core.ko` each appear twice; this is
documentary evidence, **not** an approved final modules.load file.

## Required matching before importing modules

1. Choose a lawful, redistributable source tree preserving upstream commits,
   third-party attribution and license notices.
2. Match exact kernel commit, defconfig/fragments, compiler, LTO/CFI,
   GKI/KMI symbol list, `Module.symvers` CRCs and module signatures.
3. Verify each `.ko`'s `vermagic`, undefined symbols, `modinfo depends`,
   soft dependencies, firmware requirements and init/exit behaviour.
4. Classify early-boot modules into `vendor_boot`, remaining vendor
   modules into `vendor_dlkm` as appropriate **after checking actual
   device fstab, VINTF, AVB and partition sizes**. Do not derive partition
   installation from the OEM file name alone.
5. Generate a deterministic `modules.load` from the dependency-checked
   output. Never silently deduplicate or reorder vendor modules.
6. Verify display/camera, WLAN/BT, audio, storage, touch and UDFPS on
   a real mondrian before permitting a release.

AOSP documents vendor module paths and loading at
https://source.android.com/docs/core/architecture/partitions/vendor-odm-dlkm-partition
and symbol ABI checks at
https://source.android.com/docs/core/architecture/kernel/abi-monitor .

There is **no** selected KMI, `.ko`, proprietary firmware, signing key or
Android17 release acceptance in this draft. FM radio is explicitly excluded.
