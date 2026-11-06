"""Offline integrity/provisioning failures use temporary fixtures, never source edits."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import integrity
import provision


class IntegrityTests(unittest.TestCase):
    def fixture(self, root):
        p = Path(root) / "record.txt"
        p.write_text("verified fixture", encoding="utf-8")
        return {"schema_version": "HTT-COMMUNITY-V6-RUNTIME-v1", "assets": [
            {"path": "record.txt", "sha256": integrity.sha(p)}]}

    def test_real_pinned_runtime_and_b3(self):
        value = integrity.verify_runtime()
        self.assertEqual((value["trials"], value["communities"]), (2824, 904))
        self.assertFalse(value["ollama_enabled"])
        self.assertFalse(value["network_calls"])

    def test_receipt_authorities_preserve_existing_pins(self):
        receipt = integrity.load_receipt()
        entries = {r["path"]: r for r in receipt["assets"]}
        graph = entries[integrity.GRAPH + "/full_cohort_manifest.json"]
        self.assertEqual(graph["sha256"], "3ef82624d131b36abc1eb9ad4e89b3439fed9f9600b92262c21bbcbfe6cf8757")
        self.assertIn("inputs_sha256", entries[integrity.COMMUNITY]["authority"])
        self.assertTrue(all(".env" not in Path(p).parts for p in entries))

    def test_valid_provisioned_fixture(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(integrity.check_files(root, self.fixture(root)), [])

    def test_tampering_is_not_repaired(self):
        with tempfile.TemporaryDirectory() as root:
            receipt = self.fixture(root)
            p = Path(root) / "record.txt"
            p.write_text("changed", encoding="utf-8")
            self.assertEqual(integrity.check_files(root, receipt)[0]["reason"], "CHECKSUM_MISMATCH")
            self.assertEqual(p.read_text(), "changed")

    def test_missing_asset_reported(self):
        with tempfile.TemporaryDirectory() as root:
            receipt = self.fixture(root)
            (Path(root) / "record.txt").unlink()
            self.assertEqual(integrity.check_files(root, receipt)[0]["reason"], "MISSING")

    def test_duplicate_inventory_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            receipt = self.fixture(root)
            receipt["assets"] *= 2
            with self.assertRaises(integrity.IntegrityError):
                integrity.check_files(root, receipt)

    def test_path_traversal_absolute_and_env_rejected(self):
        for path in ["../record", "/tmp/record", "app/.env", "app/.env.example"]:
            with self.subTest(path=path), self.assertRaises(integrity.IntegrityError):
                integrity.safe_path(integrity.ROOT, path)

    def test_modified_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / "receipt.json"
            p.write_text("{}", encoding="utf-8")
            with patch.object(integrity, "RECEIPT", p), self.assertRaises(integrity.IntegrityError):
                integrity.load_receipt()

    def test_incorrect_b3_membership_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / integrity.COMMUNITY
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"results": [{"projection": "B3_exact_normalization",
                "runs": [{"seed": 42, "membership": {"NCT99999999": 0}}]}]}))
            with self.assertRaises(integrity.IntegrityError):
                integrity.b3_membership(root, {"NCT00206232"})

    def test_empty_checkout_is_not_claimed_reproducible(self):
        with tempfile.TemporaryDirectory() as root, contextlib.redirect_stdout(io.StringIO()) as output:
            result = provision.main(["--assets-root", root])
        data = json.loads(output.getvalue())
        self.assertEqual(result, 1)
        self.assertEqual(data["status"], "NOT_READY")
        self.assertFalse(data["clean_clone_reproduction_established"])
        self.assertGreater(len(data["asset_failures"]), 0)

    def test_inventory_never_contains_credentials_or_backups(self):
        paths = [r["path"] for r in integrity.load_receipt()["assets"]]
        self.assertFalse(any("backups/" in p or ".env" in p for p in paths))
        self.assertTrue(any(r["distribution"] == "EXTERNAL_TRUSTED_MODEL_DO_NOT_COMMIT"
                            for r in integrity.load_receipt()["assets"]))

    def test_local_environment_matches_without_model_import(self):
        self.assertEqual(provision.check_environment(), [])


if __name__ == "__main__":
    unittest.main()
