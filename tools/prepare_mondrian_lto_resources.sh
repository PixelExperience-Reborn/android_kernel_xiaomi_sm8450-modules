#!/usr/bin/env bash
# Optional, bounded swap for Google LLVM23 Full LTO on GitHub Ubuntu runners.
# Fail closed on invalid runner paths; never change kernel Kconfig or warnings.
set -euo pipefail
: "${RUNNER_TEMP:?Runner temp directory must be provided by GitHub Actions}"
test -d "$RUNNER_TEMP"
echo "::group::OEM mondrian Full LTO runner resources before linking"
free -h
df -h "$RUNNER_TEMP"
swapon --show || true
echo "::endgroup::"

SWAP_KIB=$((3 * 1024 * 1024))
KEEP_FREE_KIB=$((4 * 1024 * 1024))
available_kib=$(df -Pk "$RUNNER_TEMP" | awk 'END {print $4}')
total_swap_kib=$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)
if ! [[ "$available_kib" =~ ^[0-9]+$ && "$total_swap_kib" =~ ^[0-9]+$ ]]; then
  echo "::error::Unable to measure real runner disk/swap resources"
  exit 1
fi
swapfile="$RUNNER_TEMP/mondrian-full-lto.swap"
if ((total_swap_kib >= SWAP_KIB)); then
  echo "[INFO] Existing runner swap is sufficient; no new swap file"
elif ((available_kib <= SWAP_KIB + KEEP_FREE_KIB)); then
  echo "::warning::Skipping 3 GiB swap: insufficient free SSD headroom (free: $((available_kib / 1024)) MiB); preserve 4 GiB for kernel link"
else
  # GitHub-hosted runner is ephemeral. Reclaim temp swap with the VM after CI.
  # Do not use sparse files or place swap inside the source/build tree.
  if sudo fallocate -l 3G "$swapfile" &&
     sudo chmod 600 "$swapfile" &&
     sudo mkswap "$swapfile" >/dev/null &&
     sudo swapon "$swapfile"; then
    echo "[PASS] 3 GiB on-disk swap enabled for Full LTO without lowering hardening"
  else
    echo "::warning::GitHub runner rejected swap setup; retain original kernel security and report real linker result"
    sudo swapoff "$swapfile" >/dev/null 2>&1 || true
    sudo rm -f "$swapfile"
  fi
fi

echo "::group::OEM mondrian resources after optional swap"
free -h
df -h "$RUNNER_TEMP"
swapon --show || true
echo "::endgroup::"
