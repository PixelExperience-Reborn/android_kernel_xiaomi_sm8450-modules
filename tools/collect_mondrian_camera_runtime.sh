#!/system/bin/sh
# Read-only Camera runtime snapshot for Xiaomi mondrian. No hardware writes.
set -eu
umask 077
if [ "$#" -gt 1 ]; then
  echo "usage: sh collect_mondrian_camera_runtime.sh [new_absolute_output_dir]" >&2
  exit 2
fi
if [ "$#" -eq 1 ]; then
  out="$1"
else
  out="/data/local/tmp/mondrian-camera-$(date +%Y%m%d-%H%M%S)-$$"
fi
case "$out" in
  /*) ;;
  *) echo "output directory must be absolute" >&2; exit 2 ;;
esac
product="$(getprop ro.product.device)"
vendor="$(getprop ro.product.vendor.device)"
if [ "$product" != "mondrian" ] && [ "$vendor" != "mondrian" ]; then
  echo "This diagnostic is only for mondrian" >&2
  exit 2
fi
if [ -e "$out" ]; then
  echo "Refusing to overwrite existing evidence: $out" >&2
  exit 2
fi
mkdir -m 700 "$out"
{
  printf 'device=%s\n' "$product"
  printf 'vendor_device=%s\n' "$vendor"
  printf 'kernelrelease=%s\n' "$(uname -r)"
  printf 'sdk=%s\n' "$(getprop ro.build.version.sdk)"
  printf 'read_only=1\n'
} > "$out/metadata.txt"
if [ -r /proc/modules ]; then
  cat /proc/modules > "$out/modules.txt"
else
  : > "$out/modules.txt"
fi
: > "$out/video4linux.tsv"
for node in /sys/class/video4linux/v4l-subdev*; do
  if [ -d "$node" ] && [ -r "$node/name" ]; then
    printf '%s\t%s\n' "$(basename "$node")" "$(cat "$node/name" 2>/dev/null)" >> "$out/video4linux.tsv"
  fi
done
: > "$out/i2c_devices.tsv"
for node in /sys/bus/i2c/devices/*; do
  if [ -d "$node" ] && [ -r "$node/name" ]; then
    printf '%s\t%s\n' "$(basename "$node")" "$(cat "$node/name" 2>/dev/null)" >> "$out/i2c_devices.tsv"
  fi
done
: > "$out/regulator_names.tsv"
for node in /sys/class/regulator/regulator.*; do
  if [ -d "$node" ] && [ -r "$node/name" ]; then
    printf '%s\t%s\n' "$(basename "$node")" "$(cat "$node/name" 2>/dev/null)" >> "$out/regulator_names.tsv"
  fi
done
printf '%s\n' "DIAGNOSTIC ONLY. No camera launched, no power writes, no OIS claim." \
  "Sysfs names/module presence do not establish functional camera hardware." \
  "Review the evidence for private metadata before sharing." > "$out/README.txt"
echo "Read-only mondrian Camera evidence: $out"
