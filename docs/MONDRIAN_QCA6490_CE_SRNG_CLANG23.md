# CE SRNG Clang 23 fix — QCA6490 PCIe on Xiaomi OEM Linux 5.10.81

Actual coherent PCIe CI run [#45075372759](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/45075372759)
compiled the **correct** `multibus_pci.o` and then stopped at
`qca-wifi-host-cmn/hif/src/ce/ce_service_srng.c:1071` with
`-Werror,-Wstrict-prototypes`: Qualcomm defines
`struct ce_ops *ce_services_srng()` instead of `(void)`.

The previously wrong SNOC profile did not compile this CE-SRNG code,
so the compiler error was hidden by the incorrect transport. Original
MiCode WLAN revision is
`334e5943b77af50dfd1fc7eb872a26b79ae5119f`.
The exact original source Git blob of `ce_service_srng.c` is
`318f50f93229be97404394b882ad9ebae73b4a67`.

The same pinned OEM WLAN source adaptator now changes **only**
`ce_services_srng()` to `ce_services_srng(void)`, exactly as its
existing `ce_services_legacy(void)` adaptation. It leaves the
`ce_service_srng` ops table, qdf export, driver registration,
CE ring buffers and warning flags untouched. All changes are applied
only inside the disposable source checkout before compilation.
No new driver is imported and no kernel version is changed.

Success must be proven by a complete PCIe QCA6490 build against
OEM Image/Module.symvers + full KMI and diagnostic board checks.
