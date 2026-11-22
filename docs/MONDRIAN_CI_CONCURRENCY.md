# CI push / PR duplicate build control

The active build branch is
bringup/a17-mondrian-oem-bsp-20261111 in the PE-Reborn modules repo.
Previously both push and PR events had separate concurrency group suffixes
(event name). Therefore an identical commit ran a complete OEM Image,
WLAN/MMRM/Display/Camera/Audio/VIDC rebuild twice in parallel.

Both build workflows now use github.head_ref || github.ref_name as the
concurrency key. This is the actual source branch for both event types.
cancel-in-progress prevents duplicate heavy jobs on superseding runs.

Independent source contracts, Camera ABI and strict full compile remain
required by their workflows. This does not skip checks based on build
success of another SHA. Avoids unnecessary Linux 5.10.81/LLVM23 rebuilds
when a single commit triggers both push and pull_request.
