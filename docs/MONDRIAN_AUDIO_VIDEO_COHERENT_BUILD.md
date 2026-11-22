# Mondrian Audio and Video integrated diagnostic build

PE-Reborn AOSP 17, Xiaomi OEM Linux 5.10.81 at `c67ed74ffe11bd2133b560078a20cf0c04e18d97`.
Preserves the successful three-repository Display/Camera/WLAN/MMRM baseline.
The existing bringup CI now attempts both real external drivers with LLVM 23
and the same OEM configuration, vmlinux and Module.symvers.

- Audio: Xiaomi MiCode/vendor_qcom_opensource_audio-kernel, marble-s-oss
  `7d174adfe5304b74889e0cf0e16132a049707710`. Original WAIPIO/taro source, explicit mondrian machine
  selection and AW882xx v1.11.0 including PID 2113; existing mondrian DTS
  has matching devices at 0x34 and 0x35. No donor DT configuration is imported.
- Video: official Qualcomm CodeLinaro video-driver, VIDEO.LA.2.0.r1-10200-WAIPIO.0,
  `707fcdb08626667663d13cfceeb2d9dfe92893e3`, same release as the present MMRM driver.
  WAIPIO/IRIS2 is selected for this external build; kernel config unchanged.
- Both source pins are actual Gitlinks; original Git blob IDs are checked.
  Compiled media modules are checked by the existing AArch64/vermagic gate
  and included in the shared dependency closure. No changes to display, camera,
  device trees, default branches or release manifest.
- Diagnostic only: no vendor_dlkm load list, HAL/firmware or hardware approval,
  no donor speaker enabled and no FM support.
- Status: first integrated CI required; fix actual compile or modpost errors
  before moving on to Camera/OIS.

## LLVM23 compilation correction

The push and PR builds #44962227027 / #44962231537 both reached the same
manufacturer Audio failure after successfully compiling the existing kernel,
WLAN, MMRM, Display and Camera. In asoc/msm_common.c:602 and :633,
LLVM23 rejects two static QoS functions declared with empty parameter lists.
Both have exactly one existing no-argument caller. The reviewed byte-exact
adaptation changes only those two definitions to (void), with original Git
blob verification, exact diff checks and regression tests. The function bodies,
callers, power behavior and warning settings remain untouched.

The build now uses make -k and captures both Audio and VIDC compiler results,
so a failure in one driver does not prevent diagnostics in the other. Either
nonzero status stops the job before staging and any successful qualification.
No compiler warning is suppressed. Compilation and hardware remain pending.
