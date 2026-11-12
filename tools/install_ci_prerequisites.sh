#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Strict Ubuntu 24.04 dependencies for our pinned mondrian OEM kernel.
# Bypass the GitHub runner's unstable mirror+file Azure archive selection.
set -euo pipefail

packages=(bc bison flex make libssl-dev libelf-dev dwarves binutils-aarch64-linux-gnu kmod)

write_sources() {
  local archive="$1" security="$2"
  cat <<SOURCES
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] ${archive} noble main universe
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] ${archive} noble-updates main universe
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] ${security} noble-security main universe
SOURCES
}

if [[ "${1:-}" == --print-sources ]]; then
  write_sources 'https://archive.ubuntu.com/ubuntu' 'https://security.ubuntu.com/ubuntu'
  exit 0
fi

if [[ ! -r /etc/os-release ]]; then
  echo '::error::Unable to identify CI operating system' >&2
  exit 1
fi
# shellcheck source=/etc/os-release
. /etc/os-release
if [[ "${ID:-}" != ubuntu || "${VERSION_ID:-}" != 24.04 ]]; then
  echo '::error::Expected GitHub Actions Ubuntu 24.04 (noble)' >&2
  exit 1
fi
if [[ "$#" -gt 0 ]]; then
  echo 'Usage: install_ci_prerequisites.sh [--print-sources]' >&2
  exit 2
fi

have_all_packages() {
  local pkg
  for pkg in "${packages[@]}"; do
    if ! dpkg-query -W '-f=${Status}' "$pkg" 2>/dev/null |
         grep -Fxq 'install ok installed'; then
      return 1
    fi
  done
  return 0
}

if have_all_packages; then
  echo '[INFO] All OEM build prerequisites already installed; skipping apt.'
else
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  mkdir -p "$tmp/lists/partial"
  if [[ ! -s /usr/share/keyrings/ubuntu-archive-keyring.gpg ]]; then
    echo '::error::Canonical Ubuntu archive signing key missing' >&2
    exit 1
  fi

  for choice in official kernel-mirror; do
    if [[ "$choice" == official ]]; then
      write_sources 'https://archive.ubuntu.com/ubuntu' \
                    'https://security.ubuntu.com/ubuntu' > "$tmp/ubuntu.list"
    else
      write_sources 'https://mirrors.kernel.org/ubuntu' \
                    'https://mirrors.kernel.org/ubuntu' > "$tmp/ubuntu.list"
    fi

    # No global sources or DNS changes; use only these signed repositories.
    # Isolated package indexes prevent fallback to cached Azure mirror URLs.
    apt_options=(
      -o "Dir::Etc::sourcelist=$tmp/ubuntu.list"
      -o 'Dir::Etc::sourceparts=-'
      -o "Dir::State::lists=$tmp/lists"
      -o 'Acquire::Retries=1'
      -o 'Acquire::ForceIPv4=true'
      -o 'Acquire::http::Timeout=12'
      -o 'Acquire::https::Timeout=12'
    )
    echo "[INFO] Installing missing Ubuntu packages via $choice (signed noble)"
    rm -rf "$tmp/lists"
    mkdir -p "$tmp/lists/partial"
    if sudo timeout 150s apt-get "${apt_options[@]}" \
         -o 'APT::Update::Error-Mode=any' update &&
       sudo env DEBIAN_FRONTEND=noninteractive timeout 210s \
         apt-get "${apt_options[@]}" install -y --no-install-recommends \
         "${packages[@]}"; then
      echo "[PASS] OEM dependencies installed via $choice"
      break
    fi
    echo "::warning::Ubuntu $choice mirror unavailable; trying alternative" >&2
  done
  if ! have_all_packages; then
    echo '::error::Required OEM packages missing after both approved Ubuntu mirrors' >&2
    exit 1
  fi
fi

for tool in bc bison flex make pahole aarch64-linux-gnu-ld modinfo; do
  command -v "$tool" >/dev/null || {
    echo "::error::Required OEM build tool unavailable: $tool" >&2
    exit 1
  }
done
for pkg in "${packages[@]}"; do
  dpkg-query -W -f='${binary:Package} ${Version}\n' "$pkg"
done
echo '[PASS] Ubuntu 24.04 signed package prerequisites verified'
