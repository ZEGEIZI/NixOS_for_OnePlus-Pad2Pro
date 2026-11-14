#!/usr/bin/env python3
"""Prune an explicitly reviewed kShimC catalog, retaining the selected versions."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from kshim_protocol import protocol

spec = importlib.util.spec_from_file_location("installer", Path(__file__).with_name("kshim-install.py"))
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def runtime_check(current):
    for name in ("/run/booted-system", "/run/current-system", "/nix/var/nix/profiles/system"):
        if str(Path(name).resolve(strict=True)) != current:
            raise ValueError("Running/activated/profile system changed: " + name)


def prune(args):
    plan = json.loads(args.plan.read_text())
    current = protocol.identifier(plan["current"])
    previous = plan["previous"]
    if previous != "none":
        protocol.identifier(previous)
    expected = plan["expected"]
    retain = plan.get("retain", [])
    if not isinstance(retain, list) or any(not isinstance(v, str) for v in retain):
        raise ValueError("Retain must be a list of version identifiers")
    for version in retain:
        protocol.identifier(version)
    keep = [current] + ([] if previous == "none" else [previous]) + retain
    if (current == previous or len(set(keep)) != len(keep)
            or not set(keep) <= set(expected) or len(expected) <= len(keep)):
        raise ValueError("Plan must retain distinct selected versions including current and remove an old version")
    for version, toplevel in expected.items():
        protocol.identifier(version)
        if not re.fullmatch(r"/nix/store/[a-z0-9]{32}-[^/]+", toplevel):
            raise ValueError("Invalid expected system path")
    remove = sorted(set(expected) - set(keep))
    if not args.staging_root:
        if os.geteuid() != 0:
            raise ValueError("Live cleanup requires root")
        runtime_check(expected[current])
    backup_parent = args.backup_dir.absolute()
    if backup_parent.resolve() != backup_parent:
        raise ValueError("Backup path contains symlinks")
    boot_path = (args.staging_root or args.boot_dir).absolute()
    if backup_parent == boot_path or boot_path in backup_parent.parents:
        raise ValueError("Backup must be outside the boot filesystem")
    backup_parent.mkdir(parents=True, exist_ok=True)
    report = {}
    with installer.boot_mount(args) as boot:
        system = protocol.existing_system(boot, "nixos")
        with protocol.locked(boot / ".nixos-install.lock"), \
                protocol.locked(system / ".update.lock"), \
                protocol.locked(boot / "kshim/.config.lock"):
            catalog = protocol.versions(system)
            if (catalog is None or set(catalog["versions"]) != set(expected)
                    or catalog["current"] != current
                    or catalog["previous"] != plan["expected_previous"]):
                raise ValueError("Catalog changed; review a new plan")
            if {p.name for p in (system / "versions").iterdir()} != set(expected):
                raise ValueError("Unexpected version directories")
            config_path = boot / "kshim/boot.conf"
            config_bytes = config_path.read_bytes()
            shared = protocol.read_config(config_path, ("format", "systems", "default", "timeout_ms"))
            if shared["default"] in {"nixos/" + version for version in remove}:
                raise ValueError("Cannot remove the explicit shared default")
            roots = boot / ".nixos-gcroots" if args.staging_root else Path("/nix/var/nix/gcroots/kshim-nixos")
            if roots.resolve() != roots or not roots.is_dir():
                raise ValueError("Invalid GC root directory")
            manifests = {}
            for version, toplevel in expected.items():
                # Check every payload and init reference before changing the menu.
                manifest = protocol.version_manifest(system, version)
                if [p for p in manifest["cmdline"].split() if p.startswith("init=")] != ["init=" + toplevel + "/init"]:
                    raise ValueError("Unexpected init reference: " + version)
                root = roots / version
                if not root.is_symlink() or os.readlink(root) != toplevel:
                    raise ValueError("GC root changed: " + version)
                manifests[version] = manifest
            if not args.staging_root:
                runtime_check(expected[current])
            backup = Path(tempfile.mkdtemp(prefix="prune-", dir=backup_parent))
            backup.chmod(0o755)
            shutil.copyfile(system / "entries.conf", backup / "entries.conf")
            shutil.copyfile(config_path, backup / "boot.conf")
            for version in expected:
                shutil.copyfile(system / "versions" / version / "manifest.conf", backup / (version + ".manifest.conf"))
            inventory = {"plan": plan, "manifests": manifests,
                         "gcroots": {v: os.readlink(roots / v) for v in expected}}
            if not args.staging_root:
                inventory["profiles"] = {p.name: os.readlink(p) for p in Path("/nix/var/nix/profiles").glob("system*") if p.is_symlink()}
            protocol.atomic_text(backup / "inventory.json", json.dumps(inventory, indent=2) + "\n")
            protocol.sync_dir(backup)
            os.sync()
            before = shutil.disk_usage(boot).used
            # Publish and fsync both surviving aliases BEFORE unlinking any payload.
            protocol.write_versions(system, current, previous, keep)
            for version in remove:
                shutil.rmtree(system / "versions" / version)
            protocol.sync_dir(system / "versions")
            for version in remove:
                (roots / version).unlink()
            protocol.sync_dir(roots)
            for version in keep:
                protocol.version_manifest(system, version)
            if protocol.versions(system)["versions"] != keep or config_path.read_bytes() != config_bytes:
                raise ValueError("Post-cleanup catalog/config verification failed")
            os.sync()
            report = {"status": "ok", "current": current, "previous": previous,
                      "retained": keep, "removed": remove, "backup": str(backup),
                      "boot_used_before_bytes": before,
                      "boot_used_after_bytes": shutil.disk_usage(boot).used,
                      "system_profiles_changed": False, "store_gc_run": False}
    # Only report success after the mount context has restored its original state.
    if not args.staging_root:
        options = subprocess.check_output(["findmnt", "-n", "-o", "OPTIONS", "--mountpoint", str(args.boot_dir)], text=True)
        report["boot_readonly"] = "ro" in options.strip().split(",")
    report_path = backup / "result.json"
    protocol.atomic_text(report_path, json.dumps(report, indent=2) + "\n")
    report_path.chmod(0o644)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--backup-dir", type=Path, required=True)
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--boot-dir", type=Path, default=Path("/boot"))
    target.add_argument("--staging-root", type=Path)
    parser.add_argument("--partuuid")
    parser.add_argument("--partlabel", default="KShinC_BOOT")
    args = parser.parse_args()
    try:
        print(json.dumps(prune(args), indent=2))
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Boot cleanup failed: {error}\n")


if __name__ == "__main__":
    main()
