#!/usr/bin/env python3
"""Update or verify the pinned kShimC protocol snapshot and NixOS extension."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "inputs/kshim-protocol"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, nargs="?", help="kShimC Git checkout")
    parser.add_argument("--revision", help="Explicit upstream revision to adopt")
    parser.add_argument("--check", action="store_true", help="Check the local snapshot without a checkout")
    args = parser.parse_args()
    metadata_path = DESTINATION / "source.json"
    metadata = json.loads(metadata_path.read_text())
    if args.check:
        for name, expected in metadata["files_sha256"].items():
            assert sha(DESTINATION / name) == expected, name
        assert set(metadata["upstream_files"]) | set(metadata["patches"]) == set(metadata["files_sha256"])
        print("kShimC snapshot verified")
        return
    if args.source is None:
        parser.error("source is required unless --check is used")
    revision = args.revision or metadata["revision"]
    revision = subprocess.check_output(["git", "-C", str(args.source), "rev-parse", revision + "^{commit}"]).decode().strip()
    with tempfile.TemporaryDirectory(prefix="nixos-kshim-") as temporary:
        snapshot = Path(temporary)
        for name, upstream in metadata["upstream_files"].items():
            target = snapshot / upstream
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(subprocess.check_output(["git", "-C", str(args.source), "show", revision + ":" + upstream]))
        for patch in metadata["patches"]:
            subprocess.run(["patch", "--batch", "--forward", "--fuzz=0", "-p1", "-i", str(DESTINATION / patch)],
                           cwd=snapshot, check=True)
        for name, upstream in metadata["upstream_files"].items():
            shutil.copyfile(snapshot / upstream, DESTINATION / name)
    metadata["revision"] = revision
    metadata["files_sha256"] = {name: sha(DESTINATION / name)
                                for name in list(metadata["upstream_files"]) + metadata["patches"]}
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    print("Updated kShimC snapshot at " + revision)


if __name__ == "__main__":
    main()
