import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import wifi_firmware as wifi
import firmware_archive as base

spec = importlib.util.spec_from_file_location("stage_firmware", TOOLS / "stage-firmware.py")
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


class WifiFirmware(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.manifest = self.root / "manifest.json"
        self.files = []
        for name in ("amss.bin", "aux_ucode.bin", "board.bin", "m3.bin", "qdss.cfg", "regdb.bin"):
            data = name.encode()
            path = self.source / wifi.PREFIX / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            self.files.append({"install": wifi.PREFIX + name, "size": len(data),
                               "sha256": hashlib.sha256(data).hexdigest()})
        self.manifest.write_text(json.dumps({"schema": 1, "files": self.files}))

    def pack(self, name="firmware.tar"):
        path = self.root / name
        wifi.pack(self.source, path, self.manifest)
        return path

    def test_repeatable_import_and_hash_validation(self):
        first, second = self.pack(), self.pack("second.tar")
        self.assertEqual(first.read_bytes(), second.read_bytes())
        (self.source / wifi.PREFIX / "amss.bin").write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "Firmware mismatch"):
            self.pack("invalid.tar")
        self.assertFalse((self.root / "invalid.tar").exists())

    def test_duplicate_extra_and_symlink_members_rejected(self):
        valid = self.pack()
        for kind in ("duplicate", "traversal", "symlink", "corrupt"):
            with self.subTest(kind=kind):
                target = self.root / (kind + ".tar")
                with tarfile.open(valid) as original, tarfile.open(target, "w") as bundle:
                    for index, member in enumerate(original.getmembers()):
                        data = original.extractfile(member).read()
                        if kind == "symlink" and index == 0:
                            member.type = tarfile.SYMTYPE
                            member.linkname = "/etc/shadow"
                            bundle.addfile(member)
                        else:
                            if kind == "corrupt" and index == 0:
                                data = b"x" * len(data)
                            bundle.addfile(member, io.BytesIO(data))
                    if kind in ("duplicate", "traversal"):
                        member = tarfile.TarInfo(self.files[0]["install"] if kind == "duplicate" else "../escape")
                        bundle.addfile(member, io.BytesIO(b""))
                with self.assertRaises(ValueError):
                    wifi.read_archive(target, self.manifest)

    def test_staging_replaces_entire_wifi_set_and_preserves_other_firmware(self):
        upstream = self.root / "upstream"
        (upstream / "firmware").mkdir(parents=True)
        items = []
        for name in ("ath12k/WCN7860/hw2.0/amss.bin", "ath12k/WCN7860/hw2.0/erhai/board-2.bin", "qcom/adsp.mdt"):
            path = upstream / "firmware" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"old")
            if not name.startswith("ath12k/WCN7860/hw2.0/"):
                items.append({"install": name, "size": 3, "sha256": hashlib.sha256(b"old").hexdigest()})
        manifest = upstream / "manifest.json"
        manifest.write_text(json.dumps({"schema": 1, "files": items}))
        archive = upstream / "base.tar"
        base.pack(upstream / "firmware", archive, manifest)
        output = self.root / "out"
        stage.stage(archive, manifest, output, self.pack(), self.manifest)
        actual = {str(path.relative_to(output / "lib/firmware"))
                  for path in (output / "lib/firmware").rglob("*") if path.is_file()}
        expected = {item["install"] for item in self.files} | {"qcom/adsp.mdt"}
        self.assertEqual(actual, expected)
        effective = json.loads((output / "share/doc/erhai-firmware/firmware-manifest.json").read_text())
        self.assertEqual({item["install"] for item in effective["files"]}, expected)
        self.assertEqual((output / "lib/firmware/qcom/adsp.mdt").read_bytes(), b"old")
