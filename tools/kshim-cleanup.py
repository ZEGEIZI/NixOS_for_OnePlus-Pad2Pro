#!/usr/bin/env python3
"""Synchronize the kShimC NixOS catalog with retained system generations."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from kshim_protocol import protocol

spec = importlib.util.spec_from_file_location("installer", Path(__file__).with_name("kshim-install.py"))
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

STORE_SYSTEM = re.compile(r"/nix/store/[a-z0-9]{32}-[^/]+\Z")


def system_link(path):
    if not path.is_symlink():
        raise ValueError("Missing system symlink: " + str(path))
    target = str(path.resolve(strict=True))
    if not STORE_SYSTEM.fullmatch(target):
        raise ValueError("Invalid system path: " + target)
    return target


def snapshot(profiles, runtime):
    generations = {}
    for path in profiles.glob("system-*-link"):
        match = re.fullmatch(r"system-([0-9]+)-link", path.name)
        if match:
            generations[int(match[1])] = system_link(path)
    # These can differ after switch/boot; all three must survive cleanup.
    protected = {name: system_link(path) for name, path in {
        "profile": profiles / "system", "activated": runtime / "current-system",
        "booted": runtime / "booted-system",
    }.items()}
    return {"generations": generations, "protected": protected}


def selection(catalog, systems, state, limit, keep_previous, pinned, default):
    keep = {catalog["current"]}
    if keep_previous and catalog["previous"] != "none":
        keep.add(catalog["previous"])
    for version in pinned:
        protocol.identifier(version)
        if version not in catalog["versions"]:
            raise ValueError("Pinned version is not in the catalog: " + version)
        keep.add(version)
    if default.startswith("nixos/"):
        version = default.removeprefix("nixos/")
        if version not in ("current", "previous"):
            if version not in catalog["versions"]:
                raise ValueError("Shared default is missing from the catalog")
            keep.add(version)
        elif version == "previous" and catalog["previous"] != "none":
            keep.add(catalog["previous"])
    numbers = sorted(state["generations"], reverse=True)
    if limit:
        numbers = numbers[:limit]
    wanted = {state["generations"][n] for n in numbers}
    wanted.update(state["protected"].values())
    keep.update(v for v in catalog["versions"] if systems[v] in wanted)
    listed = [v for v in catalog["versions"] if v in keep]
    # Preserve previous's identity if selected; otherwise choose the next
    # surviving entry, so the loader's previous alias never dangles.
    previous = catalog["previous"] if catalog["previous"] in keep else next(
        (v for v in listed if v != catalog["current"]), "none")
    return listed, previous, wanted


def cleanup(args):
    if not args.staging_root and os.geteuid() != 0:
        raise ValueError("Live cleanup requires root")
    if args.configuration_limit < 0:
        raise ValueError("configuration-limit must be nonnegative")
    with installer.boot_mount(args) as boot:
        system = protocol.existing_system(boot, "nixos")
        with protocol.locked(boot / ".nixos-install.lock"), \
                protocol.locked(system / ".update.lock"), \
                protocol.locked(boot / "kshim/.config.lock"):
            state = snapshot(args.profiles_dir, args.runtime_dir)
            catalog = protocol.versions(system)
            if catalog is None:
                raise ValueError("Missing NixOS catalog")
            shared_path = boot / "kshim/boot.conf"
            shared_bytes = shared_path.read_bytes()
            shared = protocol.read_config(shared_path, ("format", "systems", "default", "timeout_ms"))
            roots = boot / ".nixos-gcroots" if args.staging_root else Path("/nix/var/nix/gcroots/kshim-nixos")
            if roots.resolve() != roots or not roots.is_dir():
                raise ValueError("Invalid GC root directory")
            folders = {p.name for p in (system / "versions").iterdir()}
            if not set(catalog["versions"]) <= folders:
                raise ValueError("Missing catalog payloads")
            systems, manifests = {}, {}
            # Identify entries by their roots first. Unlisted leftovers from
            # interrupted deletion may already have partly removed payloads.
            for version in sorted(folders):
                protocol.identifier(version)
                folder = system / "versions" / version
                root = roots / version
                if folder.is_symlink() or not folder.is_dir():
                    raise ValueError("Invalid version directory: " + version)
                if not root.is_symlink() or not STORE_SYSTEM.fullmatch(os.readlink(root)):
                    raise ValueError("Invalid GC root: " + version)
                systems[version] = os.readlink(root)
            listed, previous, wanted = selection(catalog, systems, state, args.configuration_limit,
                                                  args.keep_previous, args.keep_version, shared["default"])
            # Re-list referenced leftovers only after verifying their payloads.
            listed += sorted(v for v in folders - set(listed) if systems[v] in wanted)
            for version in sorted(folders):
                if version not in catalog["versions"] and version not in listed:
                    continue
                manifest = protocol.version_manifest(system, version)
                init = [p.removeprefix("init=") for p in manifest["cmdline"].split() if p.startswith("init=")]
                if len(init) != 1 or not init[0].endswith("/init") or not STORE_SYSTEM.fullmatch(init[0][:-5]):
                    raise ValueError("Invalid init reference: " + version)
                target = init[0][:-5]
                if systems[version] != target:
                    raise ValueError("GC root differs from manifest: " + version)
                manifests[version] = manifest
            remove = sorted(folders - set(listed))
            orphan_roots = []
            root_targets = {}
            for root in roots.iterdir():
                protocol.identifier(root.name)
                if not root.is_symlink() or not STORE_SYSTEM.fullmatch(os.readlink(root)):
                    raise ValueError("Invalid GC root: " + str(root))
                root_targets[root.name] = os.readlink(root)
                if root.name not in folders and root_targets[root.name] not in wanted:
                    orphan_roots.append(root.name)
            report = {"dry_run": args.dry_run, "retained": listed, "removed": remove,
                      "orphan_roots_removed": sorted(orphan_roots), "previous": previous,
                      "protected_systems": state["protected"], "system_profiles_changed": False}
            if snapshot(args.profiles_dir, args.runtime_dir) != state:
                raise ValueError("System profiles/runtime changed during cleanup; retry")
            changed = listed != catalog["versions"] or previous != catalog["previous"]
            if args.dry_run or not (changed or remove or orphan_roots):
                return report
            backup = args.state_dir.absolute()
            if backup.resolve() != backup or boot == backup or boot in backup.parents:
                raise ValueError("State directory must be outside /boot without symlinks")
            backup.mkdir(parents=True, exist_ok=True)
            protocol.atomic_text(backup / "last-cleanup.json", json.dumps({
                "before": catalog, "shared_config": shared_bytes.decode(),
                "manifests": manifests, "gcroots": root_targets, "plan": report,
            }, indent=2) + "\n")
            # Menu first, payloads second, GC roots last. Interruption can leak
            # files/roots but must never leave a selected entry unprotected.
            protocol.write_versions(system, catalog["current"], previous, listed)
            for version in remove:
                shutil.rmtree(system / "versions" / version)
            protocol.sync_dir(system / "versions")
            for version in remove + orphan_roots:
                (roots / version).unlink()
            protocol.sync_dir(roots)
            if shared_path.read_bytes() != shared_bytes:
                raise ValueError("Shared menu changed during cleanup")
            protocol.atomic_text(backup / "last-result.json", json.dumps(report, indent=2) + "\n")
            return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boot-dir", type=Path, default=Path("/boot"))
    parser.add_argument("--partuuid")
    parser.add_argument("--partlabel", default="KShinC_BOOT")
    parser.add_argument("--configuration-limit", type=int, default=10)
    parser.add_argument("--keep-version", action="append", default=[])
    parser.add_argument("--no-keep-previous", dest="keep_previous", action="store_false")
    parser.add_argument("--dry-run", action="store_true")
    parser.set_defaults(staging_root=None, profiles_dir=Path("/nix/var/nix/profiles"),
                        runtime_dir=Path("/run"), state_dir=Path("/var/lib/kshim"))
    args = parser.parse_args()
    try:
        print(json.dumps(cleanup(args), sort_keys=True))
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"kShimC cleanup failed: {error}\n")


if __name__ == "__main__":
    main()
