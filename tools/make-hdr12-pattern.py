#!/usr/bin/env python3
"""Write a 16-bit RGB PNG or PPM for BT.2020/PQ HDR and precision tests.

Top: 100/203/400/600/1000-nit neutral patches. Below: dark, middle and bright
ramps; each row repeats the same ramp at 8-, 10- and 12-bit PQ precision from
left to right. Values describe content luminance, not measured panel output.
PNG includes a cICP chunk identifying full-range BT.2020/PQ RGB. PPM has no
color metadata. Do not convert the reference to an 8-bit PNG or YUV420.
"""
import argparse
from array import array
from pathlib import Path
import sys
import struct
import zlib


def pq(nits):
    power = (nits / 10000) ** (2610 / 16384)
    return ((3424 / 4096 + 2413 / 128 * power) /
            (1 + 2392 / 128 * power)) ** (2523 / 32)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    width, height = 3392, 2400
    png = args.output.suffix.lower() == ".png"
    if args.output.suffix.lower() not in (".png", ".ppm"):
        parser.error("output must end in .png or .ppm")
    with args.output.open("xb") as output:
        def chunk(kind, data):
            output.write(struct.pack(">I", len(data)) + kind + data +
                         struct.pack(">I", zlib.crc32(kind + data)))

        if png:
            output.write(b"\x89PNG\r\n\x1a\n")
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 16, 2, 0, 0, 0))
            # H.273: BT.2020 primaries, ST2084 transfer, identity matrix,
            # full range. RGB image samples are already PQ encoded.
            chunk(b"cICP", bytes((9, 16, 0, 1)))
            compressor = zlib.compressobj()
        else:
            output.write(f"P6\n{width} {height}\n65535\n".encode())
        for y in range(height):
            row = array("H")
            for x in range(width):
                if y < 480:
                    encoded = pq((100, 203, 400, 600, 1000)[x * 5 // width])
                else:
                    index = min(2, (y - 480) // 640)
                    low, high = ((0.1, 4), (60, 100), (350, 550))[index]
                    column = min(2, x * 3 // width)
                    start, end = column * width // 3, (column + 1) * width // 3
                    fraction = (x - start) / (end - start - 1)
                    encoded = pq(low) + (pq(high) - pq(low)) * fraction
                    maximum = (1 << (8, 10, 12)[column]) - 1
                    encoded = round(encoded * maximum) / maximum
                value = round(65535 * encoded)
                row.extend((value, value, value))
            if sys.byteorder == "little":
                row.byteswap()
            if png:
                compressed = compressor.compress(b"\x00" + row.tobytes())
                if compressed:
                    chunk(b"IDAT", compressed)
            else:
                output.write(row.tobytes())
        if png:
            chunk(b"IDAT", compressor.flush())
            chunk(b"IEND", b"")


if __name__ == "__main__":
    main()
