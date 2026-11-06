"""Small standard-library checks; no application/service/model invocation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("phase3_workspace", HERE / "prepare_workspace.py")
workspace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workspace)


class HandoffTests(unittest.TestCase):
    def test_runtime_inventory_is_unique_and_scoped(self):
        inventory = json.loads((HERE / "RUNTIME_ASSETS.json").read_text())
        entries = inventory["required_assets"]
        self.assertEqual(len(entries), 190)
        self.assertEqual(len({e["path"] for e in entries}), 190)
        self.assertEqual(sum(e["path"].endswith(".joblib") for e in entries), 4)
        self.assertTrue(all(e["classification"] == "UNSUITABLE_FOR_PUBLIC_DISTRIBUTION"
                            for e in entries if e["path"].endswith(".joblib")))

    def test_unsafe_paths_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            for path in ["../outside", "/absolute", "app/.env", "app/.env.private"]:
                with self.subTest(path=path), self.assertRaises(ValueError):
                    workspace.safe(temp, path)

    def test_checked_copy_and_no_source_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            src, dst = Path(temp) / "source", Path(temp) / "target"
            src.mkdir(); dst.mkdir()
            p = src / "record.txt"; p.write_text("verified fixture")
            entry = {"path": "record.txt", "sha256": workspace.sha(p)}
            self.assertTrue(workspace.copy_checked(src, dst, entry))
            self.assertFalse(workspace.copy_checked(src, dst, entry))
            self.assertEqual(p.read_text(), "verified fixture")

    def test_different_destination_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            src, dst = Path(temp) / "source", Path(temp) / "target"
            src.mkdir(); dst.mkdir()
            (src / "record").write_text("expected"); (dst / "record").write_text("preserve")
            entry = {"path": "record", "sha256": workspace.sha(src / "record")}
            with self.assertRaises(ValueError):
                workspace.copy_checked(src, dst, entry)
            self.assertEqual((dst / "record").read_text(), "preserve")

    def test_tampered_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            src, dst = Path(temp) / "source", Path(temp) / "target"
            src.mkdir(); dst.mkdir(); (src / "record").write_text("fixture")
            with self.assertRaises(ValueError):
                workspace.copy_checked(src, dst, {"path": "record", "sha256": "0" * 64})
            self.assertFalse((dst / "record").exists())

    def test_publication_omits_external_weights_and_private_config(self):
        allowlist = json.loads((HERE / "PUBLICATION_ALLOWLIST.json").read_text())
        self.assertNotIn("reports/final_project/HEARTTRIALTWIN_FINAL_20261102/modeling/train_exploratory.py",
                         {e["path"] for e in allowlist["files"]})
        for entry in allowlist["files"]:
            p = Path(entry["path"])
            self.assertFalse(p.suffix in {".joblib", ".pkl", ".pt", ".npy", ".gz", ".zip", ".parquet"})
            self.assertFalse(any(x.startswith(".env") or x == "backups" for x in p.parts))

    def test_original_frozen_membership_is_an_explicit_dependency(self):
        inventory = json.loads((HERE / "RUNTIME_ASSETS.json").read_text())
        found = [e for e in inventory["required_assets"] if e["path"].startswith("step3_manifest/")]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["authority"], "Graph manifest membership.frozen_source_sha256")


if __name__ == "__main__":
    unittest.main()
