# CI duplicate build cancellation — correct event semantics

Coherent Kernel+WLAN+Display+Camera+Audio+VIDC workflow previously ran
two identical full builds on both push and pull_request of the same source
SHA. It now groups by the source branch
`github.head_ref || github.ref_name` and cancels superseded runs, keeping
the latest required full coherent ABI qualification.

The independent WLAN workflow has asymmetric jobs: source checks run on
push and PR, but the actual `external-wlan` compile only runs on **push**.
Using the same cross-event concurrency group there would let a PR source-only
run cancel the **only** full WLAN job and silently lose required evidence.
Therefore WLAN keeps event-specific cancellation; newer *push* checks
replace older push checks and PR source checks cannot cancel them.

The two distinct workflows still each compile their selected OEM kernel
with Clang23, to establish independent WLAN and whole-component ABI
contracts. This is deliberate verification, not duplicate Git history.
No successful test is skipped, and no warning/ABI flags are bypassed.
