#!/usr/bin/env python3
"""Exercise the patched firmware-path function with mocked device identities."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

source, harness = map(Path, sys.argv[1:])
text = source.read_text()
start = text.index("static inline void ath12k_core_create_firmware_path(")
end = text.index("\nstatic inline const char *ath12k_bus_str", start)
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / "fw-path.inc").write_text(text[start:end])
    shutil.copyfile(harness, root / "test.c")
    subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
        "-std=c11", "-Wall", "-Wextra", "-Werror", str(root / "test.c"),
        "-o", str(root / "test"),
    ], check=True)
    subprocess.run([str(root / "test")], check=True)
