# QCA6490 PCIe-only OEM driver qualification — mondrian

Manufacturer sources: MiCode/vendor_qcom_opensource_wlan,
commit 334e5943b77af50dfd1fc7eb872a26b79ae5119f.
- qcacld-3.0/configs/default_defconfig (Git blob e6748c0f2b0c130728f591f940fbcb5af7d1a7c7)
- qcacld-3.0/Kbuild (Git blob 8d8008766f4b9b38127eb0d8c52b44916d7e3c1e)

The native mondrian DeviceTrees derive from the original Xiaomi
MiCode/kernel_devicetree and have qcom,cnss-qca6490 with
wlan-pcie-root-complex=0. The QCA6490 variant is a PCIe target.

The previously green CI invoked WLAN_PROFILE=qca6490 but omitted
CONFIG_CNSS_QCA6490 and the transport selection, allowing its
default_defconfig to choose ICNSS2/SNOC. Indeed CI #45068959122
compiled cmn/hif/src/dispatcher/multibus_snoc.o — successful
module linking is NOT proof of a correct PCIe module.

Both driver compile jobs now pass:
- CONFIG_CNSS_QCA6490=y selects Xiaomi's QCA6490 WLAN/HAL features;
- CONFIG_ROME_IF=pci is explicit to disallow SNOC fallback;
- WLAN_CTRL_NAME=wlan for Android WLAN control;
- TARGET_BUILD_VARIANT=user for normal release variant behavior;
- DYNAMIC_SINGLE_CHIP=qca6490 for the manufacturer's chip-specific
  firmware/config path handling.

The build fails closed unless actual compiled PCIe multibus and
QCA6490 HAL objects exist and the SNOC multibus object is absent.
Both workflows compile against the same Xiaomi OEM Linux 5.10.81
and Qualcomm dependency ABI. No Lineage driver or new firmware added.

This is still *compile-only* validation: firmware naming/availability,
CNSS2 probing and AOSP17 vendor integration remain to be verified.

## Consistency gate before first ROM build

The standalone WLAN ABI workflow must use the same immutable OEM
Kernel SHA `c67ed74ffe11bd2133b560078a20cf0c04e18d97` as the combined three-repository
qualification; this includes its checked-out source, MMRM/WLAN ABI
checks and depmod staging. A different successfully linked OEM kernel
cannot substitute for this qualification. Full PCIe and hardening
compilation still requires a completed CI run; a source-only PASS
or a shutdown during the Full LTO link is not sufficient.
