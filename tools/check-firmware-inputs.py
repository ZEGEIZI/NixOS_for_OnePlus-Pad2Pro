#!/usr/bin/env python3
"""Verify all bundled firmware archives and their complete file inventories."""
import argparse
import hashlib
import json
from pathlib import Path

from firmware_archive import read_archive
from wifi_firmware import inventory as wifi_inventory
from bluetooth_firmware import inventory as bluetooth_inventory


def verify(root):
    root = Path(root)
    inventory = json.loads((root / "archives.json").read_text())
    assert inventory["schema"] == 1
    assert set(inventory["archives"]) == {"base", "wifi", "bluetooth"}
    total = 0
    for name, entry in inventory["archives"].items():
        archive = root / entry["file"]
        manifest = root / entry["manifest"]
        assert archive.stat().st_size == entry["size"], name
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == entry["sha256"], name
        if name == "wifi":
            wifi_inventory(manifest)
        elif name == "bluetooth":
            bluetooth_inventory(manifest)
        payload = read_archive(archive, manifest)
        if name == "base":
            assert not any(path.startswith("ath12k/WCN7860/hw2.0/") for path in payload)
        total += len(payload)
    print(f"Verified 3 bundled archives and {total} firmware files")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path,
                        default=Path(__file__).resolve().parents[1] / "inputs/firmware")
    verify(parser.parse_args().inputs)
