#!/usr/bin/env python3
"""Fault-inject the actual driver function using host-only mock hardware."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

source, harness = map(Path, sys.argv[1:])
text = source.read_text()
start = text.index("static void cps8601_fw_update_check(")
end = text.index("\n}", start) + len("\n}")
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "fw-check.inc").write_text(text[start:end])
    shutil.copyfile(harness, root / "test.c")
    subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
        "-std=c11", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
        str(root / "test.c"), "-o", str(root / "test"),
    ], check=True)
    subprocess.run([str(root / "test")], check=True)
