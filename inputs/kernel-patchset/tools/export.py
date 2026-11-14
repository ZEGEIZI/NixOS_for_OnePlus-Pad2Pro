#!/usr/bin/env python3
"""Export the authoritative linear Git branch; never hand-edit generated patches."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--base", required=True)
    p.add_argument("--head", default="HEAD")
    p.add_argument("--tarball", type=Path, required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--release", required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]

    def git(*cmd):
        return subprocess.check_output(["git", "-C", str(args.repo), *cmd])

    base = git("rev-parse", args.base + "^{commit}").decode().strip()
    head = git("rev-parse", args.head + "^{commit}").decode().strip()
    if git("status", "--porcelain"):
        p.error("finish all source edits and any rebase before exporting")
    # Validate every source blob before changing the previous generated release.
    configs = {name: git("show", f"{head}:arch/arm64/configs/{name}")
               for name in ["sm8750-peripherals.config", "erhai-firstboot.config"]}
    deleted = set(git("diff", "--name-only", "--diff-filter=D", base, head).decode().splitlines())
    result = {filename: None if filename in deleted else hashlib.sha256(git("show", head + ":" + filename)).hexdigest()
              for filename in git("diff", "--name-only", base, head).decode().splitlines()}
    tarball_digest = hashlib.sha256(args.tarball.read_bytes()).hexdigest()
    if git("rev-list", "--merges", f"{base}..{head}"):
        p.error("patch branch must be linear")
    commits = git("rev-list", "--reverse", f"{base}..{head}").decode().splitlines()
    directory = root / "patchsets" / ".".join(args.version.split(".")[:2])
    patches = directory / "patches"
    patches.mkdir(parents=True, exist_ok=True)
    old_manifest = directory / "manifest.json"
    if old_manifest.exists():
        old = json.loads(old_manifest.read_text())
        for patch in old["patches"]:
            path = directory / patch["file"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != patch["sha256"]:
                p.error(f"generated patch was edited: {path}")
        for config in old["configs"]:
            path = root / config["file"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != config["sha256"]:
                p.error(f"generated configuration was edited: {path}")
    entries = []
    for index, commit in enumerate(commits, 1):
        subject = git("show", "-s", "--format=%f", commit).decode().strip()
        filename = f"{index:04d}-{subject[:110]}.patch"
        content = git("format-patch", "--stdout", "--no-signature", "--no-numbered", "-1", commit)
        (patches / filename).write_bytes(content)
        entries.append({"file": "patches/" + filename, "commit": commit,
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "depends_on": [entries[-1]["commit"]] if entries else [],
                        "upstream_status": "downstream; see provenance/port-7.3.json"})
    # Only delete files that the previous generated manifest owned.
    names = {e["file"] for e in entries}
    if old_manifest.exists():
        for entry in old["patches"]:
            if entry["file"] not in names:
                (directory / entry["file"]).unlink()
    (directory / "series").write_text("".join(e["file"] + "\n" for e in entries))
    config_entries = []
    for name, content in configs.items():
        (root / "configs" / name).write_bytes(content)
        config_entries.append({"file": "configs/" + name,
                               "source": "arch/arm64/configs/" + name,
                               "sha256": hashlib.sha256(content).hexdigest()})
    manifest = {"schema": 1, "project": "linux-sm8750-erhai-patchset", "release": args.release,
                "series": ".".join(args.version.split(".")[:2]),
                "minimum_version": args.version,
                "upstream": {"version": args.version, "tag": args.base, "commit": base,
                             "url": f"https://cdn.kernel.org/pub/linux/kernel/v{args.version.split('.')[0]}.x/linux-{args.version}.tar.xz",
                             "sha256": tarball_digest},
                "branch": "patchset-" + ".".join(args.version.split(".")[:2]),
                "head": head, "patches": entries, "configs": config_entries,
                "result_files_sha256": result,
                "validation": {"hardware": "pending", "full_build": "pending"}}
    old_manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Exported {len(entries)} commits / {len(result)} changed files at {head}")


if __name__ == "__main__":
    main()
