#!/usr/bin/env python3
"""Fail-closed OEM mondrian camera OIS/EEPROM power evidence gate.

The CamX profiles describe user-space power records, not an independently
qualified AK7323 kernel subdevice. Inspect the *compiled* three Cape camera
boards before approving any new OIS or product modules.load selection.
No camera power registers, GPIO or flash triggers are written by this tool.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

EXPECTED = (
    ("wide", "OV64B40", "GT24P128E", "WL2866D_AVDD1", 15, ("cam_vdig", "cam_clk", "cam_vana", "cam_v_custom1")),
    ("front", "OV16A1Q", "GT24P64E", "WL2866D_AVDD1", 15, ("cam_clk", "cam_vana")),
    ("ultra", "OV08D10", "P24C64F", "WL2866D_AVDD1", 15, ("cam_vana", "cam_clk")),
    ("macro", "OV02B10", "GT24P64E", "VIO", 3, ("cam_vio", "cam_clk")),
)
CAPE_BASES = ("cape", "cape-v2", "capep")


def verify_factory_profiles(hal, camera):
    if hal.get("device") != "mondrian" or camera.get("device") != "mondrian":
        raise ValueError("not the mondrian factory Camera manifest")
    if camera.get("factory_camera_hal_profiles") != hal:
        raise ValueError("compiled Camera build is not tied to the selected factory HAL profiles")
    if {i.get("camera_id") for i in hal.get("slots", [])} != set(range(4)):
        raise ValueError("factory camera ID set drift")
    if len(hal["slots"]) != 4:
        raise ValueError("factory Camera slot count drift")
    records = []
    for index, (role, sensor, eeprom, rail, typ, names) in enumerate(EXPECTED):
        item = hal["slots"][index]
        if (item["camera_id"], item["role"], item["sensor"], item["eeprom"]) != (
                index, role, sensor, eeprom):
            raise ValueError(f"factory Camera sensor / EEPROM mismatch: {role}")
        power = item.get("eeprom_power", {})
        if power != {"rail": rail, "sequence_type": typ,
                     "enable_delay_ms": 3, "disable_delay_ms": 0}:
            raise ValueError(f"factory EEPROM power record drift: {role}")
        variants = item.get("profiles", {})
        if not variants or any(
                set(digest) != {"miui", "hyper"} or any(
                    not re.fullmatch(r"[0-9a-f]{40}", s) for s in digest.values())
                for digest in variants.values()):
            raise ValueError("factory CamX profile provenance missing: " + role)
        if role == "wide":
            ois = item.get("ois_control", {})
            if item.get("actuator") != "DW9800V" or item.get("ois") != "AK7323":
                raise ValueError("unverified main Camera actuator/OIS identity")
            if ois != {
                    "standalone_subdevice_in_stock_dt": False,
                    "power_records_per_profile": 2,
                    "zero_filled_power_records_per_profile": 2,
                    "register_data_records_per_profile": 13,
                    "nonzero_register_data_records_per_profile": 0,
                    "transport": "unverified"}:
                raise ValueError("AK7323 control is not qualified by factory records")
        elif item.get("ois") is not None or item.get("actuator") is not None:
            raise ValueError("unqualified extra actuator/OIS subdevice for " + role)
        records.append({
            "camera_id": index, "role": role, "sensor": sensor, "eeprom": eeprom,
            "factory_eeprom_power_rail": rail, "power_record_type": typ,
            "enable_delay_ms": 3, "disable_delay_ms": 0,
            "expected_eeprom_fdt_regulator_names": list(names),
        })
    if camera.get("board_rear_flash_switch0_mask") != 1:
        raise ValueError("mondrian diagnostic PM8350C flash mask drift")
    if camera.get("production_camera_dtbo_approved") is not False:
        raise ValueError("unverified Camera DTBO wrongly approved for product")
    if set(camera.get("per_board", {})) != set(CAPE_BASES):
        raise ValueError("missing one of the compiled Cape camera boards")
    return records


def fdtget(image, node, property_name=None, fmt=None, *, tool="fdtget"):
    # dtc fdtget accepts u (unsigned 32-bit), i (signed), s (string);
    # d is a printf conversion, NOT a valid -t argument (AOSP 17 dtc).
    if fmt not in (None, "u", "s") or (property_name is None and fmt is not None):
        raise ValueError("invalid or misplaced fdtget format: " + repr(fmt))
    args = [tool]
    if property_name is None:
        args += ["-p"]
    elif fmt is not None:
        args += ["-t", fmt]
    args += [str(image), node]
    if property_name is not None:
        args.append(property_name)
    completed = subprocess.run(args, capture_output=True, text=True, check=False)
    if completed.returncode:
        # Preserve actual libfdt errors, rather than a bare exit status
        # that obscures wrong CLI flags, missing nodes and corrupt DTBs.
        diagnostic = completed.stderr.strip() or "no stderr"
        raise ValueError(
            "fdtget failed for " + str(image) + " " + node + " " +
            repr(property_name) + " (type=" + repr(fmt) + "): " +
            diagnostic[:1000])
    return completed.stdout.strip()


def inspect_compiled_boards(camera, out_dir, records, *, fdt_tool="fdtget"):
    output = {}
    for cape in CAPE_BASES:
        image = out_dir / "images" / (cape + "-mondrian-camera-board-diagnostic.dtb")
        if not image.is_file() or image.stat().st_size < 100:
            raise ValueError("missing actual compiled Camera FDT: " + str(image))
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        board = camera["per_board"][cape]
        if board.get("camera_board_merged_sha256") != digest:
            raise ValueError("Camera FDT differs from compiled three-repo manifest")
        slots = board.get("camera_slots", {})
        if set(slots) != {record["role"] for record in records}:
            raise ValueError("missing factory Camera DTB slot in " + cape)
        result = {}
        for item in records:
            role, index = item["role"], item["camera_id"]
            entry = slots[role]
            sensor, eeprom = entry["sensor_node"], entry["eeprom_node"]
            if entry.get("factory_camera_id") != index or entry.get("ois_src_present") is not False:
                raise ValueError("camera slot/OIS overlay drift: " + role)
            sensor_props = set(fdtget(image, sensor, tool=fdt_tool).splitlines())
            eeprom_props = set(fdtget(image, eeprom, tool=fdt_tool).splitlines())
            for name in ("cell-index", "eeprom-src", "csiphy-sd-index"):
                if name not in sensor_props:
                    raise ValueError("missing active sensor routing " + name + " " + role)
            if "ois-src" in sensor_props:
                raise ValueError("unqualified standalone OIS connection: " + role)
            names = tuple(fdtget(image, eeprom, "regulator-names", "s",
                                 tool=fdt_tool).split())
            if names != tuple(item["expected_eeprom_fdt_regulator_names"]):
                raise ValueError("compiled EEPROM regulator order drift: " + role)
            if "regulator-names" not in eeprom_props:
                raise ValueError("EEPROM power regulator-name property missing: " + role)
            if role == "wide":
                if "actuator-src" not in sensor_props:
                    raise ValueError("primary DW9800V actuator link missing")
            elif "actuator-src" in sensor_props:
                raise ValueError("unexpected other Camera actuator: " + role)
            if role == "ultra":
                if "gpio-reset" in eeprom_props:
                    raise ValueError("ultrawide EEPROM would incorrectly toggle MCLK as reset")
                if "gpio-reset" not in sensor_props:
                    raise ValueError("ultrawide sensor GPIO reset property missing")
                # AOSP 17 dtc: -t u reads a 32-bit unsigned cell.
                if fdtget(image, sensor, "gpio-reset", "u", tool=fdt_tool) != "1":
                    raise ValueError("ultrawide sensor reset index is not TLMM24")
            result[role] = {"camera_id": index, "eeprom_regulator_names": list(names),
                            "standalone_ois_link_absent": True}
        output[cape] = {"compiled_dtb_sha256": digest, "slots": result}
    return output


def audit(profiles, camera, board_dir, *, fdt_tool="fdtget"):
    records = verify_factory_profiles(profiles, camera)
    checked = inspect_compiled_boards(camera, board_dir, records, fdt_tool=fdt_tool)
    return {
        "device": "mondrian", "android_base": "AOSP 17",
        "factory_camx_eeprom_power_records_consistent": True,
        "compiled_fdt_eeprom_regulator_names_consistent": True,
        "original_wide_dw9800v_actuator_link_preserved": True,
        "wide_ak7323_profile_present": True,
        "wide_ak7323_standalone_ois_source_qualified": False,
        "wide_ois_control_records_nonzero": False,
        "factory_sensor_eeprom_power_order": records,
        "per_board": checked,
        "sensor_and_ois_power_sequence_hardware_verified": False,
        "physical_camera_ois_verified": False,
        "product_camera_dtbo_or_modules_load_approved": False,
        "status": "OEM_CAMX_POWER_AND_OIS_STATIC_EVIDENCE_ONLY",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profiles", type=Path, required=True)
    p.add_argument("--camera-evidence", type=Path, required=True)
    p.add_argument("--board-build", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    try:
        report = audit(json.loads(args.profiles.read_text()),
                       json.loads(args.camera_evidence.read_text()),
                       args.board_build)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        p.error("Camera OIS/power evidence incomplete: " + str(exc))
    print("[PASS] Factory EEPROM power records and three compiled mondrian Camera FDTs checked")
    print("[BLOCKED] AK7323 firmware/physical bus/OIS power and sensor runtime not qualified")


if __name__ == "__main__":
    main()
