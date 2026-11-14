import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
spec = importlib.util.spec_from_file_location("pruner", Path(__file__).resolve().parents[1] / "tools/prune-kshim-boot.py")
pruner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pruner)


class BootPruning(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.boot = self.base / "boot"
        self.boot.mkdir()
        (self.boot / "kshim/systems").mkdir(parents=True)
        self.config = self.boot / "kshim/boot.conf"
        self.config.write_text("format=1\nsystems=nixos\ndefault=android\ntimeout_ms=8000\n")
        image = bytearray(4096)
        struct.pack_into("<QQQ", image, 8, 0x80000, 4096, 0)
        image[56:60] = b"ARM\x64"
        (self.base / "Image").write_bytes(image)
        dtb = bytearray(40)
        struct.pack_into(">II", dtb, 0, 0xd00dfeed, 40)
        (self.base / "board.dtb").write_bytes(dtb)
        (self.base / "initrd").write_bytes(b"test-initrd")
        self.expected = {}
        roots = self.boot / ".nixos-gcroots"
        roots.mkdir()
        for i in range(1, 5):
            version = f"nixos-v{i}"
            toplevel = "/nix/store/" + str(i) * 32 + "-system"
            self.expected[version] = toplevel
            (roots / version).symlink_to(toplevel)
            (self.base / "cmdline").write_text("console=tty0 init=" + toplevel + "/init\n")
            pruner.protocol.publish(SimpleNamespace(
                system="nixos", version=version, title="NixOS", kernel_release="test",
                cmdline_file=self.base / "cmdline", image=self.base / "Image",
                dtb=self.base / "board.dtb", initrd=self.base / "initrd"), self.boot,
                reuse_payloads=True)
        self.system = self.boot / "kshim/systems/nixos"
        self.plan = {"current": "nixos-v4", "previous": "nixos-v2",
                     "expected_previous": "nixos-v3", "expected": self.expected}
        self.args = SimpleNamespace(plan=self.base / "plan.json", staging_root=self.boot,
                                    backup_dir=self.base / "backups")

    def tearDown(self):
        self.temp.cleanup()

    def run_prune(self):
        self.args.plan.write_text(json.dumps(self.plan))
        return pruner.prune(self.args)

    def test_prune_backup_payloads_roots_and_shared_config(self):
        before = self.config.read_bytes()
        result = self.run_prune()
        self.assertEqual(pruner.protocol.versions(self.system)["versions"], ["nixos-v4", "nixos-v2"])
        self.assertEqual({p.name for p in (self.system / "versions").iterdir()}, {"nixos-v4", "nixos-v2"})
        self.assertEqual({p.name for p in (self.boot / ".nixos-gcroots").iterdir()}, {"nixos-v4", "nixos-v2"})
        self.assertEqual(self.config.read_bytes(), before)
        backup = Path(result["backup"])
        self.assertEqual(len(pruner.protocol.version_list(pruner.protocol.read_config(
            backup / "entries.conf", ("format", "current", "previous", "versions"), formats=("2",))["versions"])), 4)
        self.assertEqual(json.loads((backup / "result.json").read_text())["status"], "ok")
        for version in result["retained"]:
            pruner.protocol.version_manifest(self.system, version)
            self.assertEqual((self.system / "versions" / version / "Image").stat().st_nlink, 2)

    def test_retain_additional_fallback(self):
        self.plan["retain"] = ["nixos-v1"]
        result = self.run_prune()
        self.assertEqual(result["removed"], ["nixos-v3"])
        self.assertEqual(pruner.protocol.versions(self.system)["versions"],
                         ["nixos-v4", "nixos-v2", "nixos-v1"])
        self.assertTrue((self.boot / ".nixos-gcroots/nixos-v1").is_symlink())
        pruner.protocol.version_manifest(self.system, "nixos-v1")

    def test_explicit_current_only_plan(self):
        self.plan["previous"] = "none"
        result = self.run_prune()
        self.assertEqual(result["retained"], ["nixos-v4"])
        self.assertEqual(result["removed"], ["nixos-v1", "nixos-v2", "nixos-v3"])
        self.assertEqual(pruner.protocol.versions(self.system),
                         {"format": "2", "current": "nixos-v4", "previous": "none",
                          "versions": ["nixos-v4"]})
        pruner.protocol.version_manifest(self.system, "nixos-v4")
        self.assertEqual((self.system / "versions/nixos-v4/Image").stat().st_nlink, 1)
        self.assertEqual({p.name for p in (self.boot / ".nixos-gcroots").iterdir()}, {"nixos-v4"})

    def test_reject_invalid_retention_without_menu_change(self):
        before = (self.system / "entries.conf").read_bytes()
        for retain in (["nixos-v4"], ["missing"], ["nixos-v1", "nixos-v3"], "nixos-v1"):
            with self.subTest(retain=retain):
                self.plan["retain"] = retain
                with self.assertRaises(ValueError):
                    self.run_prune()
                self.assertEqual((self.system / "entries.conf").read_bytes(), before)

    def test_reject_corrupt_retained_payload_without_menu_change(self):
        before = (self.system / "entries.conf").read_bytes()
        (self.system / "versions/nixos-v2/Image").write_bytes(b"broken")
        with self.assertRaises(ValueError):
            self.run_prune()
        self.assertEqual((self.system / "entries.conf").read_bytes(), before)

    def test_reject_changed_catalog_or_current(self):
        for key, value in (("current", "nixos-v1"), ("expected_previous", "nixos-v1")):
            with self.subTest(key=key):
                old = self.plan[key]
                self.plan[key] = value
                with self.assertRaises(ValueError):
                    self.run_prune()
                self.plan[key] = old
        self.assertEqual(len(pruner.protocol.versions(self.system)["versions"]), 4)

    def test_reject_default_removal_and_symlink_version(self):
        self.config.write_text("format=1\nsystems=nixos\ndefault=nixos/nixos-v1\ntimeout_ms=8000\n")
        with self.assertRaisesRegex(ValueError, "explicit shared default"):
            self.run_prune()
        self.config.write_text("format=1\nsystems=nixos\ndefault=android\ntimeout_ms=8000\n")
        folder = self.system / "versions/nixos-v1"
        folder.rename(self.base / "outside")
        folder.symlink_to(self.base / "outside")
        with self.assertRaises(ValueError):
            self.run_prune()
        self.assertTrue((self.base / "outside/Image").is_file())

    def test_failed_unlink_leaves_only_verified_survivors_selected(self):
        with patch.object(pruner.shutil, "rmtree", side_effect=OSError("injected deletion failure")):
            with self.assertRaises(OSError):
                self.run_prune()
        self.assertEqual(pruner.protocol.versions(self.system)["versions"], ["nixos-v4", "nixos-v2"])
        for version in ("nixos-v4", "nixos-v2"):
            pruner.protocol.version_manifest(self.system, version)
        self.assertEqual(len(list((self.boot / ".nixos-gcroots").iterdir())), 4)


if __name__ == "__main__":
    unittest.main()
