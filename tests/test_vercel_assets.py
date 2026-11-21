"""Integrity failures must stop asset preparation before a runtime is deployed."""

import hashlib
import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from backend.prepare_runtime import unpack, verified


class VercelAssetTests(unittest.TestCase):
    def test_same_size_corruption_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "file"
            path.write_bytes(b"abc")
            spec = {"bytes": 3, "sha256": hashlib.sha256(b"abc").hexdigest()}
            self.assertTrue(verified(path, spec))
            path.write_bytes(b"abd")
            self.assertFalse(verified(path, spec))

    @staticmethod
    def archive(path, files):
        with tarfile.open(path, "w:gz") as tar:
            for name, content in files.items():
                info = tarfile.TarInfo(name)
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))

    def test_unexpected_archive_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "archive.tar.gz"
            self.archive(archive, {"runtime-manifest.json": b"{}", "unexpected": b"x"})
            with self.assertRaisesRegex(ValueError, "Unexpected files"):
                unpack(archive, root / "runtime", [])

    def test_path_escape_is_rejected_even_if_listed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "archive.tar.gz"
            self.archive(archive, {"runtime-manifest.json": b"{}", "../escape": b"x"})
            with self.assertRaisesRegex(ValueError, "Unsafe runtime"):
                unpack(archive, root / "runtime", [{"path": "../escape", "bytes": 1}])
            self.assertFalse((root / "escape").exists())

    def test_valid_archive_preserves_exact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "archive.tar.gz"
            payload = b"unchanged vector index bytes"
            spec = {"path": "data/index", "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest()}
            self.archive(archive, {"runtime-manifest.json": b"{}", spec["path"]: payload})
            unpack(archive, root / "runtime", [spec])
            self.assertEqual((root / "runtime/data/index").read_bytes(), payload)


if __name__ == "__main__":
    unittest.main()
