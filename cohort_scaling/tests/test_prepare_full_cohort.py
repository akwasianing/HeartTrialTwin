"""Local preparation checks; no database, model, download, or re-extraction."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prepare_full_cohort as full


class FullCohortPreparationTests(unittest.TestCase):
    def test_membership_is_all_2824_ids_and_contains_the_complete_pilot(self):
        ids = full.membership_ids()
        self.assertEqual(len(ids), 2824)
        self.assertEqual(len(set(ids)), 2824)
        self.assertEqual(ids, sorted(ids))
        self.assertTrue(set(full.pilot.select_ids()).issubset(ids))

    def test_frozen_manifest_checksum_mismatch_is_rejected(self):
        with patch.object(full.pilot, "digest", return_value="unverified"):
            with self.assertRaisesRegex(RuntimeError, "SHA-256"):
                full.membership_ids()

    def test_normalization_keeps_submitted_and_browse_conditions_distinct(self):
        reused = full.pilot.load_reused_logic()
        submitted = {"id": "1", "name": " Heart Failure "}
        equivalent = {"id": "2", "name": "heart failure"}
        browse = {"id": "3", "mesh_term": "Heart Failure"}
        self.assertEqual(full.entity_identity("conditions.txt", submitted, reused), full.entity_identity("conditions.txt", equivalent, reused))
        self.assertNotEqual(full.entity_identity("conditions.txt", submitted, reused), full.entity_identity("browse_conditions.txt", browse, reused))

    def test_only_lead_sponsors_become_graph_links(self):
        reused = full.pilot.load_reused_logic()
        self.assertTrue(full.included_source("sponsors.txt", {"lead_or_collaborator": "Lead"}, reused))
        self.assertFalse(full.included_source("sponsors.txt", {"lead_or_collaborator": "collaborator"}, reused))

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "refusing overwrite"):
                full.prepare(Path("archive-must-not-be-opened.zip"), Path(directory))

    def test_changed_output_fails_before_graph_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "example.csv").write_text("changed")
            manifest = {"graph_version": full.VERSION, "authoritative_dataset_version": full.DATASET, "files_sha256": {"example.csv": hashlib.sha256(b"original").hexdigest()}}
            (out / "full_cohort_manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                full.validate_saved(out)

    def test_delivered_full_graph_and_source_coverage_validate(self):
        result = full.validate_saved()
        self.assertEqual(result["node_counts"]["Trial"], 2824)
        self.assertEqual(result["node_counts"]["PlannedOutcome"], result["source_record_counts"]["design_outcomes.txt"])
        self.assertEqual(result["total_nodes"], sum(result["node_counts"].values()))
        self.assertEqual(result["total_relationships"], sum(result["relationship_counts"].values()))
        self.assertTrue(all(result["checks"].values()))

    def test_original_pilot_outputs_remain_valid(self):
        result = full.pilot.validate_saved(full.pilot.OUTPUT)
        self.assertEqual(result["node_counts"]["Trial"], 50)
        self.assertEqual(result["total_nodes"], 645)
        self.assertEqual(result["total_relationships"], 1494)


if __name__ == "__main__":
    unittest.main()
