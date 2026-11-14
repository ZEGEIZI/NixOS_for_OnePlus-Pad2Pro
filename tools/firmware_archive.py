#!/usr/bin/env python3
"""Pack and stage the project's hash-pinned base firmware inventory."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

MANIFEST = Path(__file__).resolve().parents[1] / "inputs/firmware/base.json"


def inventory(manifest):
    obj = json.loads(Path(manifest).read_text())
    files = obj["files"]
    names = [item["install"] for item in files]
    if obj["schema"] != 1 or not names or len(names) != len(set(names)):
        raise ValueError("Invalid firmware inventory")
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or str(path) != name or not path.parts:
            raise ValueError("Unsafe firmware path: " + name)
    return files


def verify(data, item):
    if len(data) != item["size"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise ValueError("Firmware mismatch: " + item["install"])
    return data


def pack(source, output, manifest=MANIFEST):
    payload = {item["install"]: verify((Path(source) / item["install"]).read_bytes(), item)
               for item in inventory(manifest)}
    with Path(output).open("xb") as stream:
        with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as bundle:
            for name, data in sorted(payload.items()):
                member = tarfile.TarInfo(name)
                member.size, member.mode = len(data), 0o644
                bundle.addfile(member, io.BytesIO(data))
    return hashlib.sha256(Path(output).read_bytes()).hexdigest()


def read_archive(archive, manifest=MANIFEST):
    items = inventory(manifest)
    with tarfile.open(archive, "r:") as bundle:
        members = bundle.getmembers()
        if len(members) != len(items) or {m.name for m in members} != {i["install"] for i in items}:
            raise ValueError("Unexpected firmware archive members")
        payload = {}
        for item in items:
            member = bundle.getmember(item["install"])
            if not member.isfile() or member.size != item["size"]:
                raise ValueError("Invalid firmware archive member: " + member.name)
            with bundle.extractfile(member) as stream:
                payload[member.name] = verify(stream.read(), item)
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Firmware root with the paths listed in base.json")
    parser.add_argument("output", type=Path, help="New opd2413-base-firmware.tar")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args()
    print(pack(args.source, args.output, args.manifest))
