"""Load the pinned kShimC dependency from the portable project inputs."""
import importlib.util
from pathlib import Path
import sys

source = Path(__file__).resolve().parents[1] / "inputs/kshim-protocol/boot_files.py"
spec = importlib.util.spec_from_file_location("kshim_boot_protocol", source)
protocol = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = protocol
spec.loader.exec_module(protocol)
