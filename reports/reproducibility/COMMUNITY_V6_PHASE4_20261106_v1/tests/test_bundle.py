import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runtime_bundle", HERE / "runtime_bundle.py")
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


class BundleTests(unittest.TestCase):
    def fixture(self, root):
        root = Path(root)
        src, dest = root / "source", root / "candidate"
        src.mkdir(); dest.mkdir()
        (src / "asset.txt").write_text("verified fixture")
        entries = [{"path": "asset.txt", "sha256": bundle.sha(src / "asset.txt"), "bytes": 16}]
        return src, dest, entries

    def test_real_inventory_unchanged(self):
        self.assertEqual(len(bundle.inventory()), 190)

    def test_no_creation_without_explicit_owner_trust(self):
        with tempfile.TemporaryDirectory() as root:
            src, dest, entries = self.fixture(root)
            with patch.object(bundle, "inventory", return_value=entries), self.assertRaises(ValueError):
                bundle.create(src, dest, Path(root) / "private.tar")

    def test_exact_install_idempotence_and_deterministic_archive(self):
        with tempfile.TemporaryDirectory() as root:
            src, dest, entries = self.fixture(root)
            with patch.object(bundle, "inventory", return_value=entries):
                one = Path(root) / "one.tar"; two = Path(root) / "two.tar"
                first = bundle.create(src, dest, one, trusted_local_assets=True)
                second = bundle.create(src, dest, two, trusted_local_assets=True)
                self.assertEqual(first["archive_sha256"], second["archive_sha256"])
                self.assertEqual(bundle.install(one, dest, trusted_archive_sha256=bundle.sha(one))["copied"], 1)
                self.assertEqual(bundle.install(one, dest, trusted_archive_sha256=bundle.sha(one))["copied"], 0)
                self.assertEqual(bundle.sha(dest / "asset.txt"), entries[0]["sha256"])

    def test_tampered_source_or_archive_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            src, dest, entries = self.fixture(root)
            (src / "asset.txt").write_text("tampered fixture")
            with patch.object(bundle, "inventory", return_value=entries), self.assertRaises(ValueError):
                bundle.create(src, dest, Path(root) / "bad.tar", trusted_local_assets=True)
            self.assertFalse((Path(root) / "bad.tar").exists())
            bad = Path(root) / "invalid.tar"; bad.write_bytes(b"not a tar")
            with self.assertRaises(ValueError):
                bundle.install(bad, dest, trusted_archive_sha256="0" * 64)

    def test_existing_destination_is_never_repaired(self):
        with tempfile.TemporaryDirectory() as root:
            src, dest, entries = self.fixture(root)
            with patch.object(bundle, "inventory", return_value=entries):
                archive = Path(root) / "private.tar"
                bundle.create(src, dest, archive, trusted_local_assets=True)
                (dest / "asset.txt").write_text("preserve existing")
                with self.assertRaises(ValueError):
                    bundle.install(archive, dest, trusted_archive_sha256=bundle.sha(archive))
                self.assertEqual((dest / "asset.txt").read_text(), "preserve existing")

    def test_unsafe_paths_and_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ["../outside", "/absolute", ".env", "config/.env.example", "a\\b"]:
                with self.assertRaises(ValueError):
                    bundle.safe(root, name)
            (Path(root) / "link").symlink_to(Path(root) / "target")
            with self.assertRaises(ValueError):
                bundle.safe(root, "link/asset")

    def test_malicious_members_rejected_before_any_writes(self):
        with tempfile.TemporaryDirectory() as root:
            src, dest, entries = self.fixture(root)
            for index, mode in enumerate(["traversal", "duplicate", "symlink", "wrong_hash", "missing"]):
                archive = Path(root) / f"bad{index}.tar"
                with tarfile.open(archive, "w") as tar:
                    if mode != "missing":
                        m = tarfile.TarInfo("../outside" if mode == "traversal" else "payload/asset.txt")
                        data = b"verified fixture" if mode != "wrong_hash" else b"incorrect bytes!"
                        m.size = len(data)
                        if mode == "symlink":
                            m.type, m.linkname, m.size = tarfile.SYMTYPE, "outside", 0
                        tar.addfile(m, io.BytesIO(data))
                        if mode == "duplicate":
                            tar.addfile(m, io.BytesIO(data))
                with patch.object(bundle, "inventory", return_value=entries), self.assertRaises(ValueError):
                    bundle.install(archive, dest, trusted_archive_sha256=bundle.sha(archive))
                self.assertFalse((dest / "asset.txt").exists())


if __name__ == "__main__":
    unittest.main()
