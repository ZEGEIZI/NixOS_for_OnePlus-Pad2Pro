from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CHECKER = Path(__file__).resolve().parents[1] / "tools/check-kernel-config.py"


class KernelConfig(unittest.TestCase):
    def check(self, actual, *fragments):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / ".config"
            config.write_text(actual)
            files = []
            for index, fragment in enumerate(fragments):
                path = root / str(index)
                path.write_text(fragment)
                files.append(str(path))
            return subprocess.run([sys.executable, str(CHECKER), str(config), *files],
                                  capture_output=True, text=True)

    def test_hidden_disabled_symbols_are_off(self):
        self.assertEqual(self.check("", "# CONFIG_RUST is not set\n").returncode, 0)
        self.assertNotEqual(self.check("CONFIG_RUST=y\n", "# CONFIG_RUST is not set\n").returncode, 0)

    def test_required_boot_drivers_and_final_overrides(self):
        self.assertNotEqual(self.check("CONFIG_BTRFS_FS=m\n", "CONFIG_BTRFS_FS=y\n").returncode, 0)
        self.assertEqual(self.check("CONFIG_BTRFS_FS=y\n", "CONFIG_BTRFS_FS=m\n",
                                    "CONFIG_BTRFS_FS=y\n").returncode, 0)
