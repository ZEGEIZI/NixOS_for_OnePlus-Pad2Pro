#!/usr/bin/env python3
"""Limit one Nix system profile, retaining its current generation on rollback."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess


def retention_plan(profile, keep):
    if keep < 1:
        raise ValueError("At least one generation must be retained")
    pattern = re.compile(re.escape(profile.name) + r"-([0-9]+)-link")
    current_link = Path(os.readlink(profile))
    if current_link.parent != Path(".") and current_link.parent != profile.parent:
        raise ValueError("Current generation is outside the profile directory")
    match = pattern.fullmatch(current_link.name)
    if match is None:
        raise ValueError("Profile does not select a numbered generation")
    current = int(match[1])
    generations = set()
    for entry in profile.parent.iterdir():
        match = pattern.fullmatch(entry.name)
        if match:
            if not entry.is_symlink() or not entry.exists():
                raise ValueError("Invalid generation link: " + str(entry))
            generations.add(int(match[1]))
    if current not in generations:
        raise ValueError("Current generation is missing")
    # Count the selected generation within the limit, even after a rollback.
    retained = {current}
    retained.update(sorted(generations - retained, reverse=True)[:keep - 1])
    return {"current": current, "retained": sorted(retained),
            "removed": sorted(generations - retained)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=Path("/nix/var/nix/profiles/system"))
    parser.add_argument("--keep", type=int, required=True)
    parser.add_argument("--nix-env", default="nix-env")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        plan = retention_plan(args.profile, args.keep)
        if plan["removed"] and not args.dry_run:
            # Nix takes its profile lock and independently protects the current
            # generation. Never unlink profile generations directly.
            subprocess.run([args.nix_env, "--profile", str(args.profile),
                            "--delete-generations", *map(str, plan["removed"])], check=True)
        print(json.dumps({"dry_run": args.dry_run, **plan}, sort_keys=True))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"System profile retention failed: {error}\n")


if __name__ == "__main__":
    main()
