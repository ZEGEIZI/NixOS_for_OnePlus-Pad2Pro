#!/usr/bin/env python3
"""Pack and verify OPD2413 OEM Bluetooth firmware, without factory identity."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

MANIFEST = Path(__file__).resolve().parents[1] / "inputs/firmware/bluetooth.json"
PREFIX = "qca/oneplus/opd2413/"
NAMES = {"brhbtfw20.mbn", "brhbtnv20.bin", "brhperifw20.mbn", "brhperinv20.bin", "tmel_peach_20.elf"} | {
    "brhbtnv20.b" + suffix for suffix in ("2e", "34", "35", "36", "37", "38", "39", "3e", "41")
}


def inventory(manifest):
    obj = json.loads(Path(manifest).read_text())
    files = obj["files"]
    names = [i["install"] for i in files]
    if obj["schema"] != 1 or len(names) != len(NAMES) or set(names) != {PREFIX + n for n in NAMES}:
        raise ValueError("Unexpected OPD2413 Bluetooth firmware inventory")
    return files


def verify(data, item):
    if len(data) != item["size"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise ValueError("Firmware mismatch: " + item["install"])
    return data


def pack(source, output, manifest=MANIFEST):
    payload = {i["install"]: verify((Path(source) / i["install"]).read_bytes(), i) for i in inventory(manifest)}
    with Path(output).open("xb") as stream:
        with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as bundle:
            for name, data in sorted(payload.items()):
                member = tarfile.TarInfo(name)
                member.size, member.mode = len(data), 0o644
                bundle.addfile(member, io.BytesIO(data))
    return hashlib.sha256(Path(output).read_bytes()).hexdigest()


def stage(archive, output, manifest=MANIFEST):
    items = inventory(manifest)
    with tarfile.open(archive, "r:") as bundle:
        members = bundle.getmembers()
        if len(members) != len(items) or {m.name for m in members} != {i["install"] for i in items}:
            raise ValueError("Unexpected Bluetooth archive members")
        payload = {}
        for item in items:
            member = bundle.getmember(item["install"])
            if not member.isfile() or member.size != item["size"]:
                raise ValueError("Invalid Bluetooth archive member: " + member.name)
            with bundle.extractfile(member) as stream:
                payload[member.name] = verify(stream.read(), item)
    for name, data in payload.items():
        target = Path(output) / "lib/firmware" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("pack", "stage"))
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args()
    result = globals()[args.action](args.source, args.output, args.manifest)
    if result:
        print(result)
