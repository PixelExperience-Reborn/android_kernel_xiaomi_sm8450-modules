# Camera OIS initialization rollback — Xiaomi OEM source, mondrian

Reviewed against these *exact* manufacturer files:

- MiCode/vendor_qcom_opensource_camera-kernel @
  9ed4ce96d49c0759c6365627113c5f59c2407942,
  drivers/cam_sensor_module/cam_ois/cam_ois_dev.c (blob
  90071b155ed33071dd96706819a3d5d371f107e1).
- The original MiCode Camera Kbuild includes cam_ois_dev, cam_ois_core and
  cam_ois_soc when CONFIG_SPECTRA_SENSOR is enabled.
- Native PE-Reborn mondrian DeviceTrees @
  a0db12120fc6c29cc5855d3e1699c9ef73594ee3 preserve wide actuator-src
  but intentionally do not claim a standalone qcom,ois or ois-src.
- LineageOS lineage-24.0 is a **reference only**. Its mondrian Camera DTS
  also has the standalone OIS and ois-src statements commented out.
  No Lineage source is imported.

## Actual OEM driver error path repaired

The manufacturer camera_ois_driver_init() registers a platform OIS driver
then an I2C OIS driver. If the I2C registration fails, the unmodified function
returns the error while leaving the platform OIS driver registered. This can
leave dangling registrations on failure of module initialization.

The new two-line source patch unregisters the platform driver and clears its
registration flag in the exact I2C registration failure branch. It preserves
the original error return, both registration paths on success, Kbuild, device
matching (qcom,ois and qcom,cam-i2c-ois), and existing exit handling.
The patch is only applied to disposable CI source checkouts. There is no
new DT node, GPIO, guessed I2C address, camera firmware or load-order change.

Compilation checks use pinned Xiaomi OEM 5.10.81, Google LLVM23 and the
exact module symbol CRCs from the three-repository coherent build. Source
tests verify exact original Git blob, the two added statements and that both
camera compile workflows apply the same patch.

This fixes an observable lifetime bug; it does NOT assert that AK7323 has a
verified standalone OIS protocol, that Camera HAL works on AOSP 17, or that
the build can be flashed. Those are separate integration requirements.
