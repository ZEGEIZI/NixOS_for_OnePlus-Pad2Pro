import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("bluetooth_firmware", Path(__file__).resolve().parents[1] / "tools/bluetooth_firmware.py")
fw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fw)


class BluetoothFirmware(unittest.TestCase):
    def prepare(self, root):
        source = root / "source"
        files = []
        for name in sorted(fw.NAMES):
            relative = fw.PREFIX + name
            data = name.encode()
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            files.append(dict(install=relative, size=len(data), sha256=hashlib.sha256(data).hexdigest()))
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps(dict(schema=1, files=files)))
        return source, manifest

    def test_reproducible_pack_and_exact_stage(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source, manifest = self.prepare(root)
            a, b = root / "a.tar", root / "b.tar"
            self.assertEqual(fw.pack(source, a, manifest), fw.pack(source, b, manifest))
            self.assertEqual(a.read_bytes(), b.read_bytes())
            fw.stage(a, root / "output", manifest)
            for item in fw.inventory(manifest):
                self.assertEqual((source / item["install"]).read_bytes(), (root / "output/lib/firmware" / item["install"]).read_bytes())
            (source / fw.PREFIX / "brhbtfw20.mbn").write_bytes(b"wrong")
            with self.assertRaises(ValueError):
                fw.pack(source, root / "bad.tar", manifest)

    def test_invalid_archive_never_stages_partial_firmware(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source, manifest = self.prepare(root)
            valid = root / "valid.tar"
            fw.pack(source, valid, manifest)
            with tarfile.open(valid) as bundle:
                original = [(m.name, bundle.extractfile(m).read()) for m in bundle.getmembers()]
            for kind in ("duplicate", "extra", "symlink", "corrupt", "missing"):
                with self.subTest(kind=kind):
                    target = root / (kind + ".tar")
                    with tarfile.open(target, "w") as bundle:
                        entries = original[:-1] if kind == "missing" else original
                        for i, (name, data) in enumerate(entries):
                            m = tarfile.TarInfo(name)
                            m.size = len(data)
                            if i == 0 and kind == "symlink":
                                m.type, m.linkname, m.size = tarfile.SYMTYPE, "/tmp/foreign", 0
                            if i == 0 and kind == "corrupt":
                                data = b"x" * len(data)
                            bundle.addfile(m, io.BytesIO(data))
                        if kind in ("duplicate", "extra"):
                            m = tarfile.TarInfo(original[0][0] if kind == "duplicate" else "../foreign")
                            bundle.addfile(m, io.BytesIO())
                    out = root / ("output-" + kind)
                    with self.assertRaises(ValueError):
                        fw.stage(target, out, manifest)
                    self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
