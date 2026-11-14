#!/usr/bin/env python3
"""Collect device evidence over SSH; this command does not reboot or activate."""
import argparse
import datetime
import json
from pathlib import Path
import shlex
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--host", required=True)
p.add_argument("--expected-release", required=True)
p.add_argument("--expected-system")
p.add_argument("--output", type=Path, required=True)
args = p.parse_args()
if args.output.exists():
    p.error("preserve previous evidence; choose a new output")

commands = {
    "release": "uname -r",
    "kernel_build": "cat /proc/version",
    "boot_id": "cat /proc/sys/kernel/random/boot_id",
    "current_system": "readlink -f /run/current-system",
    "booted_system": "readlink -f /run/booted-system",
    "root_mount": "findmnt -n -o SOURCE,FSTYPE,OPTIONS /",
    "nix_mount": "findmnt -n -o SOURCE,FSTYPE,OPTIONS /nix",
    "failed_services": "systemctl --failed --no-legend --plain",
    "services": "systemctl is-active display-manager NetworkManager bluetooth scx_loader",
    "sound_cards": "cat /proc/asound/cards",
    "drm_connectors": "for f in /sys/class/drm/card*-*/status; do test ! -e \"$f\" || { printf '%s ' \"$f\"; cat \"$f\"; }; done",
    "input_devices": "sed -n '/^N: Name=/p' /proc/bus/input/devices",
    "wifi_state": "nmcli -t -f DEVICE,TYPE,STATE device status",
    "wifi_routes": "ip route show default",
    "wifi_gateway": "task_gateway=$(ip -4 route show default | awk 'NR == 1 { print $3 }'); test -n \"$task_gateway\" && ping -c 5 -W 2 \"$task_gateway\"",
    "bluetooth": "bluetoothctl show | sed -n '/Powered:/p; /Discovering:/p; /Pairable:/p'",
    "battery": "for d in /sys/class/power_supply/*; do printf '%s\\n' \"$d\"; for f in type status capacity online voltage_now current_now; do test ! -r \"$d/$f\" || { printf '%s=' \"$f\"; cat \"$d/$f\"; }; done; done",
    "suspend_modes": "cat /sys/power/mem_sleep",
    "btf": "test -s /sys/kernel/btf/vmlinux && echo available",
    "sched_ext": "cat /sys/kernel/sched_ext/state",
    "kernel_errors": "journalctl -b -k -p err --no-pager -o cat",
}
report = {"timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "expected_release": args.expected_release, "checks": {},
          "manual_acceptance": {key: "unverified" for key in [
              "cold_boot", "ordinary_reboot", "display", "touch", "gpu", "audio",
              "wifi_discovery_and_connectivity", "bluetooth_playback", "charging",
              "suspend_resume", "fallback_boot"]}}
for name, command in commands.items():
    try:
        result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
                                 args.host, "sh -c " + shlex.quote(command)],
                                capture_output=True, text=True, timeout=45)
    except subprocess.TimeoutExpired:
        report["checks"][name] = {"exit_code": 124, "stdout": "", "stderr": "SSH command timed out"}
        break
    report["checks"][name] = {"exit_code": result.returncode,
                              "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
    if result.returncode == 255:
        break
checks = report["checks"]
report["identity_verified"] = (checks["release"]["exit_code"] == 0 and
                                checks["release"]["stdout"] == args.expected_release)
if args.expected_system:
    report["identity_verified"] &= checks.get("booted_system", {}).get("stdout") == args.expected_system
# Do not turn service/sysfs observations into a claim about physical operation.
report["hardware_accepted"] = False
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"identity_verified": report["identity_verified"],
                  "hardware_accepted": False, "report": str(args.output)}, indent=2))
raise SystemExit(0 if report["identity_verified"] else 1)
