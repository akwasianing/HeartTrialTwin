"""Offline integrity tests; no torch, encoder, database, or network is needed."""

import csv
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from collections import Counter
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from gnn_graphrag.src import extract_full_cohort as extraction


def read(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class FullCohortExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name) / "extracted"
        cls.graph = extraction.load_verified_full_graph()
        cls.manifest = extraction.extract_full_cohort(output_dir=cls.output)
        cls.nodes = read(cls.output / "nodes.csv")
        cls.relationships = read(cls.output / "relationships.csv")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_source_pin_all_checksums_and_versions(self):
        manifest = self.manifest
        self.assertEqual(extraction.sha256(extraction.DEFAULT_SOURCE / "full_cohort_manifest.json"), extraction.MANIFEST_SHA256)
        self.assertEqual(manifest["validation"]["source_files_verified"], 26)
        self.assertEqual(manifest["source"]["all_manifest_listed_file_sha256"], self.graph.manifest["files_sha256"])
        self.assertTrue(manifest["validation"]["frozen_manifest_checksum_passed"])
        self.assertEqual(manifest["source"]["graph_version"], extraction.GRAPH_VERSION)
        self.assertEqual(manifest["source"]["dataset_version"], extraction.DATASET_VERSION)
        self.assertEqual(manifest["source"]["snapshot_date"], "2026-09-05")

    def test_exact_counts_membership_and_deterministic_node_order(self):
        counts = self.manifest["counts"]
        self.assertEqual(len(self.nodes), 28777)
        self.assertEqual(len(self.relationships), 79125)
        self.assertEqual(counts["semantic_original_relationships"], 50349)
        self.assertEqual(counts["semantic_message_edges_total"], 100698)
        self.assertEqual(dict(Counter(row["node_label"] for row in self.nodes)),
            {"Trial": 2824, "ConditionTerm": 1743, "Intervention": 3417, "Sponsor": 1052,
             "PlannedOutcome": 19740, "SourceDataset": 1})
        self.assertEqual([int(row["node_index"]) for row in self.nodes], list(range(28777)))
        order = {label: index for index, label in enumerate(extraction.NODE_ORDER)}
        keys = [(order[row["node_label"]], row["node_id"]) for row in self.nodes]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual({row["node_id"] for row in self.nodes if row["node_label"] == "Trial"}, set(self.graph.membership))

    def test_all_original_relationships_properties_and_directions_preserved(self):
        expected = {(rel.source_id, rel.relationship_type, rel.target_id, rel.source_file,
                     extraction.canonical(rel.properties)) for rel in self.graph.relationships}
        actual = set()
        for index, row in enumerate(self.relationships):
            self.assertEqual(int(row["relationship_index"]), index)
            source, target = self.nodes[int(row["source_node_index"])], self.nodes[int(row["target_node_index"])]
            self.assertEqual((source["node_id"], source["node_label"]), (row["source_node_id"], row["source_node_label"]))
            self.assertEqual((target["node_id"], target["node_label"]), (row["target_node_id"], row["target_node_label"]))
            actual.add((row["source_node_id"], row["relationship_type"], row["target_node_id"], row["source_file"], row["properties_json"]))
        self.assertEqual(len(actual), len(self.relationships))
        self.assertEqual(actual, expected)

    def test_reverse_edges_unique_and_exactly_bound_to_original_edges(self):
        seen, counts = set(), Counter()
        with (self.output / "message_edges_semantic.csv").open(newline="", encoding="utf-8") as handle:
            for index, row in enumerate(csv.DictReader(handle)):
                self.assertEqual(int(row["message_edge_index"]), index)
                rel = self.relationships[int(row["original_relationship_index"])]
                self.assertNotIn(row["relationship_type"], extraction.PROVENANCE_TYPES)
                self.assertEqual(row["relationship_type"], rel["relationship_type"])
                direction = row["message_direction"]
                self.assertIn(direction, ("forward", "reverse"))
                s, t = ("source", "target") if direction == "forward" else ("target", "source")
                for prefix, expected_prefix in (("source", s), ("target", t)):
                    self.assertEqual(row[prefix + "_node_index"], rel[expected_prefix + "_node_index"])
                    self.assertEqual(row[prefix + "_node_label"], rel[expected_prefix + "_node_label"])
                key = (row["source_node_index"], row["relationship_type"], row["target_node_index"])
                self.assertNotIn(key, seen)
                seen.add(key)
                counts[(row["original_relationship_index"], direction)] += 1
        self.assertEqual(len(seen), 100698)
        for row in self.relationships:
            for direction in ("forward", "reverse"):
                self.assertEqual(counts[(row["relationship_index"], direction)],
                                 int(row["relationship_type"] not in extraction.PROVENANCE_TYPES))

    def test_provenance_and_all_original_node_metadata_retained(self):
        source = {node.node_id: node for node in self.graph.nodes}
        for row in self.nodes:
            node = source[row["node_id"]]
            spec = extraction.NODE_SPEC_BY_LABEL[node.label]
            expected = {k: v for k, v in node.properties.items() if k not in (spec.id_header, ":LABEL")}
            self.assertEqual(json.loads(row["properties_json"]), expected)
            self.assertEqual(row["graph_version"], extraction.GRAPH_VERSION)
        counts = Counter(row["relationship_type"] for row in self.relationships)
        self.assertEqual(counts["MEMBER_OF_DATASET"], 2824)
        self.assertEqual(counts["SOURCED_FROM"], 25952)
        self.assertTrue(self.manifest["message_passing_policy"]["original_provenance_preserved"])

    def test_feature_allowlist_identifier_redaction_and_prohibited_values(self):
        properties = {field: "FORBIDDEN_" + field for field in self.manifest["feature_policy"]["prohibited_fields"]}
        properties.update(nct_id="NCT00206232", brief_title="Title NCT00206232", study_type="INTERVENTIONAL", phase="PHASE2")
        text = extraction.feature_text("Trial", properties)
        self.assertNotIn("NCT00206232", text)
        self.assertNotIn("FORBIDDEN_", text)
        self.assertIn("Title: Title", text)
        source = {node.node_id: node for node in self.graph.nodes}
        for row in self.nodes:
            self.assertIsNone(extraction.NCT_TOKEN.search(row["feature_text"]))
            self.assertEqual(row["feature_text"], extraction.feature_text(row["node_label"], source[row["node_id"]].properties))
            self.assertEqual(row["feature_text_sha256"], hashlib.sha256(row["feature_text"].encode()).hexdigest())
            if row["node_label"] == "PlannedOutcome":
                self.assertIn(extraction.prototype.PLANNED_OUTCOME_SAFEGUARD, row["feature_text"])

    def test_missing_values_and_missing_trial_evidence_not_imputed(self):
        outcomes = [json.loads(r["properties_json"]) for r in self.nodes if r["node_label"] == "PlannedOutcome"]
        self.assertEqual(sum(p["time_frame"] == "" for p in outcomes), 528)
        self.assertTrue(all(p["population"] == "" for p in outcomes))
        self.assertEqual(sum("time_frame" in json.loads(row["missing_feature_fields_json"])
            for row in self.nodes if row["node_label"] == "PlannedOutcome"), 528)
        missing = self.manifest["missingness"]["source_missing_trial_ids"]
        self.assertEqual(len(missing["design_outcomes.txt"]), 41)
        self.assertEqual(len(missing["browse_conditions.txt"]), 253)
        self.assertIn("NCT00000475", {r["node_id"] for r in self.nodes})
        self.assertFalse(any(r["source_node_id"] == "NCT00000475" and r["relationship_type"] == "HAS_PLANNED_OUTCOME" for r in self.relationships))

    def test_no_training_readiness_claims_or_embedding_outputs(self):
        state = self.manifest["training_readiness"]
        self.assertEqual(state["status"], "PRE_SPLIT_NOT_LEAKAGE_SAFE")
        self.assertIn("reverse edges", state["warning"])
        self.assertTrue(state["target_associations_present"])
        for field in ("training_performed", "embeddings_computed", "message_passing_performed", "splits_created"):
            self.assertFalse(state[field])
        self.assertEqual({p.name for p in self.output.iterdir()},
                         {"nodes.csv", "relationships.csv", "message_edges_semantic.csv", "extraction_manifest.json", "SHA256SUMS"})

    def test_byte_deterministic_regeneration_output_hashes_and_no_overwrite(self):
        other = Path(self.temp.name) / "second"
        extraction.extract_full_cohort(output_dir=other)
        for path in self.output.iterdir():
            self.assertEqual(path.read_bytes(), (other / path.name).read_bytes(), path.name)
        for name, record in self.manifest["outputs"].items():
            self.assertEqual(extraction.sha256(self.output / name), record["sha256"])
        for line in (self.output / "SHA256SUMS").read_text().splitlines():
            digest, name = line.split("  ")
            self.assertEqual(extraction.sha256(self.output / name), digest)
        with self.assertRaisesRegex(extraction.FullExtractionError, "already exists"):
            extraction.extract_full_cohort(output_dir=self.output)

    def test_source_manifest_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "full_cohort_manifest.json"
            shutil.copyfile(extraction.DEFAULT_SOURCE / path.name, path)
            path.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaisesRegex(extraction.FullExtractionError, "manifest SHA-256"):
                extraction.load_verified_full_graph(Path(directory))

    def test_source_cache_tampering_rejected_before_output_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            shutil.copytree(extraction.DEFAULT_SOURCE, source)
            with (source / "source_cache/design_outcomes.jsonl").open("a") as handle:
                handle.write("\n")
            output = Path(directory) / "output"
            with self.assertRaisesRegex(extraction.FullExtractionError, "Source SHA-256 mismatch: source_cache/design_outcomes.jsonl"):
                extraction.extract_full_cohort(source, output)
            self.assertFalse(output.exists())

    def test_unexpected_csv_schema_and_malformed_rows_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            path.write_text("nct_id,extra\nNCT00206232,unsafe\n")
            with self.assertRaisesRegex(extraction.FullExtractionError, "CSV schema"):
                extraction.read_csv(path, ("nct_id",))
            path.write_text("nct_id\nNCT00206232,extra\n")
            with self.assertRaisesRegex(extraction.FullExtractionError, "Malformed CSV"):
                extraction.read_csv(path, ("nct_id",))

    def test_duplicate_identifiers_relationships_and_wrong_counts_rejected(self):
        with self.assertRaisesRegex(extraction.FullExtractionError, "duplicate node"):
            extraction.validate_graph(replace(self.graph, nodes=self.graph.nodes + (self.graph.nodes[0],)))
        with self.assertRaisesRegex(extraction.FullExtractionError, "Duplicate relationship"):
            extraction.validate_graph(replace(self.graph, relationships=self.graph.relationships + (self.graph.relationships[0],)))
        without_condition = tuple(node for i, node in enumerate(self.graph.nodes) if i != 2824)
        with self.assertRaisesRegex(extraction.FullExtractionError, "Node count"):
            extraction.validate_graph(replace(self.graph, nodes=without_condition))

    def test_invalid_endpoints_and_cross_trial_outcome_association_rejected(self):
        bad = replace(self.graph.relationships[0], target_id="missing:node")
        with self.assertRaisesRegex(extraction.FullExtractionError, "Invalid relationship endpoint"):
            extraction.validate_graph(replace(self.graph, relationships=(bad,) + self.graph.relationships[1:]))
        index = next(i for i, rel in enumerate(self.graph.relationships) if rel.relationship_type == "HAS_PLANNED_OUTCOME")
        rel = self.graph.relationships[index]
        different_nct = next(nct for nct in self.graph.membership if nct != rel.source_id)
        bad = replace(rel, source_id=different_nct)
        altered = self.graph.relationships[:index] + (bad,) + self.graph.relationships[index + 1:]
        with self.assertRaisesRegex(extraction.FullExtractionError, "trial/source association"):
            extraction.validate_graph(replace(self.graph, relationships=altered))

    def test_provenance_and_node_property_tampering_rejected(self):
        index = next(i for i, node in enumerate(self.graph.nodes) if node.label == "SourceDataset")
        node = self.graph.nodes[index]
        bad = replace(node, properties={**node.properties, "snapshot_date": "2026-09-06"})
        with self.assertRaisesRegex(extraction.FullExtractionError, "SourceDataset provenance"):
            extraction.validate_graph(replace(self.graph, nodes=self.graph.nodes[:index] + (bad,) + self.graph.nodes[index + 1:]))
        node = self.graph.nodes[0]
        bad = replace(node, properties={**node.properties, "overall_status": "SECRET"})
        with self.assertRaisesRegex(extraction.FullExtractionError, "node property schema"):
            extraction.validate_graph(replace(self.graph, nodes=(bad,) + self.graph.nodes[1:]))


if __name__ == "__main__":
    unittest.main()
