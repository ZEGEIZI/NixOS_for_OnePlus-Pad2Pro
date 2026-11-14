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
          "adsp_remote_heap": {"consumer": adsp[0], "pool": heap[0], "exclusive_reservation": True},
          "enabled_address_collisions": collisions, "shared_unit_addresses": disabled_groups}
if args.report:
    args.report.write_text(json.dumps(report, indent=2) + "\n")
if collisions:
    raise SystemExit(json.dumps(collisions, indent=2))
print(f"PASS: OPD2413 identity, XN242 match/dither, exclusive ADSP heap, {len(disabled_groups)} shared-address groups with at most one enabled node")
