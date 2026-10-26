"""Offline pilot payload and mocked target-isolation tests. No live driver."""

import contextlib
import copy
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import import_pilot as importer


class PilotImporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = importer.load_pilot()

    def test_complete_payload_matches_verified_pilot_counts(self):
        result = importer.summary(self.graph)
        self.assertEqual(result["total_nodes"], 645)
        self.assertEqual(result["total_relationships"], 1494)
        self.assertEqual(result["node_counts"]["Trial"], 50)
        self.assertEqual(result["node_counts"]["PlannedOutcome"], 336)
        self.assertEqual(len(result["relationship_counts"]), 7)
        self.assertEqual(len(result["node_counts"]), 6)

    def test_safe_properties_and_identifier_mapping(self):
        for spec in importer.NODE_SPECS:
            for row in self.graph.nodes[spec.label]:
                props = row["properties"]
                self.assertEqual(row["id"], props[spec.id_property])
                self.assertFalse(set(props) & importer.preparation.PROHIBITED)
                self.assertFalse(any(":ID(" in key or key == ":LABEL" for key in props))
        self.assertTrue(all(row["properties"]["evidence_safeguard"] == importer.preparation.SAFEGUARD for row in self.graph.nodes["PlannedOutcome"]))

    def test_condition_source_ids_and_renamed_files_preserved(self):
        self.assertIn("relationships_condition_term_source_dataset.csv", self.graph.relationships)
        self.assertIn("relationships_planned_outcome_source_dataset.csv", self.graph.relationships)
        for filename in ("relationships_trial_submitted_condition.csv", "relationships_trial_browse_condition.csv"):
            for row in self.graph.relationships[filename]:
                self.assertTrue(row["properties"]["source_record_ids"])
                self.assertNotIn("source_record_id", row["properties"])

    def test_source_dataset_provenance_matches_manifest(self):
        source = self.graph.nodes["SourceDataset"][0]["properties"]
        self.assertEqual(source["graph_version"], importer.preparation.VERSION)
        self.assertEqual(source["snapshot_date"], "2026-09-05")
        self.assertEqual(source["archive_sha256"], self.graph.manifest["archive"]["sha256"])
        self.assertEqual(source["pinned_manifest_sha256"], importer.preparation.MEMBERSHIP_SHA)

    def test_baseline_csv_header_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nodes_trial.csv"
            path.write_text("trial_id:ID(Trial),nct_id,dataset_version,:LABEL\nNCT00000001,NCT00000001,x,Trial\n")
            with self.assertRaisesRegex(RuntimeError, "Header mismatch"):
                importer.reference.read_csv(path, importer.NODE_HEADERS["Trial"])

    def test_tampered_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "pilot_manifest.json").write_text(json.dumps({"pilot_version": "unverified"}))
            with self.assertRaisesRegex(importer.PilotImportError, "SHA-256"):
                importer.load_pilot(path)

    def test_tampered_csv_is_rejected_by_checksums(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pilot"
            shutil.copytree(importer.preparation.OUTPUT, path)
            with (path / "nodes_trial.csv").open("a") as handle:
                handle.write("\n")
            with self.assertRaisesRegex(RuntimeError, "hash mismatch|Checksum"):
                importer.load_pilot(path)

    def test_duplicate_node_and_invalid_endpoint_are_rejected(self):
        graph = copy.deepcopy(self.graph)
        graph.nodes["Trial"][1] = copy.deepcopy(graph.nodes["Trial"][0])
        with self.assertRaisesRegex(importer.PilotImportError, "duplicate"):
            importer.validate_payload(graph)
        graph = copy.deepcopy(self.graph)
        graph.relationships["relationships_trial_planned_outcome.csv"][0]["start_id"] = "NCT99999999"
        with self.assertRaisesRegex(importer.PilotImportError, "endpoint"):
            importer.validate_payload(graph)

    def test_wrong_graph_and_outcome_provenance_are_rejected(self):
        graph = copy.deepcopy(self.graph)
        graph.nodes["SourceDataset"][0]["properties"]["graph_version"] = "HTT-KG-AACT-20260905-v1"
        with self.assertRaisesRegex(importer.PilotImportError, "provenance"):
            importer.validate_payload(graph)
        graph = copy.deepcopy(self.graph)
        graph.relationships["relationships_trial_planned_outcome.csv"][0]["properties"]["source_record_id"] = "invented"
        with self.assertRaisesRegex(importer.PilotImportError, "linkage"):
            importer.validate_payload(graph)

    def test_missing_payload_rows_fail_manifest_derived_counts(self):
        graph = copy.deepcopy(self.graph)
        graph.nodes["PlannedOutcome"].pop()
        with self.assertRaisesRegex(importer.PilotImportError, "counts"):
            importer.validate_payload(graph)

    def test_dedicated_config_never_falls_back_to_baseline_variables(self):
        with self.assertRaisesRegex(importer.PilotImportError, "dedicated"):
            importer.load_config(environ={"NEO4J_URI": "neo4j+s://57aa5fa3.databases.neo4j.io", "NEO4J_USERNAME": "secret-user", "NEO4J_PASSWORD": "secret-password", "NEO4J_DATABASE": "57aa5fa3"})

    def test_baseline_database_or_endpoint_rejected_including_url_variants(self):
        for uri, database in (
            ("bolt://localhost:7687", "57aa5fa3"),
            ("bolt://localhost:7687", "57AA5FA3"),
            ("neo4j+s://57aa5fa3.databases.neo4j.io", "pilot"),
            ("bolt+s://57AA5FA3.databases.neo4j.io.:7687", "pilot"),
            ("neo4j+s://%35%37aa5fa3.databases.neo4j.io", "pilot"),
        ):
            with self.subTest(uri=uri, database=database):
                with self.assertRaisesRegex(importer.PilotImportError, "prohibited"):
                    importer.validate_target(importer.PilotConfig(uri, "test-user", "test-password", database))

    def test_config_hides_credentials_and_accepts_dedicated_target(self):
        config = importer.load_config(environ={
            "PILOT_NEO4J_URI": "bolt://localhost:17687", "PILOT_NEO4J_USERNAME": "test-user",
            "PILOT_NEO4J_PASSWORD": "test-password", "PILOT_NEO4J_DATABASE": "pilot",
        })
        self.assertNotIn("test-password", repr(config))
        self.assertNotIn("test-user", repr(config))
        self.assertNotIn("localhost", repr(config))

    def test_default_dry_run_never_loads_credentials_or_executes(self):
        with patch.object(importer, "load_config", side_effect=AssertionError("Credentials accessed")), patch.object(importer, "execute_pilot", side_effect=AssertionError("Execution attempted")), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(importer.main([]), 0)
        self.assertEqual(json.loads(output.getvalue())["mode"], "OFFLINE_DRY_RUN")

    def test_baseline_and_missing_confirmations_rejected_before_driver_creation(self):
        factory = MagicMock(side_effect=AssertionError("Driver must not be created"))
        for config, confirmation in (
            (importer.PilotConfig("neo4j+s://57aa5fa3.databases.neo4j.io", "test-user", "test-password", "pilot"), "pilot"),
            (importer.PilotConfig("bolt://localhost:17687", "test-user", "test-password", "pilot"), "wrong"),
        ):
            with self.assertRaises(importer.PilotImportError):
                importer.execute_pilot(self.graph, config, confirm_database=confirmation, confirm_pilot_version=importer.preparation.VERSION, driver_factory=factory)
        factory.assert_not_called()

    def test_identity_mismatch_and_nonempty_target_rejected_before_writes(self):
        config = importer.PilotConfig("bolt://localhost:17687", "test-user", "test-password", "pilot")
        for wrong_identity in (True, False):
            driver = MagicMock()
            driver.__enter__.return_value = driver
            rows = [([{"name": "wrong" if wrong_identity else "pilot"}], None, None)]
            if not wrong_identity:
                rows.append(([{"node_count": 26, "relationship_count": 65}], None, None))
            driver.execute_query.side_effect = rows
            with self.assertRaises(importer.PilotImportError):
                importer.execute_pilot(self.graph, config, confirm_database="pilot", confirm_pilot_version=importer.preparation.VERSION, driver_factory=lambda *a, **k: driver)
            driver.session.assert_not_called()

    def test_mocked_full_import_batches_and_verifies_exact_payload(self):
        config = importer.PilotConfig("bolt://localhost:17687", "test-user", "test-password", "pilot")
        driver, session, tx = MagicMock(), MagicMock(), MagicMock()
        driver.__enter__.return_value = driver
        driver.session.return_value.__enter__.return_value = session
        nodes = {spec.label: [] for spec in importer.NODE_SPECS}
        edges = {spec.filename: [] for spec in importer.RELATIONSHIP_SPECS}
        node_queries = {importer.reference.node_merge_query(spec): spec.label for spec in importer.NODE_SPECS}
        edge_queries = {importer.reference.relationship_merge_query(spec): spec.filename for spec in importer.RELATIONSHIP_SPECS}
        write_order = []

        def run(query, **parameters):
            result = MagicMock()
            if query in node_queries:
                nodes[node_queries[query]].extend(copy.deepcopy(parameters["rows"]))
                write_order.append("node")
                count = len(parameters["rows"])
            elif query in edge_queries:
                edges[edge_queries[query]].extend(copy.deepcopy(parameters["rows"]))
                write_order.append("edge")
                count = len(parameters["rows"])
            else:
                count = sum(map(len, nodes.values())) if query.startswith("MATCH (n)") else sum(map(len, edges.values()))
                result.single.return_value = {"count": count}
                return result
            self.assertLessEqual(count, 100)
            self.assertIn("$rows", query)
            result.single.return_value = {"imported": count}
            return result

        def read(query, **parameters):
            self.assertEqual(parameters["database_"], "pilot")
            if query.startswith("CALL db.info"):
                rows = [{"name": "pilot"}]
            elif query == importer.reference.TOTALS_QUERY:
                rows = [{"node_count": sum(map(len, nodes.values())), "relationship_count": sum(map(len, edges.values()))}]
            elif query.startswith("MATCH (n:"):
                label = query.split("MATCH (n:")[1].split(")")[0]
                rows = nodes[label]
            else:
                rows = []
                for spec in importer.RELATIONSHIP_SPECS:
                    prefix = f"MATCH (a:{spec.start_label})-[r:{spec.relationship_type}]->(b:{spec.end_label})"
                    if query.startswith(prefix):
                        rows = edges[spec.filename]
                        break
            return rows, None, None
        tx.run.side_effect = run
        driver.execute_query.side_effect = read
        session.execute_write.side_effect = lambda action: action(tx)
        result = importer.execute_pilot(self.graph, config, confirm_database="pilot", confirm_pilot_version=importer.preparation.VERSION, driver_factory=lambda *a, **k: driver)
        self.assertEqual(result["mode"], "IMPORTED_AND_VERIFIED")
        self.assertEqual(sum(map(len, nodes.values())), 645)
        self.assertEqual(sum(map(len, edges.values())), 1494)
        self.assertNotIn("node", write_order[write_order.index("edge"):])


if __name__ == "__main__":
    unittest.main()
