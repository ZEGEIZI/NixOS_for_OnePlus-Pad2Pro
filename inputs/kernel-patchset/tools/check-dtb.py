#!/usr/bin/env python3
"""Check board identity, display, DSP memory ownership and address collisions."""
import argparse
import json
from pathlib import Path
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("dtb", type=Path)
p.add_argument("--report", type=Path)
p.add_argument("--fdtget", default="fdtget")
args = p.parse_args()


def fdt(*cmd):
    return subprocess.run([args.fdtget, *cmd], capture_output=True, text=True)


nodes = {}


def walk(path, parent_enabled):
    props = fdt("-p", str(args.dtb), path)
    if props.returncode:
        raise SystemExit(props.stderr)
    properties = props.stdout.splitlines()
    status = fdt("-t", "s", str(args.dtb), path, "status") if "status" in properties else None
    enabled = parent_enabled and (status is None or status.stdout.strip() in ("okay", "ok"))
    compatible = fdt("-t", "s", str(args.dtb), path, "compatible") if "compatible" in properties else None
    children = fdt("-l", str(args.dtb), path)
    if children.returncode:
        raise SystemExit(children.stderr)
    names = children.stdout.splitlines()
    nodes[path] = {"enabled": enabled, "properties": properties,
                   "compatible": compatible.stdout.split() if compatible else [], "children": names}
    for name in names:
        walk(path.rstrip("/") + "/" + name, enabled)


walk("/", True)
required = {"oneplus,opd2413", "oneplus,erhai", "qcom,sm8750"}
if not required.issubset(nodes["/"]["compatible"]):
    raise SystemExit("missing board identity")
panels = [path for path, node in nodes.items() if "csot,xn242" in node["compatible"]]
if len(panels) != 1:
    raise SystemExit(f"expected one independently matched XN242 panel: {panels}")
panel = nodes[panels[0]]
if "novatek,nt36536" not in panel["compatible"] or "qcom,dpu-8bpc-dither" not in panel["properties"]:
    raise SystemExit("missing panel fallback identity or board dither policy")

mdss = "/soc@0/display-subsystem@ae00000"
splash = "/reserved-memory/framebuffer@fc800000"
splash_range = ["0", "fc800000", "0", "2b00000"]
mdss_phandle = fdt("-t", "x", str(args.dtb), mdss, "phandle").stdout.split()
splash_phandle = fdt("-t", "x", str(args.dtb), splash, "phandle").stdout.split()
if (len(mdss_phandle) != 1 or len(splash_phandle) != 1
        or fdt("-t", "x", str(args.dtb), mdss, "memory-region").stdout.split() != splash_phandle
        or fdt("-t", "x", str(args.dtb), splash, "reg").stdout.split() != splash_range
        or fdt("-t", "x", str(args.dtb), splash, "iommu-addresses").stdout.split() != mdss_phandle + splash_range
        or "no-map" not in nodes[splash]["properties"]):
    raise SystemExit("MDSS must retain the firmware splash framebuffer's bounded identity mapping")

i2c_backlight = "/soc@0/geniqup@9c0000/i2c@980000"
if fdt("-t", "u", str(args.dtb), i2c_backlight, "clock-frequency").stdout.split() != ["100000"]:
    raise SystemExit("KTZ8868 master bus must use 100 kHz")

# Do not let a future forward port silently restore the readback-sensitive
# VDDIO range or lose the connector sensors required to admit charge pumps.
vddio = [path for path, node in nodes.items()
         if "regulator-name" in node["properties"]
         and fdt("-t", "s", str(args.dtb), path, "regulator-name").stdout.strip() == "vreg_l12b_1p8"]
if len(vddio) != 1 or any(
        fdt("-t", "u", str(args.dtb), vddio[0], prop).stdout.split() != ["1896000"]
        for prop in ("regulator-min-microvolt", "regulator-max-microvolt")):
    raise SystemExit("XN242 VDDIO must retain its validated 1.896 V constraint")
pumps = [path for path, node in nodes.items()
         if node["enabled"] and "southchip,sc8547a" in node["compatible"]]
primary = [path for path in pumps if "southchip,secondary" not in nodes[path]["properties"]]
secondary = [path for path in pumps if "southchip,secondary" in nodes[path]["properties"]]
if len(primary) != 1 or len(secondary) != 1:
    raise SystemExit("charging requires one primary and one secondary SC8547A")
channels = fdt("-t", "x", str(args.dtb), primary[0], "io-channels").stdout.split()
if len(channels) != 4 or channels[0] != channels[2] or channels[1::2] != ["74c", "747"]:
    raise SystemExit("SC8547A must use the stock battery/USB connector NTC channels")
if fdt("-t", "s", str(args.dtb), primary[0], "io-channel-names").stdout.split() != [
        "battery-connector", "usb-connector"]:
    raise SystemExit("incorrect SC8547A connector channel names")
adc = [path for path, node in nodes.items()
       if node["enabled"] and "phandle" in node["properties"]
       and fdt("-t", "x", str(args.dtb), path, "phandle").stdout.split() == [channels[0]]]
if len(adc) != 1:
    raise SystemExit("charging connector ADC reference is missing or disabled")
for channel in ("747", "74c"):
    path = adc[0] + "/channel@" + channel
    if path not in nodes or not {"qcom,adc5-gen4", "qcom,ratiometric"}.issubset(nodes[path]["properties"]):
        raise SystemExit("charging connector NTC must use Gen4 ratiometric conversion")

# FastRPC assigns the whole ADSP remote heap to DSP VMIDs at probe. A CMA
# reusable pool would let unrelated Linux allocations access protected pages.
adsp = [path for path, node in nodes.items()
        if node["enabled"] and "qcom,fastrpc" in node["compatible"]
        and "label" in node["properties"]
        and fdt("-t", "s", str(args.dtb), path, "label").stdout.strip() == "adsp"]
if len(adsp) != 1:
    raise SystemExit(f"expected one ADSP FastRPC channel: {adsp}")
reference = fdt("-t", "x", str(args.dtb), adsp[0], "memory-region")
if reference.returncode or len(reference.stdout.split()) != 1:
    raise SystemExit("ADSP must reference one dedicated remote heap")
heap = [path for path, node in nodes.items()
        if node["enabled"] and "shared-dma-pool" in node["compatible"]
        and "phandle" in node["properties"]
        and fdt("-t", "x", str(args.dtb), path, "phandle").stdout.split() == reference.stdout.split()]
if len(heap) != 1:
    raise SystemExit(f"ADSP remote heap reference is not a unique shared pool: {heap}")
if "reusable" in nodes[heap[0]]["properties"] or "no-map" not in nodes[heap[0]]["properties"]:
    raise SystemExit("ADSP remote heap assigned to DSP must be no-map and must not be reusable CMA")

collisions, disabled_groups = [], []
for parent, node in nodes.items():
    by_address = {}
    for name in node["children"]:
        path = parent.rstrip("/") + "/" + name
        if "@" in name and "reg" in nodes[path]["properties"]:
            by_address.setdefault(name.split("@", 1)[1].lower(), []).append(path)
    for paths in by_address.values():
        if len(paths) < 2:
            continue
        active = [path for path in paths if nodes[path]["enabled"]]
        (collisions if len(active) > 1 else disabled_groups).append({"nodes": paths, "active": active})
report = {"board_identity": nodes["/"]["compatible"], "panel": panels[0],
          "vddio_uV": 1896000,
          "charge_pumps": {"primary": primary[0], "secondary": secondary[0], "connector_adc": adc[0]},
          "adsp_remote_heap": {"consumer": adsp[0], "pool": heap[0], "exclusive_reservation": True},
          "enabled_address_collisions": collisions, "shared_unit_addresses": disabled_groups}
if args.report:
    args.report.write_text(json.dumps(report, indent=2) + "\n")
if collisions:
    raise SystemExit(json.dumps(collisions, indent=2))
print(f"PASS: OPD2413 identity, XN242 match/dither, exclusive ADSP heap, {len(disabled_groups)} shared-address groups with at most one enabled node")
