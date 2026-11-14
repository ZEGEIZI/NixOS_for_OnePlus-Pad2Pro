#!/usr/bin/env python3
"""Verify a release and optionally replay it on a fresh official source archive."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile


def verify_release(root, series):
    directory = root / "patchsets" / series
    manifest = json.loads((directory / "manifest.json").read_text())
    paths = [entry["file"] for entry in manifest["patches"]]
    assert (directory / "series").read_text().splitlines() == paths
    assert len(set(paths)) == len(paths), "duplicate patches"
    for entries, parent in [(manifest["patches"], directory), (manifest["configs"], root)]:
        for entry in entries:
            path = parent / entry["file"]
            assert path.resolve().is_relative_to(root.resolve()), "path escapes release"
            assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"], path
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--series", default="7.3")
    p.add_argument("--tarball", type=Path)
    p.add_argument("--destination", type=Path)
    p.add_argument("--forward", action="store_true", help="same-series newer archive; needs a separate build and device acceptance")
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    m = verify_release(root, args.series)
    manifest_file = root / "patchsets" / args.series / "manifest.json"
    report = {"release": m["release"], "patch_head": m["head"],
              "manifest_sha256": hashlib.sha256(manifest_file.read_bytes()).hexdigest(),
              "manifest_verified": True, "replayed": False,
              "source_equivalent": False, "hardware_verified": False}
    if args.tarball:
        if args.destination is None or args.destination.exists():
            p.error("replay requires a new --destination")
        digest = hashlib.sha256(args.tarball.read_bytes()).hexdigest()
        if not args.forward:
            assert digest == m["upstream"]["sha256"], "wrong official archive"
        args.destination.mkdir(parents=True)
        with tarfile.open(args.tarball) as archive:
            names = {Path(member.name).parts[0] for member in archive.getmembers()}
            assert len(names) == 1, names
            archive.extractall(args.destination, filter="data")
        source = args.destination / names.pop()
        makefile = (source / "Makefile").read_text().splitlines()
        version = ".".join(next(line.split("=", 1)[1].strip() for line in makefile
                                if line.startswith(key + " ="))
                           for key in ["VERSION", "PATCHLEVEL", "SUBLEVEL"])
        assert next(line.split("=", 1)[1].strip() for line in makefile
                    if line.startswith("EXTRAVERSION =")) == "", "requires a released kernel"
        assert version.startswith(m["series"] + "."), version
        assert tuple(map(int, version.split("."))) >= tuple(map(int, m["minimum_version"].split(".")))
        for entry in m["patches"]:
            with (root / "patchsets" / args.series / entry["file"]).open("rb") as patch:
                applied = subprocess.run(["patch", "--batch", "--forward", "--fuzz=0", "-p1"],
                                         cwd=source, stdin=patch, capture_output=True)
                if applied.returncode:
                    raise SystemExit(f"Failed patch: {entry['file']}\n" +
                                     applied.stdout.decode() + applied.stderr.decode())
        if not args.forward:
            for file, expected in m["result_files_sha256"].items():
                if expected is None:
                    assert not (source / file).exists(), file
                else:
                    assert hashlib.sha256((source / file).read_bytes()).hexdigest() == expected, file
        for entry in m["configs"]:
            assert (source / entry["source"]).read_bytes() == (root / entry["file"]).read_bytes()
        report.update(replayed=True, source_equivalent=not args.forward,
                      version=version, tarball_sha256=digest, source=str(source.resolve()))
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
