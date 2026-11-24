# Qualcomm WAIPIO 11900 — mondrian data and EVA candidates

The public Qualcomm manifest at `4ada7dbba74eacc651b1a0852ec90d7801c8199c`, tag
`LA.VENDOR.1.0.r1-11900-WAIPIO.0`, was fetched from CodeLinaro and all five
project revisions were independently fetched there by GitHub Actions
[run 45432312156](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/45432312156).
The immutable candidate list is in `qualcomm-mondrian-waipio-11900-candidates.json`.

This is source provenance, **not** driver qualification. The exact Xiaomi
OEM suffix has not been established, and these candidates are not in the
build or module load lists. Retain the previously verified three-repository
baseline until the Goodix ServerHive qualification passes.

Before selecting data modules, compare the official dataipa implementation
against the OEM IPA 5.1/GSI and RMNET DT bindings, the in-tree IPA framework
registration contract, module dependencies and exported symbols, modem
firmware and the stock vendor module inventory. Do not introduce a second
RMNET core or IPA implementation with duplicate symbols. For EVA, verify
WAIPIO platform data and generic CVP binding, CDSP/SYNX, IOMMU, firmware,
and the factory HAL contract; do not load CVP and EVA solely because both
occur in the manifest. Build against the exact OEM kernel Module.symvers
with LLVM23 and unchanged hardening. No Lineage imports.

This audit does not approve a boot image, production modules.load or a
physical device. Xiaomi Display garnet-t-oss remains the next isolated
compile candidate after Goodix passes.
