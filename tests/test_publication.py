import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
spec = importlib.util.spec_from_file_location("installer", Path(__file__).resolve().parents[1] / "tools/kshim-install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class Publication(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.boot = self.root / "boot"
        self.boot.mkdir()
        self.payloads = self.root / "payloads"
        self.payloads.mkdir()
        header = bytearray(64)
        struct.pack_into("<QQQ", header, 8, 0x80000, 4096, 0)
        header[56:60] = b"ARM\x64"
        (self.payloads / "Image").write_bytes(header + bytes(4096 - 64))
        (self.payloads / "initrd").write_bytes(b"test-initrd")
        dts = self.payloads / "board.dts"
        dts.write_text('/dts-v1/; / { compatible = "oneplus,opd2413", "qcom,sm8750"; };')
        subprocess.run(["dtc", "-I", "dts", "-O", "dtb", "-o", str(self.payloads / "board.dtb"), str(dts)], check=True)

    def tearDown(self):
        self.temporary.cleanup()

    def system(self, name):
        path = self.root / name
        path.mkdir()
        (path / "init").write_text("test-init")
        (path / "boot.json").write_text(json.dumps({
            "org.nixos.bootspec.v1": {
                "system": "aarch64-linux", "toplevel": str(path), "init": str(path / "init"),
                "kernel": str(self.payloads / "Image"), "initrd": str(self.payloads / "initrd"),
                "kernelParams": ["console=tty0"],
            },
            "org.oneplus.pad2pro.v1": {
                "dtb": str(self.payloads / "board.dtb"), "kernelRelease": "7.2.15-test",
            },
        }))
        return path

    def install(self, system):
        return installer.install(SimpleNamespace(system=system, staging_root=self.boot))

    def entries(self):
        return installer.protocol.versions(self.boot / "kshim/systems/nixos")

    def test_publish_update_idempotence_rollback_and_roots(self):
        first, second = self.system("system-a"), self.system("system-b")
        a = self.install(first)["boot_id"]
        b = self.install(second)["boot_id"]
        self.assertEqual(self.entries()["previous"], a)
        self.install(second)
        self.assertEqual(self.entries()["previous"], a)
        self.install(first)
        self.assertEqual(self.entries()["current"], a)
        self.assertEqual(self.entries()["previous"], b)
        for system, version in ((first, a), (second, b)):
            root = self.boot / ".nixos-gcroots" / version
            self.assertEqual(root.resolve(), system)
            folder = self.boot / "kshim/systems/nixos/versions" / version
            manifest = installer.protocol.version_manifest(folder.parent.parent, version)
            self.assertIn("init=" + str(system / "init"), manifest["cmdline"])
            self.assertFalse((folder / "Image").is_symlink())

    def test_preserve_other_linux_and_default(self):
        kshim = self.boot / "kshim"
        kshim.mkdir()
        (kshim / "boot.conf").write_text("format=1\nsystems=armada\ndefault=armada/current\ntimeout_ms=3000\n")
        self.install(self.system("system-a"))
        self.assertEqual((kshim / "boot.conf").read_text(),
                         "format=1\nsystems=armada,nixos\ndefault=armada/current\ntimeout_ms=3000\n")

    def test_failed_payload_keeps_previous_selection(self):
        a = self.install(self.system("system-a"))["boot_id"]
        (self.payloads / "Image").write_bytes(b"broken")
        with self.assertRaises(ValueError):
            self.install(self.system("system-b"))
        self.assertEqual(self.entries()["current"], a)

    def test_shared_default_requires_system_and_selector(self):
        self.install(self.system("system-a"))
        path = self.boot / "kshim/boot.conf"
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            installer.protocol.configure(SimpleNamespace(
                systems="nixos", default="nixos", timeout_ms=8000,
            ), self.boot)
        self.assertEqual(path.read_bytes(), before)
        installer.protocol.configure(SimpleNamespace(
            systems="nixos", default="nixos/current", timeout_ms=8000,
        ), self.boot)
        self.assertIn("default=nixos/current\n", path.read_text())

    def test_reject_foreign_architecture_and_injected_init(self):
        system = self.system("system-a")
        path = system / "boot.json"
        doc = json.loads(path.read_text())
        doc["org.nixos.bootspec.v1"]["system"] = "x86_64-linux"
        path.write_text(json.dumps(doc))
        with self.assertRaises(ValueError):
            self.install(system)
        doc["org.nixos.bootspec.v1"]["system"] = "aarch64-linux"
        doc["org.nixos.bootspec.v1"]["kernelParams"].append("init=/bin/sh")
        path.write_text(json.dumps(doc))
        with self.assertRaises(ValueError):
            self.install(system)
        self.assertEqual(list(self.boot.iterdir()), [])

    def test_publish_and_restore_more_than_eight_generations(self):
        systems = [self.system(f"system-{i}") for i in range(12)]
        ids = [self.install(system)["boot_id"] for system in systems]
        self.assertEqual(self.entries()["versions"], ids[::-1])

        target = self.boot / "kshim/systems/nixos"
        installer.protocol.write_versions(target, ids[-1], ids[-2], ids[1:][::-1])
        self.install(systems[0])
        self.assertEqual(self.entries()["versions"], [ids[0], *ids[1:][::-1]])
        self.assertEqual(self.entries()["current"], ids[0])
        self.assertEqual(self.entries()["previous"], ids[-1])

    def folder(self, version):
        return self.boot / "kshim/systems/nixos/versions" / version

    def test_identical_payloads_share_storage_across_generations(self):
        a = self.install(self.system("system-a"))["boot_id"]
        result = self.install(self.system("system-b"))
        b = result["boot_id"]
        self.assertEqual(result["reused_payloads"], ["dtb", "image", "initrd"])
        for name in ("Image", "board.dtb", "initramfs.img"):
            self.assertTrue((self.folder(a) / name).samefile(self.folder(b) / name))
            self.assertFalse((self.folder(b) / name).is_symlink())
        self.assertNotEqual((self.folder(a) / "manifest.conf").stat().st_ino,
                            (self.folder(b) / "manifest.conf").stat().st_ino)

    def test_changed_initrd_is_copied_without_changing_old_version(self):
        a = self.install(self.system("system-a"))["boot_id"]
        (self.payloads / "initrd").write_bytes(b"new-initrd")
        result = self.install(self.system("system-b"))
        b = result["boot_id"]
        self.assertEqual(result["reused_payloads"], ["dtb", "image"])
        self.assertEqual((self.folder(a) / "initramfs.img").read_bytes(), b"test-initrd")
        self.assertEqual((self.folder(b) / "initramfs.img").read_bytes(), b"new-initrd")
        self.assertFalse((self.folder(a) / "initramfs.img").samefile(self.folder(b) / "initramfs.img"))

    def test_changed_kernel_is_copied_even_at_the_same_source_path(self):
        a = self.install(self.system("system-a"))["boot_id"]
        old = (self.folder(a) / "Image").read_bytes()
        changed = bytearray(old)
        changed[-1] = 1
        (self.payloads / "Image").write_bytes(changed)
        result = self.install(self.system("system-b"))
        self.assertEqual(result["reused_payloads"], ["dtb", "initrd"])
        self.assertEqual((self.folder(a) / "Image").read_bytes(), old)
        self.assertEqual((self.folder(result["boot_id"]) / "Image").read_bytes(), changed)

    def test_sharing_does_not_require_free_space_for_another_kernel(self):
        self.install(self.system("system-a"))
        space = shutil.disk_usage(self.boot)._replace(free=8 * 1024 * 1024 + 1)
        with patch.object(installer.protocol.shutil, "disk_usage", return_value=space):
            result = self.install(self.system("system-b"))
        self.assertEqual(result["reused_payloads"], ["dtb", "image", "initrd"])

    def test_corrupt_or_symlinked_candidate_is_not_reused(self):
        a = self.install(self.system("system-a"))["boot_id"]
        image = self.folder(a) / "Image"
        image.write_bytes(b"broken")
        b = self.install(self.system("system-b"))["boot_id"]
        self.assertEqual((self.folder(b) / "Image").read_bytes(), (self.payloads / "Image").read_bytes())
        image.unlink()
        image.symlink_to(self.payloads / "Image")
        # Hide the valid second entry so only the symlinked candidate is considered.
        installer.protocol.write_versions(self.folder(a).parent.parent, a, "none", [a])
        result = self.install(self.system("system-c"))
        self.assertEqual(result["reused_payloads"], [])
        self.assertFalse((self.folder(result["boot_id"]) / "Image").samefile(self.payloads / "Image"))

    def test_link_failure_keeps_old_menu_and_cleans_partial_links(self):
        a = self.install(self.system("system-a"))["boot_id"]
        before = self.entries()
        real_link = installer.protocol.os.link
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected hardlink failure")
            return real_link(*args, **kwargs)

        with patch.object(installer.protocol.os, "link", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "hardlink failure"):
                self.install(self.system("system-b"))
        self.assertEqual(self.entries(), before)
        self.assertEqual({p.name for p in self.folder(a).parent.iterdir()}, {a})
        self.assertEqual((self.folder(a) / "Image").stat().st_nlink, 1)

    def test_removing_an_old_version_keeps_shared_payloads_valid(self):
        a = self.install(self.system("system-a"))["boot_id"]
        b = self.install(self.system("system-b"))["boot_id"]
        target = self.folder(a).parent.parent
        installer.protocol.write_versions(target, b, "none", [b])
        shutil.rmtree(self.folder(a))
        installer.protocol.version_manifest(target, b)
        self.assertEqual((self.folder(b) / "Image").stat().st_nlink, 1)


if __name__ == "__main__":
    unittest.main()
