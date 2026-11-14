#!/usr/bin/env python3
"""Write one limited-range, neutral BT.2020/PQ YUV420P10LE test frame.

The raw frame needs explicit color metadata when encoded; it is not a video.
Content nits describe encoded samples, not calibrated panel luminance.
"""
import argparse
from array import array
from pathlib import Path
import sys


def pq(nits):
    power = (nits / 10000) ** (2610 / 16384)
    return ((3424 / 4096 + 2413 / 128 * power) /
            (1 + 2392 / 128 * power)) ** (2523 / 32)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--pattern", choices=("steps", "reference", "highlight"),
                        default="steps")
    args = parser.parse_args()
    width, height = 1000, 200
    levels = [round(64 + 876 * pq(n)) for n in (100, 203, 400, 600, 1000)]
    pixels = array("H")
    for y in range(height):
        for x in range(width):
            if args.pattern == "steps":
                value = levels[x // (width // 5)]
            else:
                value = levels[4] if args.pattern == "highlight" and x < 32 and y < 32 else levels[1]
            pixels.append(value)
    pixels.extend([512] * (width * height // 2))
    if sys.byteorder != "little":
        pixels.byteswap()
    args.output.write_bytes(pixels.tobytes())


if __name__ == "__main__":
    main()
