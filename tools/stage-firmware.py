#!/usr/bin/env python3
"""Stage verified erhai firmware with the complete OPD2413 OEM Wi-Fi set."""
import argparse
import json
from pathlib import Path
import shutil

from wifi_firmware import install, read_archive
from firmware_archive import read_archive as read_base_archive


def stage(base_archive, base_manifest, output, wifi_archive, wifi_manifest):
    # Never mix firmware versions: the OEM driver namespace uses this complete
    # set, and the upstream generic/erhai WCN7860 files are not installed.
    payload = read_archive(wifi_archive, wifi_manifest)
    base_payload = read_base_archive(base_archive, base_manifest)
    if any(name.startswith("ath12k/WCN7860/hw2.0/") for name in base_payload):
        raise ValueError("Base inventory must exclude the superseded WCN7860 set")
    install(base_payload | payload, output)
    installed = json.loads(base_manifest.read_text())["files"].copy()
    installed.extend(json.loads(wifi_manifest.read_text())["files"])
    docs = output / "share/doc/erhai-firmware"
    docs.mkdir(parents=True)
    # This is the effective inventory, not the superseded upstream Wi-Fi list.
    (docs / "firmware-manifest.json").write_text(json.dumps({"files": installed}, indent=2) + "\n")
    shutil.copyfile(base_manifest, docs / "base-firmware-manifest.json")
    shutil.copyfile(wifi_manifest, docs / "opd2413-wifi-firmware.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_archive", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--wifi-archive", required=True, type=Path)
    parser.add_argument("--wifi-manifest", required=True, type=Path)
    parser.add_argument("--base-manifest", required=True, type=Path)
    args = parser.parse_args()
    stage(args.base_archive, args.base_manifest, args.output, args.wifi_archive, args.wifi_manifest)
