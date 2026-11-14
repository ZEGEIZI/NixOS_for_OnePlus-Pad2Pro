#!/usr/bin/env python3
"""Copy a verified generated patchset release into the portable NixOS source."""
import argparse
import importlib.util
from pathlib import Path
import shutil
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("source", type=Path)
args = p.parse_args()
source = args.source.resolve()
spec = importlib.util.spec_from_file_location("erhai_release", source / "tools/verify.py")
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)
m = verify.verify_release(source, "7.3")
destination = Path(__file__).resolve().parents[1] / "inputs/kernel-patchset"
if (destination / "tools/verify.py").exists():
    verify.verify_release(destination, "7.3")
with tempfile.TemporaryDirectory(prefix="erhai-release-") as tmp:
    snapshot = Path(tmp) / "release"
    snapshot.mkdir()
    for name in ["patchsets", "configs", "tools", "provenance", "tests"]:
        if (source / name).exists():
            shutil.copytree(source / name, snapshot / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ["README.md", "PLAN.md"]:
        if (source / name).exists():
            shutil.copy2(source / name, snapshot / name)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(snapshot, destination)
print(f"Vendored {m['release']} at {m['head']}")
