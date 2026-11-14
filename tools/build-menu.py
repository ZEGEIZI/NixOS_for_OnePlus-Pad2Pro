#!/usr/bin/env python3
"""Build the independent kShimC menu for KShinC_BOOT. No device commands."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

PROTOCOL = Path(__file__).resolve().parents[1] / "inputs/kshim-protocol/source.json"
REVISION = json.loads(PROTOCOL.read_text())["revision"]

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--kshim-project", type=Path, required=True)
parser.add_argument("--stock-boot", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--jobs", type=int, default=8)
args = parser.parse_args()
if args.output.exists():
    parser.error("Use a new output directory")
args.output.mkdir(parents=True)
snapshot = args.output / "source"
snapshot.mkdir()
archive = subprocess.check_output([
    "git", "-C", str(args.kshim_project), "archive", "--format=tar", REVISION
])
with tarfile.open(fileobj=io.BytesIO(archive)) as source:
    source.extractall(snapshot, filter="data")
config = snapshot / "boot/kshim-ext4.config"
values = {"CONFIG_KSHIM_BOOT_PARTUUID": '""', "CONFIG_KSHIM_BOOT_PARTLABEL": '"KShinC_BOOT"'}
lines = config.read_text().splitlines()
for key in values:
    if sum(line.startswith(key + "=") for line in lines) != 1:
        parser.error("Unexpected upstream partition configuration")
config.write_text("\n".join(key + "=" + values[key] if (key := line.split("=", 1)[0]) in values else line
                            for line in lines) + "\n")
tools = args.output / "boot-tools"
subprocess.run([
    sys.executable, str(snapshot / "tools/build_boot_tools.py"),
    "--mode", "ext4", "--jobs", str(args.jobs), "--out", str(tools),
], check=True)
subprocess.run([
    sys.executable, str(snapshot / "tools/build_external_boot.py"),
    "--boot-tools", str(tools), "--stock-boot", str(args.stock_boot),
    "--out", str(args.output / "menu"),
], check=True)
report = {"kshim_revision": REVISION, "boot_partlabel": "KShinC_BOOT", "boot_partuuid": None,
          "protocol_source_sha256": hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
          "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
          "device_written": False, "hardware_verified": False}
(args.output / "source.json").write_text(json.dumps(report, indent=2) + "\n")
