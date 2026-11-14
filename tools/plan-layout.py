#!/usr/bin/env python3
"""Read a GPT header capture and print a proposed layout. Never writes a device."""
import argparse
import json
from pathlib import Path
import struct
import zlib


def plan(data, sector, root_gib):
    header = bytearray(data[sector:sector * 2])
    if header[:8] != b"EFI PART":
        raise ValueError("Missing primary GPT header")
    size, expected = struct.unpack_from("<II", header, 12)
    if not 92 <= size <= sector:
        raise ValueError("Invalid GPT header size")
    struct.pack_into("<I", header, 16, 0)
    if zlib.crc32(header[:size]) != expected:
        raise ValueError("GPT header checksum mismatch")
    table_lba, count, entry_size, table_crc = struct.unpack_from("<QIII", header, 72)
    if entry_size < 128 or count > 4096:
        raise ValueError("Unsupported GPT entry array")
    entries = data[table_lba * sector:table_lba * sector + count * entry_size]
    if len(entries) != count * entry_size or zlib.crc32(entries) != table_crc:
        raise ValueError("Missing/corrupt GPT entries")
    partitions = []
    for index in range(count):
        entry = entries[index * entry_size:(index + 1) * entry_size]
        if entry[:16] == bytes(16):
            continue
        start, end = struct.unpack_from("<QQ", entry, 32)
        partitions.append({"number": index + 1, "label": entry[56:128].decode("utf-16-le").rstrip("\0"),
                           "start_lba": start, "end_lba": end})
    partitions.sort(key=lambda p: p["start_lba"])
    labels = [p["label"] for p in partitions[-3:]]
    if labels not in (["userdata", "ARMADA_BOOT", "ARMADA_ROOT"],
                      ["userdata", "KShinC_BOOT", "NixOS_Root"]):
        raise ValueError("Expected verified userdata + two Linux partitions at the end; review other layouts manually")
    old_data, old_boot, old_root = partitions[-3:]
    root_bytes, boot_bytes = root_gib * 2**30, 2**30
    new_root_start = (old_root["end_lba"] + 1) - root_bytes // sector
    new_boot_start = new_root_start - boot_bytes // sector
    if root_gib <= 0 or new_boot_start <= old_data["start_lba"]:
        raise ValueError("Requested Linux space does not fit")
    if (new_boot_start * sector) % 2**20 or (new_root_start * sector) % 2**20:
        raise ValueError("Proposed boundaries are not MiB aligned")
    new = [
        dict(old_data, end_lba=new_boot_start - 1),
        dict(old_boot, label="KShinC_BOOT", start_lba=new_boot_start, end_lba=new_root_start - 1),
        dict(old_root, label="NixOS_Root", start_lba=new_root_start),
    ]
    for p in new:
        p["bytes"] = (p["end_lba"] - p["start_lba"] + 1) * sector
        p["GiB"] = round(p["bytes"] / 2**30, 6)
    return {"mode": "PLAN_ONLY", "logical_sector_bytes": sector, "android_userdata_recreation_required": True,
            "old_linux_data_destroyed": True, "preserved_partition_numbers": [p["number"] for p in partitions[:-3]],
            "current_tail": partitions[-3:], "proposed_tail": new}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gpt_capture", type=Path)
    parser.add_argument("--sector-bytes", type=int, choices=[512, 4096], required=True)
    parser.add_argument("--root-gib", type=int, default=200)
    args = parser.parse_args()
    try:
        print(json.dumps(plan(args.gpt_capture.read_bytes(), args.sector_bytes, args.root_gib), indent=2))
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + "\n")
