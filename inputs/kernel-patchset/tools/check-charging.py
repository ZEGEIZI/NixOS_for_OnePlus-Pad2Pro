#!/usr/bin/env python3
"""Compile and run the board's pure charging policy against boundary scenarios."""
import argparse
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("source", type=Path)
p.add_argument("--cc", default="cc")
args = p.parse_args()
root = Path(__file__).resolve().parents[1]

with tempfile.TemporaryDirectory(prefix="erhai-charge-test-") as tmp:
    tmp = Path(tmp)
    include = tmp / "linux"
    include.mkdir()
    (include / "kernel.h").write_text("""
#ifndef TEST_KERNEL_H
#define TEST_KERNEL_H
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
typedef uint8_t u8;
typedef uint16_t u16;
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define min(a,b) ((a) < (b) ? (a) : (b))
#endif
""")
    (include / "jiffies.h").write_text("""
#define msecs_to_jiffies(ms) ((unsigned long)(ms))
#define time_before(a,b) ((long)((a) - (b)) < 0)
""")
    binary = tmp / "charging-policy"
    subprocess.run([args.cc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                    "-Wno-sign-compare", "-I", str(tmp), "-I",
                    str(args.source / "drivers/power/supply"),
                    str(root / "tests/charging-policy.c"), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
