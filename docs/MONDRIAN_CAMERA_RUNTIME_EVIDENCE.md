# Mondrian Camera runtime evidence — read only

Pinned Xiaomi OEM 5.10.81 + LLVM23 whole-component builds are green:

- https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/45033970467
- https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/45033976806

These prove compile-time component ABI and FDT connectivity only. The next
evidence must come from a running mondrian, not from copying another ROM's
OIS node or inferring an AK7323 power sequence.

Copy tools/collect_mondrian_camera_runtime.sh to /data/local/tmp on the
actual POCO F5 Pro / Redmi K60. With KernelSU/root or adb shell, run:

    sh /data/local/tmp/collect_mondrian_camera_runtime.sh

The script creates a private directory beneath /data/local/tmp and prints
its full path. It ONLY reads properties, /proc/modules and read-only names
exposed through /sys/class/video4linux, /sys/bus/i2c/devices and
/sys/class/regulator. No Camera HAL starts, no I2C transfer, no GPIO,
regulator, sysfs, module-loading or power-state writes. No logcat, dmesg
or dumpsys are collected by default. Review files before sharing.

On a trusted workstation, after transferring the directory:

    python3 tools/check_mondrian_camera_runtime.py \
      --input /path/to/capture --out /path/to/camera-runtime.json

The parser checks a mondrian capture and reports observable module names,
V4L2 subdevices and I2C/regulator names. Absence from /proc/modules can
also mean a driver was built into the kernel. This alone is NOT proof that
the camera HAL works, AK7323 hardware stabilizes, power cycles succeed or
that the diagnostic DTBO is flashable.

No change to OEM kernel, native device trees, Qualcomm Camera, Audio,
VIDC, WLAN, MMRM, WL2866D power states or product module loading.
