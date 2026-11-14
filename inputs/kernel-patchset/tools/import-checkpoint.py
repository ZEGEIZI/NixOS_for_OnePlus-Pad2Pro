#!/usr/bin/env python3
"""Reconstruct a downstream checkpoint as ordered subsystem commits, without checkout.

This is a migration tool, not an old-kernel support branch. The resulting ref is
immutable extraction evidence. Ongoing work belongs on the current patch branch.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def group(path):
    if path.startswith((".github/", "AGENTS.md", "CLAUDE.md")):
        return "99-repository-policy"
    if "gunyah" in path or path in ("arch/arm64/Kbuild", "arch/arm64/mm/fault.c"):
        return "13-gunyah"
    if path.startswith("arch/arm64/configs/"):
        return "15-hardware-config"
    if path.startswith("arch/arm64/boot/dts/"):
        return "14-device-tree"
    if path.startswith("Documentation/") or path == "MAINTAINERS":
        return "01-bindings-and-documentation"
    if path.startswith(("drivers/bluetooth/", "tools/testing/selftests/bluetooth/")):
        return "10-bluetooth"
    if path.startswith(("drivers/net/", "tools/testing/selftests/net/")):
        return "09-wifi"
    if path.startswith(("sound/", "include/sound/", "include/uapi/sound/", "include/dt-bindings/sound/", "drivers/soundwire/")):
        return "08-audio"
    if path.startswith(("drivers/gpu/", "include/drm/", "tools/testing/selftests/drm/")):
        return "05-display-and-gpu"
    if path.startswith(("drivers/input/", "drivers/spi/")):
        return "06-input"
    if path.startswith(("drivers/power/supply/", "tools/testing/selftests/power_supply/")):
        return "07-power-supply"
    if path.startswith(("drivers/media/", "drivers/phy/qualcomm/phy-qcom-mipi")):
        return "12-camera-and-video"
    if path.startswith(("drivers/usb/", "drivers/tty/", "include/linux/usb/")):
        return "11-usb-and-uart"
    if path.startswith(("drivers/video/backlight/", "drivers/iio/", "drivers/thermal/", "include/linux/iio/")):
        return "04-backlight-and-thermal"
    return "03-platform-dependencies"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    def git(*cmd, data=None, env=None):
        return subprocess.check_output(["git", "-C", str(args.repo), *cmd], input=data, env=env)

    ref = "refs/patchset/extraction-checkpoint"
    if subprocess.run(["git", "-C", str(args.repo), "show-ref", "--verify", "--quiet", ref]).returncode == 0:
        parser.error(f"{ref} already exists; preserve extraction evidence")
    base = git("rev-parse", args.base).decode().strip()
    device = git("rev-parse", args.device).decode().strip()
    files = git("diff", "--name-only", base, device).decode().splitlines()
    grouped = {}
    for path in files:
        grouped.setdefault(group(path), []).append(path)
    report = {"base": base, "device": device, "groups": []}
    with tempfile.TemporaryDirectory(prefix="erhai-index-") as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / "index"),
                   GIT_AUTHOR_NAME="Erhai patchset migration", GIT_AUTHOR_EMAIL="erhai-patchset@localhost",
                   GIT_COMMITTER_NAME="Erhai patchset migration", GIT_COMMITTER_EMAIL="erhai-patchset@localhost",
                   GIT_AUTHOR_DATE="2026-11-13T12:00:00Z", GIT_COMMITTER_DATE="2026-11-13T12:00:00Z")
        git("read-tree", base, env=env)
        parent = base
        for name, paths in sorted(grouped.items()):
            entries = git("ls-tree", "-r", "-z", device, "--", *paths)
            git("update-index", "-z", "--index-info", data=entries, env=env)
            present = {item.split(b"\t", 1)[1].decode() for item in entries.split(b"\0") if item}
            for path in set(paths) - present:
                git("update-index", "--force-remove", path, env=env)
            tree = git("write-tree", env=env).decode().strip()
            body = (f"erhai: reconstruct {name[3:]} support\n\n"
                    f"Aggregate the final subsystem delta against Linux 7.2.15.\n"
                    f"Source: https://github.com/ZEGEIZI/linux-sm8750-erhai/commit/{device}\n"
                    "Original authorship and license notices remain in the files.\n"
                    "This generated commit records extraction, not original authorship.\n"
                    "Upstream-status: downstream checkpoint; audit while porting forward\n")
            parent = git("commit-tree", tree, "-p", parent, data=body.encode(), env=env).decode().strip()
            report["groups"].append({"name": name, "commit": parent, "paths": paths})
        expected = git("rev-parse", device + "^{tree}").decode().strip()
        assert tree == expected, (tree, expected)
        git("update-ref", ref, parent)
        report.update(ref=ref, reconstructed_tree=tree, device_tree=expected, exact_tree_match=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Reconstructed all {len(files)} files in {len(grouped)} groups; tree {tree}")


if __name__ == "__main__":
    main()
