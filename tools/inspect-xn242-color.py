#!/usr/bin/env python3
"""Summarize XN242 factory calibration without publishing its proprietary LUTs."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import struct
import xml.etree.ElementTree as ET


PANEL = "XN242_p_d_dsc_video_mode_panel"
MODE = "24924_d65_hdr"
SAMPLE = struct.Struct("<3I3f")
PRIMARIES = {
    "red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255),
    "white": (255, 255, 255),
}


def decode_blob(hex_string):
    data = bytearray.fromhex(hex_string)
    # These blobs swap adjacent bytes from the end, leaving the first byte
    # untouched for odd lengths. This is only an encoding, not encryption.
    for i in range(len(data) % 2, len(data) - 1, 2):
        data[i], data[i + 1] = data[i + 1], data[i]
    return json.loads(data)


def read_samples(data):
    # Version 1.0, 21 measured RGB/XYZ pairs, then two opaque trailer bytes.
    if len(data) != 4 + 21 * SAMPLE.size + 2 or data[:4] != struct.pack("<f", 1.0):
        raise ValueError("Unexpected XN242 ODF version or length")
    samples = {}
    for r, g, b, x, y, z in SAMPLE.iter_unpack(data[4:-2]):
        rgb = r, g, b
        if rgb in samples or max(rgb) > 255 or not all(math.isfinite(v) and v >= 0 for v in (x, y, z)):
            raise ValueError("Invalid or duplicate ODF sample")
        samples[rgb] = x, y, z
    expected = set(PRIMARIES.values()) | {(v, v, v) for v in range(0, 256, 32)}
    if not expected.issubset(samples):
        raise ValueError("Missing XN242 ODF primaries or gray ramp")
    return samples


def describe(qdcm, odf):
    mode = json.loads(qdcm)[PANEL][MODE]
    if mode["DynamicRange"] != "HDR":
        raise ValueError("Factory mode does not identify itself as HDR")
    hdr = ET.fromstring(decode_blob(mode["PostBlendHdrBlob"])["blob"])
    dither = decode_blob(mode["PostBlendDither"])
    samples = read_samples(odf)
    black, white = samples[(0, 0, 0)][1], samples[(255, 255, 255)][1]
    gray = [(v, samples[(v, v, v)][1]) for v in range(0, 256, 32)] + [(255, white)]
    if any(a[1] >= b[1] for a, b in zip(gray, gray[1:])):
        raise ValueError("Factory gray ramp is not increasing")
    chromaticities = {}
    for name, rgb in PRIMARIES.items():
        xyz = samples[rgb]
        if sum(xyz) <= 0:
            raise ValueError("Invalid zero-sum XYZ sample")
        chromaticities[name] = [round(v / sum(xyz), 6) for v in xyz[:2]]
    hdr_min = float(hdr.findtext("panel_min_luminance"))
    hdr_max = float(hdr.findtext("panel_max_luminance"))
    gamma = float(hdr.findtext("output_gamma_space/val"))
    if not (0 <= hdr_min < hdr_max <= 2000 and 1 < gamma < 4):
        raise ValueError("Unexpected HDR luminance or gamma")
    return {
        "panel": PANEL, "factory_hdr_mode": MODE,
        "qdcm_sha256": hashlib.sha256(qdcm).hexdigest(),
        "odf_sha256": hashlib.sha256(odf).hexdigest(),
        "factory_hdr": {
            "panel_color_mode": hdr.findtext("panel_color_mode"),
            "output_gamma": gamma, "min_nits": hdr_min, "peak_nits": hdr_max,
            "dither_mode": dither["ditherMode"], "temporal_dither": bool(dither["temporalEnable"]),
        },
        "factory_max_level_measurements": {
            "chromaticities_xy": chromaticities,
            "black_nits": round(black, 6), "white_nits": round(white, 6),
            "estimated_gray_gamma": round(statistics.median(
                math.log((lum - black) / (white - black)) / math.log(v / 255)
                for v, lum in gray[1:-1]), 4),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("qdcm_json", type=Path)
    parser.add_argument("max_level_odf", type=Path)
    args = parser.parse_args()
    print(json.dumps(describe(args.qdcm_json.read_bytes(), args.max_level_odf.read_bytes()), indent=2))


if __name__ == "__main__":
    main()
