#!/usr/bin/env python3
"""Verify and pack the OEM Wi-Fi set without importing device identity or keys."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

PREFIX = "ath12k/WCN7860/hw2.0/oneplus/opd2413/"
MANIFEST = Path(__file__).resolve().parents[1] / "inputs/firmware/wifi.json"


def inventory(path):
    manifest = json.loads(Path(path).read_text())
    files = manifest["files"]
    names = [item["install"] for item in files]
    expected = {PREFIX + name for name in (
        "amss.bin", "aux_ucode.bin", "board.bin", "m3.bin", "qdss.cfg", "regdb.bin"
    )}
    if manifest["schema"] != 1 or len(names) != len(expected) or set(names) != expected:
        raise ValueError("Unexpected OPD2413 Wi-Fi firmware inventory")
    return files


def verify(data, item):
    if len(data) != item["size"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise ValueError(f"Firmware mismatch: {item['install']}")
    return data


def read_source(source, manifest=MANIFEST):
    source = Path(source)
    return {item["install"]: verify((source / item["install"]).read_bytes(), item)
            for item in inventory(manifest)}


def read_archive(archive, manifest=MANIFEST):
    items = inventory(manifest)
    with tarfile.open(archive, "r:") as bundle:
        members = bundle.getmembers()
        names = [member.name for member in members]
        if len(names) != len(items) or set(names) != {item["install"] for item in items}:
            raise ValueError("Unexpected Wi-Fi archive members")
        payload = {}
        for item in items:
            member = bundle.getmember(item["install"])
            if not member.isfile() or member.size != item["size"]:
                raise ValueError(f"Invalid Wi-Fi archive member: {member.name}")
            with bundle.extractfile(member) as stream:
                payload[member.name] = verify(stream.read(), item)
    return payload


def install(payload, output):
    for name, data in payload.items():
        path = Path(output) / "lib/firmware" / PurePosixPath(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def pack(source, output, manifest=MANIFEST):
    # Validate everything before creating the archive; tar metadata is fixed so
    # importing the same vendor files yields the same Nix fixed-output hash.
    payload = read_source(source, manifest)
    with Path(output).open("xb") as stream:
        with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as bundle:
            for name, data in sorted(payload.items()):
                member = tarfile.TarInfo(name)
                member.size = len(data)
                member.mode = 0o644
                bundle.addfile(member, io.BytesIO(data))
    return hashlib.sha256(Path(output).read_bytes()).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Firmware root containing ath12k/")
    parser.add_argument("output", type=Path, help="New opd2413-wifi-firmware.tar")
    args = parser.parse_args()
    print(pack(args.source, args.output), args.output)
