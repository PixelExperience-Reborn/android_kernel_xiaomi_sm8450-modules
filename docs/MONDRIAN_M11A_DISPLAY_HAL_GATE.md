# Mondrian M11A — post-build Display ABI and HAL gate

Scope: PE-Reborn AOSP 17, Xiaomi OEM Linux 5.10.81, SM8475, M11A
`0x4d31314100420200`. No product driver change. Do not import LineageOS.
Do not replace the native Qualcomm Display merely because Xiaomi compiles.

## Verified compilation

- Kernel [2efda4c](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450/commit/2efda4c)
- Modules [fe50211](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/commit/fe50211)
- DeviceTrees [2550600](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-devicetrees/commit/2550600)
- Xiaomi Display [bf0d5e2](https://github.com/MiCode/vendor_opensource_display-drivers/tree/bf0d5e23be5457001a18aa9dcd68cb17994ae36a), adapted with four versioned patches.
- [Build 45496059633](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/45496059633):
  full OEM kernel, MMRM, both Display modules, strict MODPOST, imported CRC
  and vermagic passed. Diagnostic-only; no product module selection.
- [135 source tests](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/45496060806)
  passed before this documentation/tool update.

## Userspace ABI: real differences, not build failures

Calculated normal LP64 (AArch64) C layouts from the pinned
[Xiaomi SDE UAPI](https://github.com/MiCode/vendor_opensource_display-drivers/blob/bf0d5e23be5457001a18aa9dcd68cb17994ae36a/include/uapi/display/drm/sde_drm.h),
[PE Qualcomm SDE UAPI](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450/blob/2efda4c/techpack/display/include/uapi/display/drm/sde_drm.h)
and the kernel drm_clip_rect (four unsigned shorts).

| Structure | Xiaomi bytes | PE Qualcomm bytes |
|---|---:|---:|
| sde_drm_roi_v1 | 36 | 72 |
| sde_drm_dest_scaler_cfg | 24 | 32 |
| sde_drm_dest_scaler_data | 56 | 136 |

The PE ROI adds roi_feature_flags and spr_roi; its scaler adds merge_mode
and changes the scaler array from two to four entries. This is a property
payload ABI difference even if the kernel module's symbol CRCs match.
Whether the exact factory HWC submits these properties, and which layouts
it uses, remains to be established. Do not pad, truncate or swap structs
without that evidence.

## FOD character device and event protocol

[Xiaomi mi_disp.h](https://github.com/MiCode/vendor_opensource_display-drivers/blob/bf0d5e23be5457001a18aa9dcd68cb17994ae36a/include/uapi/display/drm/mi_disp.h)
and [native mondrian_fod.c](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450/blob/2efda4c/techpack/display/msm/mondrian/mondrian_fod.c)
agree on the four 12-byte requests (SET_DOZE, REGISTER, DEREGISTER,
SET_LOCAL_HBM), FOD type 2, 12-byte event header plus 4-byte payload,
READY bit 3, and low-brightness capture bit 2. The native shim deliberately
does not implement the entire Xiaomi ioctl surface.

**Different read behavior:** [Xiaomi mi_disp_file.c](https://github.com/MiCode/vendor_opensource_display-drivers/blob/bf0d5e23be5457001a18aa9dcd68cb17994ae36a/msm/mi_disp/mi_disp_file.c#L98-L170)
requeues a record that does not fit in the remaining read buffer. With a
pending 16-byte FOD record and a 12-byte initial request this returns zero,
not a header. Native mondrian_fod.c supports split reads and superseding
READY with OFF until payload delivery begins. A HAL using whole records
does not necessarily encounter this problem. The actual factory HAL read
sequence is **not verified**. Do not change the Xiaomi queue blindly.

## Goodix / AOD source-level contract

Both SDE implementations map ON to UNBLANK, LP1/LP2 to BLANK_LP and OFF
to BLANK. Xiaomi calls the DPMS notifier in pre-commit and post-commit;
it supplies the primary/secondary tag, c_conn->panel and early_trigger.
Goodix handles BLANK/BLANK_LP after commit and schedules resume after
UNBLANK. The kernel notifier filters by exact drm_panel pointer and tag.

- [Xiaomi sde_kms.c](https://github.com/MiCode/vendor_opensource_display-drivers/blob/bf0d5e23be5457001a18aa9dcd68cb17994ae36a/msm/sde/sde_kms.c#L926-L1040)
- [Goodix](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450/blob/2efda4c/drivers/input/touchscreen/goodix_berlin_driver/goodix_ts_core.c#L1895-L1927)
- [DT overlay](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-devicetrees/blob/2550600/qcom/mondrian-m11a-primary-overlay.dts)

The DT already includes the primary DSI provider and M11A panel phandles
and requires the notifier. No reason to rewrite the successful Goodix fix.
Actual registration, pointer match, event delivery and wake gestures
(fod_type/double_type before sleep) must still be observed on hardware.

## Additional binary evidence: Goodix sysfs consumers

Read-only inspection of the archived ARM64 binary copies for mondrian
found a separate userspace ABI gap. These are not independent verification
of a factory package. No third-party driver, device configuration, HAL
binary or LineageOS code has been imported.

The three blob IDs in the existing maintainer vendor archive
[LF52406 at 3ccf06a](https://github.com/LF52406/proprietary_vendor_xiaomi_mondrian/tree/3ccf06a7c4f6543a2a8b0811e8843514a624b56b)
match the inspected [TheMuppets archive at 3535868](https://github.com/TheMuppets/proprietary_vendor_xiaomi_mondrian/tree/3535868a024688fb69067e1e2c701935210f8d68):

| Relative vendor file | Git blob SHA-1 |
|---|---|
| lib64/hw/fingerprint.goodix_fod.default.so | a5b11731088660dad24159262080a645eb56b964 |
| lib64/libgf_hal.so | 8eb91088ac0ca6aaad74e4a013ed9f493ef0a220 |
| lib64/hw/fingerprint.fpc_fod.default.so | c350f441e34623a83f7a8e72ce0911078bd20020 |

Archive history attributes the Goodix wrapper to OS2.0.203.0.VMNMIXM
([da8a760](https://github.com/TheMuppets/proprietary_vendor_xiaomi_mondrian/commit/da8a7603c1c794c1489cc7f599e93489433f5791))
and libgf_hal.so to OS3.0.2.0.VMNMIXM
([8ccad3c](https://github.com/TheMuppets/proprietary_vendor_xiaomi_mondrian/commit/8ccad3c85b27bd20527e84cf622d711868c991d6)).
Do not treat this mixed archive as a single authenticated factory image.

The wrapper imports libgf_hal.so. In that library, ARM64 ADRP/ADD string
references, BL targets resolved through .rela.plt, and register setup
establish these call sites (ELF virtual addresses, not runtime addresses):

| Path under /sys/class/mi_display/disp-DSI-0/ | Observed calls | Evidence |
|---|---|---|
| wp_info | __open_2, __read_chk, close | CustomizedAlgo::getOEMWPInfo, xref 0x31a50, read 0x31a80; caller-supplied count |
| flatmode_check | __open_2, read, close | SZCustomizedProductTest::ReadFlatmode, xref 0x36ad0, read 0x36b04; w2 = 10 at 0x36afc |
| disp_param | __open_2, __write_chk, close | xref 0x367b0, open 0x367c0 with O_RDWR, write 0x367f0 |

For disp_param the helper-generated feature/value command and normal
authentication reachability remain to be resolved; the flatmode read
is in a product-test function and is not proof of a normal FOD path.
The 10-byte flatmode read is **not** the FOD event read size.
Neither fingerprint wrapper nor libgf_hal contains the full
/dev/mi_display/disp_feature string; do not infer its absence in the
full factory software from those three binaries.

The [Xiaomi candidate sysfs](https://github.com/MiCode/vendor_opensource_display-drivers/blob/bf0d5e23be5457001a18aa9dcd68cb17994ae36a/msm/mi_disp/mi_disp_sysfs.c)
implements real display operations for all three paths. Its
mi_disp_feature_attach_display creates the per-display DSI device and
attributes. The native PE mondrian_fod.c creates disp_feature, not these
per-display attributes. This is a concrete API difference; it is not
justification to add fabricated calibration or flatmode results. The
factory HWC and the FOD character-device consumer remain unverified.
The inventory now recognizes sysfs-only consumers and fortified
Bionic I/O imports, including libgf_hal.so. It still does not infer
call arguments from strings.

## Historical stock Composer and actual ioctl calls

A separate mondrian stock dump contains the vendor partition, unlike the
available OS3.0.5.0.VMNMIXM dump, which has no vendor tree. Reference:
[gm-stuffs/poco_mondrian_dump at 08d057d](https://github.com/gm-stuffs/poco_mondrian_dump/tree/08d057dfd16a6b2c8520100290d4b1807b03ce86).
The branch describes the Android 14 V816.0.8.0.UMNMIXM release; its
vendor/build.prop reports mondrian, V816.0.8.0.UMNMIXM and vendor Android
12. This is historical comparison data, not authenticated HyperOS 3
evidence and not a selected AOSP 17 vendor tree.

The ARM64 DisplayDeviceManager library (vendor/lib64/libMiDispDevManager.so,
Git blob 7a1c4e3d9165e1b9068df1138b5c13117c3b081b) opens
/dev/mi_display/disp_feature. Resolve BL through the ELF PLT and
.rela.plt and inspect MOVZ/MOVK into w1 immediately before each ioctl.
All nine observed LP64 requests match the pinned Xiaomi mi_disp.h
declarations; the native FOD shim supports only three of these nine.
A separate native LHBM request 0x400c440e is not among these observed calls.

| Operation | ioctl | ELF call VA | Native FOD shim supports |
|---|---|---|---|
| SET_FEATURE | 0xc0304401 | 0x21f0 | no |
| SET_DOZE_BRIGHTNESS | 0x400c4402 | 0x22b0 | yes |
| GET_DOZE_BRIGHTNESS | 0x800c4403 | 0x234c | no |
| GET_PANEL_INFO | 0xc0184404 | 0x240c | no |
| GET_WP_INFO | 0xc0184405 | 0x24cc | no |
| GET_FPS | 0x800c4406 | 0x258c | no |
| REGISTER_EVENT | 0x400c4407 | 0x26cc | yes |
| DEREGISTER_EVENT | 0x400c4408 | 0x27b0 | yes |
| WRITE_DSI_CMD | 0x40284409 | 0x2804 | no |

The historical HWC uses vendor/lib64/libsdedrm.so (Git blob
b98233ab5d4bdf7c6aea56aab6bc552fac58b2e5). In DRMConnector::SetROI
(VA 0x25c14) and DRMCrtc::SetROI (VA 0x37644), the count is checked
against four, 36 bytes of ROI storage are initialized, and four
16-bit coordinates per rectangle are written with 8-byte stride.
The pointer to the ROI is passed as the atomic property value (connector
tail call 0x25da0, CRTC tail call 0x37998). This is not an ioctl with
an encoded ROI length, nor a DRM blob that carries a length.

The corresponding Xiaomi SDE consumer copies its 36-byte ROI type;
PE Qualcomm unconditionally copies its 72-byte ROI type for the
non-null pointer. A legacy producer does not supply the additional
flags/SPR fields. Reading beyond the historical ABI or interpreting
adjacent memory as flags is not a valid compatibility strategy.

In vendor/lib64/libsdmcore.so (Git blob
20116f0b2c596956e066066c480ebc0faaa6736b), HWPeripheralDRM::SetDestScalarData
(VA 0xbbc6c) uses a 24-byte scaler stride (w25=0x18 at 0xbbcb0)
and passes the constructed object via a virtual DRM operation at
0xbbe48. This is consistent with the Xiaomi 24-byte scaler entry;
it does not establish the complete current HWC ABI or prove every
optional property is exercised by the panel.

Independent local host LP64 C static assertions against the extracted
declarations verified the nine ioctl encodings and six SDE structure
sizes plus two offsets (17 assertions). This was not a full upstream
header compilation, a driver build or a hardware test.

## Native AOSP 17 FOD transport requirement

The historical maintainer UDFPS handler
[LF52406, 6e0022f, UdfpsHandler.cpp](https://github.com/LF52406/mondrian_android_device_xiaomi_sm8450-common/blob/6e0022f5100e09ac97980095b6ed8528f4ff823f/udfps/UdfpsHandler.cpp)
reads the 12-byte event header first and the payload in a second read.
It is an existing comparative reference only (Lineage-derived), not
code for import. This exact pattern is incompatible with the original
Xiaomi mi_disp_read behavior for a queued 16-byte FOD record, which
returns zero for the initial short read and requeues the record.

For the independently implemented PE-Reborn userspace FOD transport,
subscribe only to primary FOD and read a complete 16-byte record at
once. Both currently inspected kernel implementations can deliver this
record. Validate display id, event type, length and payload before
dispatching, serialize cancellation/finger-up against late READY, and
handle interrupted/nonblocking reads and teardown without spinning.
A future implementation must also verify actual HAL/service integration
and wake gesture timing. Do not import the prior UDFPS handler or
change the candidate's generic event queue solely to accommodate it.

This evidence favors the original Xiaomi candidate for historical stock
Display ABI. It does not approve replacing the current driver: the
target HyperOS 3 HWC, actual stock FOD event consumer and runtime
calibration/panel behavior remain unverified. Obtain the exact selected
firmware vendor partition (or Composer, libsdedrm, libsdmcore,
libMiDispDevManager and actual FOD consumer from that same image) before
choosing the final production driver or changing the queue.

## Next evidence: original vendor HAL, not another ROM

Use the extracted vendor partition of an independently sourced, verified
Xiaomi mondrian firmware matching the intended SKU/region. The inventory
does not extract firmware images, establish authenticity or execute binaries.

```sh
python3 tools/audit_mondrian_display_hal.py \
  --vendor-root /path/to/stock/vendor \
  --firmware-build OS3.0.5.0.VMNMIXM \
  --out /tmp/mondrian-display-hal.json
```

Substitute the actual stock build. Optionally record the archive SHA256
with --firmware-sha256. The tool scans ELF files under bin, lib, lib64,
identifies character-device and sysfs path/name candidates, hashes them
and records DT_NEEDED and relevant imported I/O functions. Missing literals or imports are not
proof of absence: wrappers and indirect calls are possible. Supply the
JSON plus the relevant original binaries privately for ARM64 disassembly.
Confirm ioctl request numbers, structure usage, read call sizes and
HWC property payload sizes at actual call sites, or in narrowly scoped
stock runtime traces. Do not publish proprietary binaries in the repository.

Before changing product selection: check AOSP 17 UDFPS/HWC integration,
SELinux/ueventd, exact M11A panel revision, 60/90/120 Hz, normal/AOD LHBM,
finger down/up, repeated cancel, suspend/resume and ESD. All runtime and
production qualification flags remain false. The original WAIPIO 11900
IPA/RMNET/EVA/CVP candidate lock is unaffected.
