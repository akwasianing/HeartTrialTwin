"""Tests for the fixed, read-only HeartTrialTwin Neo4j retrieval workflows."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "graphrag" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

spec = importlib.util.spec_from_file_location("graphrag_retrieve", SRC_DIR / "retrieve.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load graphrag/src/retrieve.py")
retrieve = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = retrieve
spec.loader.exec_module(retrieve)
import queries  # noqa: E402


def outcome_rows() -> list[dict]:
    rows = []
    for trial_number in range(5):
        nct_id = f"NCT{trial_number + 1:08d}"
        for outcome_number in range(2):
            source_id = str(1000 + trial_number * 2 + outcome_number)
            rows.append(
                {
                    "nct_id": nct_id,
                    "brief_title": f"Trial {trial_number + 1}",
                    "planned_outcome": {
                        "planned_outcome_id": f"planned_outcome:{source_id}",
                        "source_record_id": source_id,
                        "outcome_type": "primary" if outcome_number == 0 else "secondary",
                        "measure": f"Measure {trial_number + 1}-{outcome_number + 1}",
                        "time_frame": f"Time {outcome_number + 1}",
                        "source_table": "design_outcomes.txt",
                        "dataset_version": retrieve.EXPECTED_DATASET_VERSION,
                    },
                    "source_dataset": {
                        "dataset_version": retrieve.EXPECTED_DATASET_VERSION,
                        "graph_version": retrieve.EXPECTED_GRAPH_VERSION,
                        "snapshot_date": "2026-09-05",
                    },
                    "relationship_path": {
                        "planned_outcome": {"type": "HAS_PLANNED_OUTCOME"},
                        "dataset": {"type": "MEMBER_OF_DATASET"},
                    },
                }
            )
    return rows


class FakeDriver:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.connectivity_verified = False
        self.closed = False

    def verify_connectivity(self) -> None:
        self.connectivity_verified = True

    def close(self) -> None:
        self.closed = True

    def execute_query(self, query, *, parameters_, database_, routing_):
        self.calls.append(
            {
                "query": query,
                "parameters": parameters_,
                "database": database_,
                "routing": routing_,
            }
        )
        if query == queries.DATABASE_INFO_QUERY:
            records = [{"name": retrieve.EXPECTED_DATABASE}]
        elif query == queries.GRAPH_TOTALS_QUERY:
            records = [{"node_count": 26, "relationship_count": 65}]
        elif query == queries.SOURCE_DATASET_QUERY:
            records = [
                {
                    "source_dataset": {
                        "source_dataset_id": retrieve.EXPECTED_DATASET_VERSION,
                        "dataset_version": retrieve.EXPECTED_DATASET_VERSION,
                        "graph_version": retrieve.EXPECTED_GRAPH_VERSION,
                        "snapshot_date": "2026-09-05",
                    }
                }
            ]
        elif query == queries.BASIC_TRIAL_QUERY:
            records = [
                {
                    "trial": {
                        "trial_id": parameters_["nct_id"],
                        "nct_id": parameters_["nct_id"],
                        "brief_title": "Test trial",
                    },
                    "evidence_paths": [
                        {
                            "relationship_type": "HAS_PLANNED_OUTCOME",
                            "relationship_properties": {
                                "source_table": "design_outcomes.txt"
                            },
                            "evidence_labels": ["PlannedOutcome"],
                            "evidence_properties": {
                                "measure": "Registered measure",
                                "source_record_id": "1000",
                            },
                        }
                    ],
                }
            ]
        elif query == queries.SPONSOR_OUTCOME_QUERY:
            records = [
                {
                    **outcome_rows()[0],
                    "condition": {"name": "Heart Failure"},
                    "intervention": {"name": "Spironolactone"},
                    "sponsor": {"name": "Test Sponsor"},
                }
            ]
        elif query == queries.OUTCOME_COMPARISON_QUERY:
            records = outcome_rows()
        else:
            raise AssertionError(f"Unexpected query: {query}")
        return records, object(), list(records[0]) if records else []


class GraphRetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = retrieve.Neo4jConfig(
            uri="neo4j+s://example.invalid",
            username="configured-user",
            password="private-password",
            database=retrieve.EXPECTED_DATABASE,
            env_source="test",
        )
        self.driver = FakeDriver()
        self.retriever = retrieve.Neo4jRetriever(self.config, driver=self.driver)

    def test_all_queries_are_fixed_and_read_only(self) -> None:
        write_pattern = re.compile(
            r"\b(CREATE|DELETE|DETACH|DROP|LOAD\s+CSV|MERGE|REMOVE|SET)\b",
            re.IGNORECASE,
        )
        for query in queries.READ_ONLY_QUERIES:
            with self.subTest(query=query[:30]):
                self.assertIsNone(write_pattern.search(query))
        self.assertIn("$nct_id", queries.BASIC_TRIAL_QUERY)
        self.assertIn("$condition_normalized", queries.SPONSOR_OUTCOME_QUERY)
        self.assertIn("$intervention_normalized", queries.SPONSOR_OUTCOME_QUERY)
        self.assertIn("$dataset_version", queries.OUTCOME_COMPARISON_QUERY)

    def test_connection_verifies_database_graph_and_provenance(self) -> None:
        status = self.retriever.verify_connection()
        self.assertTrue(self.driver.connectivity_verified)
        self.assertTrue(status["connected"])
        self.assertEqual(status["database"], retrieve.EXPECTED_DATABASE)
        self.assertEqual(status["node_count"], 26)
        self.assertEqual(status["relationship_count"], 65)
        self.assertEqual(status["dataset_version"], retrieve.EXPECTED_DATASET_VERSION)
        self.assertTrue(all(call["database"] == retrieve.EXPECTED_DATABASE for call in self.driver.calls))

    def test_basic_retrieval_uses_exact_nct_parameter_and_paths(self) -> None:
        result = self.retriever.question_1("nct00206232")
        self.assertEqual(result["parameters"]["nct_id"], "NCT00206232")
        self.assertEqual(result["row_count"], 1)
        self.assertEqual(
            result["evidence"][0]["evidence_paths"][0]["relationship_type"],
            "HAS_PLANNED_OUTCOME",
        )
        call = self.driver.calls[-1]
        self.assertEqual(call["parameters"]["nct_id"], "NCT00206232")
        self.assertNotIn("NCT00206232", call["query"])

    def test_multihop_retrieval_is_parameterized_and_grounded(self) -> None:
        result = self.retriever.question_2()
        self.assertEqual(result["parameters"]["condition_normalized"], "heart failure")
        self.assertEqual(result["parameters"]["intervention_normalized"], "spironolactone")
        evidence = result["evidence"][0]
        self.assertEqual(evidence["condition"]["name"], "Heart Failure")
        self.assertEqual(evidence["intervention"]["name"], "Spironolactone")
        self.assertEqual(evidence["planned_outcome"]["source_table"], "design_outcomes.txt")
        self.assertEqual(
            result["safeguards"]["planned_outcomes"],
            retrieve.PLANNED_OUTCOME_SAFEGUARD,
        )

    def test_outcome_comparison_is_deterministic_and_nonclinical(self) -> None:
        first = self.retriever.question_3()
        second = self.retriever.question_3()
        self.assertEqual(
            first["deterministic_comparison"], second["deterministic_comparison"]
        )
        comparison = first["deterministic_comparison"]
        self.assertEqual(comparison["trial_count"], 5)
        self.assertEqual(comparison["planned_outcome_count"], 10)
        self.assertEqual(comparison["shared_exact_measure_count"], 0)
        self.assertIn("no clinical inference", comparison["comparison_method"])

    def test_invalid_nct_input_is_rejected_before_query(self) -> None:
        initial_calls = len(self.driver.calls)
        for invalid in ("", "NCT123", "ABC00206232", None):
            with self.subTest(invalid=invalid):
                with self.assertRaises(retrieve.GraphRetrievalError):
                    self.retriever.question_1(invalid)  # type: ignore[arg-type]
        self.assertEqual(len(self.driver.calls), initial_calls)

    def test_configuration_summary_never_exposes_credentials(self) -> None:
        summary = self.config.public_summary()
        serialized = json.dumps(summary)
        self.assertNotIn(self.config.password, serialized)
        self.assertNotIn(self.config.username, serialized)
        self.assertEqual(summary["database"], retrieve.EXPECTED_DATABASE)

    def test_load_config_uses_ignored_env_contract_and_checks_database(self) -> None:
        content = (
            "NEO4J_URI=neo4j+s://example.invalid\n"
            "NEO4J_USERNAME=test-user\n"
            "NEO4J_PASSWORD=test-password\n"
            f"NEO4J_DATABASE={retrieve.EXPECTED_DATABASE}\n"
        )
        names = ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE")
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text(content, encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                config = retrieve.load_config(env_path)
        self.assertEqual(config.database, retrieve.EXPECTED_DATABASE)
        self.assertEqual(config.password, "test-password")
        self.assertNotIn(config.password, json.dumps(config.public_summary()))

    def test_result_files_never_overwrite(self) -> None:
        payload = self.retriever.question_2()
        with tempfile.TemporaryDirectory() as directory:
            first = retrieve.save_results(payload, Path(directory))
            second = retrieve.save_results(payload, Path(directory))
            self.assertNotEqual(first, second)
            self.assertTrue(first.is_file())
            self.assertTrue(second.is_file())
            stored = json.loads(first.read_text(encoding="utf-8"))
            self.assertEqual(stored["evidence"], payload["evidence"])


if __name__ == "__main__":
    unittest.main()
