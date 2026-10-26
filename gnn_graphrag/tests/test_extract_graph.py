"""Tests for deterministic HeartTrialTwin graph extraction."""

from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "gnn_graphrag" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import extract_graph as extraction  # noqa: E402


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class GraphExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls.tempdir.name) / "output"
        cls.manifest = extraction.extract_graph(output_dir=cls.output_dir)
        cls.nodes = read_csv(cls.output_dir / "nodes.csv")
        cls.relationships = read_csv(cls.output_dir / "relationships.csv")
        cls.full_messages = read_csv(cls.output_dir / "message_edges_full.csv")
        cls.semantic_messages = read_csv(cls.output_dir / "message_edges_semantic.csv")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tempdir.cleanup()

    def test_versions_hashes_and_counts_are_verified(self) -> None:
        source = self.manifest["source"]
        counts = self.manifest["counts"]
        self.assertEqual(source["dataset_version"], extraction.EXPECTED_DATASET_VERSION)
        self.assertEqual(source["graph_version"], extraction.EXPECTED_GRAPH_VERSION)
        self.assertEqual(source["snapshot_date"], extraction.EXPECTED_SNAPSHOT_DATE)
        self.assertEqual(len(source["source_file_sha256"]), 16)
        self.assertTrue(all(len(value) == 64 for value in source["source_file_sha256"].values()))
        self.assertEqual(counts["nodes_total"], 26)
        self.assertEqual(counts["original_directed_relationships_total"], 65)
        self.assertEqual(counts["full_message_edges_total"], 130)
        self.assertEqual(counts["semantic_message_edges_total"], 80)

    def test_source_hash_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "knowledge_graph"
            copied.mkdir()
            filenames = ["graph_import_manifest.json"]
            filenames.extend(spec.filename for spec in extraction.NODE_SPECS)
            filenames.extend(spec.filename for spec in extraction.RELATIONSHIP_SPECS)
            for filename in filenames:
                shutil.copy2(extraction.DEFAULT_SOURCE_DIR / filename, copied / filename)
            path = copied / "nodes_trial.csv"
            path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaisesRegex(extraction.ExtractionError, "Source hash mismatch"):
                extraction.load_verified_graph(copied)

    def test_node_indices_follow_declared_deterministic_order(self) -> None:
        self.assertEqual([int(row["node_index"]) for row in self.nodes], list(range(26)))
        expected_labels = []
        for label in extraction.NODE_LABEL_ORDER:
            label_rows = [row for row in self.nodes if row["node_label"] == label]
            self.assertEqual(
                [row["node_id"] for row in label_rows],
                sorted(row["node_id"] for row in label_rows),
            )
            expected_labels.extend([label] * len(label_rows))
        self.assertEqual([row["node_label"] for row in self.nodes], expected_labels)
        self.assertEqual(len({row["node_id"] for row in self.nodes}), 26)

    def test_original_relationships_preserve_direction_and_valid_endpoints(self) -> None:
        node_by_index = {row["node_index"]: row for row in self.nodes}
        triples = set()
        for row in self.relationships:
            self.assertIn(row["source_node_index"], node_by_index)
            self.assertIn(row["target_node_index"], node_by_index)
            self.assertEqual(
                node_by_index[row["source_node_index"]]["node_id"],
                row["source_node_id"],
            )
            self.assertEqual(
                node_by_index[row["target_node_index"]]["node_id"],
                row["target_node_id"],
            )
            triple = (
                row["source_node_id"],
                row["relationship_type"],
                row["target_node_id"],
            )
            self.assertNotIn(triple, triples)
            triples.add(triple)
        self.assertEqual(len(triples), 65)

    def test_message_edges_are_bidirectional_and_have_expected_counts(self) -> None:
        self.assertEqual(len(self.full_messages), 130)
        self.assertEqual(len(self.semantic_messages), 80)
        for rows in (self.full_messages, self.semantic_messages):
            grouped: dict[str, list[dict[str, str]]] = {}
            for row in rows:
                grouped.setdefault(row["original_relationship_index"], []).append(row)
            for pair in grouped.values():
                self.assertEqual(len(pair), 2)
                forward = next(row for row in pair if row["message_direction"] == "forward")
                reverse = next(row for row in pair if row["message_direction"] == "reverse")
                self.assertEqual(forward["source_node_index"], reverse["target_node_index"])
                self.assertEqual(forward["target_node_index"], reverse["source_node_index"])
                self.assertEqual(forward["relationship_type"], reverse["relationship_type"])

    def test_provenance_is_preserved_but_excluded_from_semantic_messages(self) -> None:
        original_provenance = [
            row
            for row in self.relationships
            if row["relationship_type"] in extraction.PROVENANCE_RELATIONSHIP_TYPES
        ]
        full_provenance = [
            row
            for row in self.full_messages
            if row["relationship_type"] in extraction.PROVENANCE_RELATIONSHIP_TYPES
        ]
        semantic_provenance = [
            row
            for row in self.semantic_messages
            if row["relationship_type"] in extraction.PROVENANCE_RELATIONSHIP_TYPES
        ]
        self.assertEqual(len(original_provenance), 25)
        self.assertEqual(len(full_provenance), 50)
        self.assertEqual(semantic_provenance, [])
        self.assertTrue(self.manifest["message_passing"]["semantic_graph"]["provenance_preserved_in_original_graph"])

    def test_feature_text_uses_only_approved_fields_and_safeguard(self) -> None:
        sentinel_properties = {
            "nct_id": "NCT00000001",
            "brief_title": "Approved title",
            "study_type": "INTERVENTIONAL",
            "phase": "PHASE2",
            "enrollment": "SECRET_ENROLLMENT",
            "completion_date": "SECRET_COMPLETION",
            "overall_status": "SECRET_STATUS",
            "termination_reason": "SECRET_REASON",
            "prediction_label": "SECRET_LABEL",
            "observed_result": "SECRET_RESULT",
        }
        text = extraction.canonical_feature_text("Trial", sentinel_properties)
        for sentinel in (
            "SECRET_ENROLLMENT",
            "SECRET_COMPLETION",
            "SECRET_STATUS",
            "SECRET_REASON",
            "SECRET_LABEL",
            "SECRET_RESULT",
        ):
            self.assertNotIn(sentinel, text)

        planned_rows = [row for row in self.nodes if row["node_label"] == "PlannedOutcome"]
        self.assertEqual(len(planned_rows), 10)
        for row in planned_rows:
            self.assertIn(extraction.PLANNED_OUTCOME_SAFEGUARD, row["feature_text"])
            self.assertNotIn("Observed result:", row["feature_text"])
        for row in self.nodes:
            self.assertNotIn("Completion date:", row["feature_text"])
            self.assertNotIn("Enrollment:", row["feature_text"])
            self.assertNotIn("Termination reason:", row["feature_text"])
            self.assertNotIn("Prediction", row["feature_text"])
            self.assertNotIn("original registration record", row["feature_text"].casefold())

    def test_regeneration_is_byte_deterministic_and_manifest_hashes_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            second_dir = Path(directory) / "second"
            second_manifest = extraction.extract_graph(output_dir=second_dir)
            for filename in (
                "nodes.csv",
                "relationships.csv",
                "message_edges_full.csv",
                "message_edges_semantic.csv",
                "extraction_manifest.json",
            ):
                self.assertEqual(
                    (self.output_dir / filename).read_bytes(),
                    (second_dir / filename).read_bytes(),
                )
            for filename, record in second_manifest["outputs"].items():
                self.assertEqual(record["sha256"], extraction.sha256_path(second_dir / filename))


if __name__ == "__main__":
    unittest.main()
