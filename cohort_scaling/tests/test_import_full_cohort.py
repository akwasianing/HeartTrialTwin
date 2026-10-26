"""Offline real-payload checks and an in-memory Neo4j fake; no live services."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import import_full_cohort as importer


class Result:
    def __init__(self, rows=()):
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)

    def single(self, strict=False):
        return next(iter(self.rows))

    def consume(self):
        return None


class Transaction:
    def __init__(self, driver):
        self.driver = driver
        self.pending = None

    def __enter__(self):
        self.driver.begun += 1
        return self

    def __exit__(self, *error):
        if error[0] is not None:
            self.driver.rollbacks += 1

    def run(self, query, **parameters):
        driver = self.driver
        if driver.fail_run_at == driver.begun:
            raise RuntimeError("private-password private-endpoint must never be printed")
        if "$rows" not in query or set(parameters) != {"rows"}:
            raise AssertionError("Fixed parameterized import query required")
        rows = parameters["rows"]
        if query in driver.node_queries:
            if any(driver.edges.values()):
                raise AssertionError("Nodes must precede relationships")
            category, name = "nodes", driver.node_queries[query]
        elif query in driver.edge_queries:
            category, name = "edges", driver.edge_queries[query]
        else:
            raise AssertionError("Unexpected write query")
        driver.batch_lengths.append(len(rows))
        self.pending = category, name, rows
        count = len(rows) - 1 if driver.wrong_batch_count else len(rows)
        return Result([{"imported": count}])

    def commit(self):
        category, name, rows = self.pending
        getattr(self.driver, category)[name].extend(rows)
        if self.driver.ambiguous_commit_at == self.driver.begun:
            raise RuntimeError("private-password: commit response lost")
        self.driver.commits += 1


class Session:
    def __init__(self, driver, database, **kwargs):
        if database != driver.database:
            raise AssertionError("Wrong database scope")
        self.driver = driver

    def __enter__(self):
        return self

    def __exit__(self, *error):
        pass

    def begin_transaction(self):
        return Transaction(self.driver)

    def run(self, query):
        driver = self.driver
        if query.startswith("CREATE CONSTRAINT") or query == "CALL db.awaitIndexes(30)":
            driver.schema_queries.append(query)
            return Result()
        if query.startswith("MATCH (n:"):
            label = query.split("MATCH (n:")[1].split(")")[0]
            return Result(({**row, "labels": [label]} for row in driver.nodes[label]))
        for spec in importer.RELATIONSHIP_SPECS:
            if query.startswith(f"MATCH (a:{spec.start_label})-[r:{spec.relationship_type}]->(b:{spec.end_label})"):
                return Result(iter(driver.edges[spec.filename]))
        raise AssertionError("Unexpected read query")


class FakeDriver:
    def __init__(self, *, identity=None, initial_counts=(0, 0), fail_run_at=None,
                 ambiguous_commit_at=None, wrong_batch_count=False, race=False,
                 corrupt_verification=False):
        self.database = "hearttrialtwin-full2824"
        self.identity = identity or self.database
        self.initial_counts = initial_counts
        self.fail_run_at = fail_run_at
        self.ambiguous_commit_at = ambiguous_commit_at
        self.wrong_batch_count = wrong_batch_count
        self.race = race
        self.corrupt_verification = corrupt_verification
        self.nodes = {s.label: [] for s in importer.NODE_SPECS}
        self.edges = {s.filename: [] for s in importer.RELATIONSHIP_SPECS}
        self.node_queries = {importer.reference.node_merge_query(s): s.label for s in importer.NODE_SPECS}
        self.edge_queries = {importer.reference.relationship_merge_query(s): s.filename for s in importer.RELATIONSHIP_SPECS}
        self.begun = self.commits = self.rollbacks = 0
        self.schema_queries = []
        self.batch_lengths = []
        self.session_databases = []

    def __enter__(self):
        return self

    def __exit__(self, *error):
        pass

    def verify_connectivity(self):
        pass

    def session(self, *, database, **kwargs):
        self.session_databases.append(database)
        return Session(self, database, **kwargs)

    def execute_query(self, query, *, parameters_, database_, routing_):
        if database_ != self.database or routing_ != "r" or parameters_ != {}:
            raise AssertionError("Every query needs explicit database scope")
        if query == importer.IDENTITY_QUERY:
            return [{"name": self.identity}], None, None
        if query != importer.reference.TOTALS_QUERY:
            raise AssertionError("Unexpected query")
        counts = (sum(map(len, self.nodes.values())), sum(map(len, self.edges.values())))
        if counts == (0, 0):
            counts = self.initial_counts
        if self.race and self.schema_queries:
            counts = (1, 0)
        if self.corrupt_verification and self.commits:
            counts = (counts[0] + 1, counts[1])
        return [{"node_count": counts[0], "relationship_count": counts[1]}], None, None


class FullCohortImporterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = importer.load_full_cohort()
        cls.config = importer.FullConfig("bolt://127.0.0.1:7687", "private-user", "private-password", "hearttrialtwin-full2824")

    def execute(self, driver, **kwargs):
        return importer.execute_full_cohort(
            self.graph, self.config, confirm_database=self.config.database,
            confirm_graph_version=importer.preparation.VERSION,
            driver_factory=lambda *a, **k: driver, **kwargs)

    @contextlib.contextmanager
    def changed(self, obj, key, value):
        original = obj[key]
        obj[key] = value
        try:
            yield
        finally:
            obj[key] = original

    def test_real_payload_counts_and_deterministic_hash(self):
        result = importer.summary(self.graph)
        self.assertEqual(result["network_calls"], 0)
        self.assertEqual(result["total_nodes"], 28777)
        self.assertEqual(result["total_relationships"], 79125)
        self.assertEqual(result["node_counts"]["Trial"], 2824)
        self.assertEqual(result["node_counts"]["PlannedOutcome"], 19740)
        self.assertEqual(len(result["node_counts"]), 6)
        self.assertEqual(len(result["relationship_counts"]), 7)
        self.assertEqual(importer.payload_hash(self.graph), result["payload_sha256"])
        self.assertEqual(importer.NODE_SPECS, importer.pilot.NODE_SPECS)
        self.assertEqual(importer.RELATIONSHIP_SPECS, importer.pilot.RELATIONSHIP_SPECS)

    def test_safe_properties_source_ids_and_provenance_preserved(self):
        for rows in self.graph.nodes.values():
            for row in rows:
                self.assertFalse(set(row["properties"]) & importer.preparation.pilot.PROHIBITED)
        source = self.graph.nodes["SourceDataset"][0]["properties"]
        self.assertEqual(source["graph_version"], importer.preparation.VERSION)
        self.assertEqual(source["snapshot_date"], "2026-09-05")
        self.assertEqual(source["archive_sha256"], importer.preparation.ARCHIVE_SHA256)
        for name in ("relationships_trial_submitted_condition.csv", "relationships_trial_browse_condition.csv"):
            for row in self.graph.relationships[name]:
                self.assertTrue(row["properties"]["source_record_ids"])
        self.assertTrue(all(row["properties"]["evidence_safeguard"] == importer.preparation.pilot.SAFEGUARD for row in self.graph.nodes["PlannedOutcome"]))

    def test_tampered_manifest_rejected_before_source_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "full_cohort_manifest.json").write_text("{}")
            with self.assertRaisesRegex(importer.FullImportError, "SHA-256"):
                importer.load_full_cohort(directory)

    def test_csv_checksum_corruption_is_rejected(self):
        original = importer.preparation.pilot.digest
        def changed(path):
            return "changed" if Path(path).name == "nodes_trial.csv" else original(path)
        with patch.object(importer.preparation.pilot, "digest", side_effect=changed):
            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                importer.load_full_cohort()

    def test_incompatible_headers_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nodes_trial.csv"
            path.write_text("nct_id,wrong_column\nNCT00000001,wrong\n")
            with self.assertRaisesRegex(RuntimeError, "Header mismatch"):
                importer.reference.read_csv(path, importer.NODE_SPECS[0].header)

    def test_duplicate_identifiers_and_bad_endpoints_rejected(self):
        rows = self.graph.nodes["Trial"]
        with self.changed(rows[1], "id", rows[0]["id"]):
            with self.assertRaisesRegex(importer.FullImportError, "duplicate"):
                importer.validate_payload(self.graph)
        row = self.graph.relationships["relationships_trial_planned_outcome.csv"][0]
        with self.changed(row, "start_id", "NCT99999999"):
            with self.assertRaisesRegex(importer.FullImportError, "endpoint"):
                importer.validate_payload(self.graph)

    def test_wrong_graph_and_outcome_provenance_rejected(self):
        props = self.graph.nodes["SourceDataset"][0]["properties"]
        with self.changed(props, "graph_version", importer.pilot.preparation.VERSION):
            with self.assertRaisesRegex(importer.FullImportError, "provenance"):
                importer.validate_payload(self.graph)
        props = self.graph.relationships["relationships_trial_planned_outcome.csv"][0]["properties"]
        with self.changed(props, "source_record_id", "invented"):
            with self.assertRaisesRegex(importer.FullImportError, "linkage"):
                importer.validate_payload(self.graph)

    def test_other_in_memory_value_changes_are_rejected(self):
        props = self.graph.nodes["Trial"][0]["properties"]
        with self.changed(props, "brief_title", "changed"):
            with self.assertRaisesRegex(importer.FullImportError, "Payload changed"):
                importer.validate_payload(self.graph)

    def test_dedicated_configuration_has_no_baseline_or_pilot_fallback(self):
        with self.assertRaisesRegex(importer.FullImportError, "no fallback"):
            importer.load_config(environ={"PILOT_NEO4J_URI": "bolt://localhost:7687", "NEO4J_PASSWORD": "private-password"})

    def test_target_rejects_aura_pilot_defaults_remote_and_embedded_secrets(self):
        cases = (
            ("neo4j+s://57aa5fa3.databases.neo4j.io", "full-cohort"),
            ("bolt+s://%35%37aa5fa3.databases.neo4j.io.", "full-cohort"),
            ("bolt://localhost:7687", "57AA5FA3"),
            ("bolt://127.0.0.1:7687", "neo4j"),
            ("bolt://localhost:7687", "NEO4J"),
            ("bolt://[::1]:7687", "system"),
            ("bolt://localhost:7687", "hearttrialtwin-pilot50"),
            ("bolt://other-host:7687", "full-cohort"),
            ("neo4j://localhost:7687", "full-cohort"),
            ("bolt://user:password@localhost:7687", "full-cohort"),
            ("bolt://localhost:7687?query=bad", "full-cohort"),
            ("bolt://localhost:99999", "full-cohort"),
            ("bolt://localhost:7687", " full-cohort"),
        )
        for uri, database in cases:
            with self.subTest(database=database), self.assertRaises(importer.FullImportError):
                importer.validate_target(importer.FullConfig(uri, "private-user", "private-password", database))

    def test_dedicated_database_on_existing_instance_is_allowed_and_credentials_hidden(self):
        importer.validate_target(self.config)
        self.assertNotIn("private-user", repr(self.config))
        self.assertNotIn("private-password", repr(self.config))
        self.assertNotIn("127.0.0.1", repr(self.config))
        config = importer.load_config(environ={
            "FULL_NEO4J_URI": self.config.uri, "FULL_NEO4J_USERNAME": self.config.username,
            "FULL_NEO4J_PASSWORD": self.config.password, "FULL_NEO4J_DATABASE": self.config.database,
        })
        self.assertEqual(config, self.config)

    def test_explicit_environment_file_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env.full"
            path.write_text("FULL_NEO4J_URI=bolt://localhost:7687\nFULL_NEO4J_DATABASE=hearttrialtwin-full2824\nFULL_NEO4J_USERNAME=test-user\nFULL_NEO4J_PASSWORD=test-only-not-real\n")
            config = importer.load_config(path, environ={})
            self.assertEqual(config.database, self.config.database)

    def test_default_cli_does_not_read_credentials_or_execute(self):
        with patch.object(importer, "load_full_cohort", return_value=self.graph), patch.object(importer, "load_config", side_effect=AssertionError("Credentials accessed")), patch.object(importer, "execute_full_cohort", side_effect=AssertionError("Execution attempted")), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(importer.main([]), 0)
        self.assertEqual(json.loads(output.getvalue())["mode"], "OFFLINE_DRY_RUN")

    def test_bad_batch_sizes_and_confirmations_rejected_before_driver_creation(self):
        factory = Mock(side_effect=AssertionError("Driver created"))
        for value in (0, -1, 1001, True, "250"):
            with self.assertRaises(importer.FullImportError):
                importer.validate_batch_size(value)
        for database, version in (("wrong", importer.preparation.VERSION), (self.config.database, "wrong")):
            with self.assertRaises(importer.FullImportError):
                importer.execute_full_cohort(self.graph, self.config, confirm_database=database, confirm_graph_version=version, driver_factory=factory)
        factory.assert_not_called()

    def test_prohibited_target_is_rejected_before_driver_creation(self):
        factory = Mock(side_effect=AssertionError("Driver created"))
        config = importer.FullConfig("bolt://127.0.0.1:7687", "private-user", "private-password", "neo4j")
        with self.assertRaises(importer.FullImportError):
            importer.execute_full_cohort(self.graph, config, confirm_database="neo4j", confirm_graph_version=importer.preparation.VERSION, driver_factory=factory)
        factory.assert_not_called()

    def test_identity_completed_and_partial_targets_refused_before_constraints(self):
        for driver in (FakeDriver(identity="neo4j"), FakeDriver(initial_counts=(645, 1494)),
                       FakeDriver(initial_counts=(28777, 79125)), FakeDriver(initial_counts=(1, 0))):
            with self.assertRaises(importer.FullImportError):
                self.execute(driver)
            self.assertEqual(driver.schema_queries, [])
            self.assertEqual(driver.begun, 0)

    def test_target_change_after_constraints_refuses_data_writes(self):
        driver = FakeDriver(race=True)
        with self.assertRaisesRegex(importer.FullImportError, "changed during preflight"):
            self.execute(driver)
        self.assertTrue(driver.schema_queries)
        self.assertEqual(driver.begun, 0)

    def test_complete_mocked_import_is_sequential_bounded_and_database_scoped(self):
        driver = FakeDriver()
        result = self.execute(driver, batch_size=137)
        self.assertEqual(result["mode"], "IMPORTED_AND_VERIFIED")
        self.assertEqual(result["total_nodes"], 28777)
        self.assertEqual(result["total_relationships"], 79125)
        self.assertTrue(all(1 <= size <= 137 for size in driver.batch_lengths))
        self.assertEqual(driver.begun, driver.commits)
        self.assertEqual(driver.commits, importer.summary(self.graph, 137)["planned_data_transactions"])
        self.assertTrue(driver.session_databases)
        self.assertEqual(set(driver.session_databases), {self.config.database})
        self.assertEqual(driver.rollbacks, 0)

    def test_failed_batch_count_rolls_back_current_batch(self):
        driver = FakeDriver(wrong_batch_count=True)
        with self.assertRaisesRegex(importer.FullImportError, "Batch count") as caught:
            self.execute(driver)
        self.assertEqual(driver.commits, 0)
        self.assertEqual(driver.rollbacks, 1)
        self.assertEqual(caught.exception.details["confirmed_data_transactions"], 0)

    def test_error_after_commits_stops_without_retry_cleanup_or_secret_leak(self):
        driver = FakeDriver(fail_run_at=3)
        with self.assertRaises(importer.FullImportError) as caught:
            self.execute(driver)
        self.assertEqual(driver.begun, 3)
        self.assertEqual(driver.commits, 2)
        details = caught.exception.details
        self.assertEqual(details["confirmed_data_transactions"], 2)
        self.assertFalse(details["automatic_retry"])
        self.assertFalse(details["automatic_cleanup"])
        self.assertFalse(details["commit_outcome_unknown"])
        rendered = str(caught.exception) + json.dumps(details)
        self.assertNotIn("private-password", rendered)
        self.assertNotIn("private-endpoint", rendered)

    def test_ambiguous_commit_is_reported_and_never_retried(self):
        driver = FakeDriver(ambiguous_commit_at=2)
        with self.assertRaises(importer.FullImportError) as caught:
            self.execute(driver)
        self.assertEqual(driver.begun, 2)
        self.assertEqual(driver.commits, 1)
        self.assertTrue(caught.exception.details["commit_outcome_unknown"])
        self.assertEqual(caught.exception.details["confirmed_data_transactions"], 1)

    def test_post_import_verification_failure_requires_review(self):
        driver = FakeDriver(corrupt_verification=True)
        with self.assertRaisesRegex(importer.FullImportError, "totals mismatch") as caught:
            self.execute(driver)
        self.assertEqual(caught.exception.details["stage"], "verification")
        self.assertFalse(caught.exception.details["automatic_cleanup"])


if __name__ == "__main__":
    unittest.main()
