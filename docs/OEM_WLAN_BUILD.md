# Qualcomm external module development for mondrian

The primary source is the pinned Xiaomi manufacturer kernel. This repository links the actual manufacturer WLAN source as a versioned Git submodule (MiCode/vendor_qcom_opensource_wlan, mondrian-s-oss commit 334e5943b77af50dfd1fc7eb872a26b79ae5119f). The prior contract and module list are preserved. No sources from LineageOS are included.

Run git submodule update --init --recursive and python3 tools/verify_oem_wlan.py. The new CI compiles the same OEM Linux 5.10.81 kernel and module symbol table using the pinned Google Android Clang r614150, then attempts a strict build of Xiaomi QCACLD QCA6490. A pass of the source test is not a pass of the external-module compile. Display, Camera, MMRM, Audio and mobile networking sources remain pending release-matched Qualcomm revisions.

We do not package modules into Android 17 vendor_dlkm before actual Module.symvers/vermagic/dependency and firmware validation. No FM radio or unrelated-device build target is selected.
