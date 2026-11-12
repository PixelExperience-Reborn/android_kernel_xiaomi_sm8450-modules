# Verified OEM WLAN LLVM23 correction

Upstream: MiCode/vendor_qcom_opensource_wlan at commit 334e5943b77af50dfd1fc7eb872a26b79ae5119f.

The upstream public header `qcacld-3.0/core/mac/src/include/parser_api.h` declares `populate_mdie(... uint8_t mdie[])`, while the corresponding implementation has `uint8_t mdie[SIR_MDIE_SIZE]`. The selected OEM Linux 5.10 kernel with official Android Clang 23 rejects the discrepancy under `-Werror,-Warray-parameter` (confirmed in GitHub Actions #43008080728 and #43008088059).

Guarded script `tools/apply_oem_wlan_fix.py` changes only the header parameter bound to match the existing implementation. This preserves the pointer ABI, the buffer's actual layout and the manufacturer implementation. It verifies the exact Git blob SHA of the manufacturer's header and changes the single declaration only in the throwaway CI checkout; no compiler warning is disabled.

**Do not mark WLAN module ready:** pass requires full Kbuild/modpost, the correct KMI and Module.symvers, firmware packaging and device tests.
