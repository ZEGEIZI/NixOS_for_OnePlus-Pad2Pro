#!/usr/bin/env python3
"""Pack a Nix-built RAM probe with separately verified, independent kShimC tools."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--payload", type=Path, required=True)
parser.add_argument("--kshim-project", type=Path, required=True)
parser.add_argument("--boot-tools", type=Path, required=True)
parser.add_argument("--stock-boot", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--profile", choices=["initrd", "system"], default="initrd")
args = parser.parse_args()
if args.output.exists():
    parser.error("Use a new output directory")
args.output.mkdir(parents=True)
dtb = args.output / "probe.dtb"
shutil.copyfile(args.payload / "board.dtb", dtb)
cmdline = (args.payload / "cmdline").read_text().strip()
if args.profile == "initrd" and "rd.systemd.unit=pad2pro-probe.target" not in cmdline.split():
    parser.error("Expected the RAM-only diagnostic payload")
if args.profile == "system" and ("pad2pro.ram=1" not in cmdline.split() or not (args.payload / "rootfs.squashfs").is_file()):
    parser.error("Expected the full RAM system payload")
subprocess.run(["fdtput", "-t", "s", str(dtb), "/chosen", "bootargs", cmdline], check=True)
subprocess.run([
    sys.executable, str(args.kshim_project / "tools/build_external_boot.py"),
    "--boot-tools", str(args.boot_tools.resolve()),
    "--stock-boot", str(args.stock_boot.resolve()),
    "--debug-image", str((args.payload / "Image").resolve()),
    "--debug-dtb", str(dtb.resolve()),
    "--debug-initrd", str((args.payload / "initramfs.img").resolve()),
    "--out", str((args.output / "packed").resolve()),
], check=True)
report = {
    "stage": "NixOS systemd initrd only; no device filesystems mounted" if args.profile == "initrd" else "Full RAM NixOS; HTTP store verified by SHA-256",
    "hardware_verified": False,
    "device_written": False,
    "cmdline": cmdline,
    "inputs": {name: hashlib.sha256((args.payload / name).read_bytes()).hexdigest()
               for name in ("Image", "board.dtb", "initramfs.img", "cmdline")},
}
(args.output / "probe.json").write_text(json.dumps(report, indent=2) + "\n")
print(args.output / "packed/boot.img")
