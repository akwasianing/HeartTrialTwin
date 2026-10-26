"""Tests for the bounded HeartTrialTwin trial-ranking demonstration."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "gnn_graphrag" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import features  # noqa: E402
import graph_data  # noqa: E402
import model  # noqa: E402
import trial_ranking_demo as ranking  # noqa: E402
from test_graphsage_demo import FakeEncoder  # noqa: E402


class TrialRankingDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = graph_data.load_graph_data()
        cls.features = features.build_feature_matrix(
            cls.graph,
            FakeEncoder(),
            verify_repeat=True,
            model_snapshot_sha256_value="test-snapshot",
        )

    def test_rank_candidates_orders_cosine_and_uses_stable_tie_break(self):
        query = torch.tensor([1.0, 0.0])
        candidates = torch.tensor([[0.0, 1.0], [1.0, 0.0], [1.0, 0.0]])
        result = ranking.rank_candidates(query, candidates, ["NCT00000003", "NCT00000002", "NCT00000001"])
        self.assertEqual([item["trial_id"] for item in result], ["NCT00000001", "NCT00000002", "NCT00000003"])
        self.assertEqual([item["rank"] for item in result], [1, 2, 3])

    def test_metric_calculations(self):
        metrics = ranking.summarize_ranks([1, 2, 5])
        self.assertEqual(metrics["query_count"], 3)
        self.assertEqual(metrics["hit_at_1_count"], 1)
        self.assertAlmostEqual(metrics["hit_at_1"], 1 / 3)
        self.assertAlmostEqual(metrics["mean_reciprocal_rank"], (1 + 0.5 + 0.2) / 3)

    def test_source_grounded_associations_cover_all_outcomes_once(self):
        associations = ranking.planned_outcome_trial_associations(self.graph)
        self.assertEqual(len(associations), 10)
        self.assertEqual(
            set(associations),
            {node.index for node in self.graph.nodes if node.label == "PlannedOutcome"},
        )
        for outcome_index, relationship in associations.items():
            self.assertEqual(relationship.relationship_type, "HAS_PLANNED_OUTCOME")
            self.assertEqual(relationship.target, outcome_index)
            self.assertEqual(relationship.source_label, "Trial")
            self.assertEqual(relationship.target_label, "PlannedOutcome")
            self.assertEqual(relationship.source_file, "relationships_trial_planned_outcome.csv")
            self.assertEqual(relationship.properties["source_table"], "design_outcomes.txt")

    def test_experiment_uses_identical_inputs_and_preserves_provenance(self):
        report = ranking.run_ranking_experiment(self.graph, self.features, seed=12345)
        fixed = report["fixed_inputs"]
        self.assertEqual(len(fixed["query_planned_outcome_ids"]), 10)
        self.assertEqual(len(fixed["candidate_trial_ids"]), 5)
        self.assertTrue(fixed["identical_across_representations"])
        for result in report["representations"].values():
            self.assertEqual(result["query_node_ids"], fixed["query_planned_outcome_ids"])
            self.assertEqual(result["candidate_trial_ids"], fixed["candidate_trial_ids"])
            for query in result["queries"]:
                self.assertEqual(query["source_grounding"]["relationship_type"], "HAS_PLANNED_OUTCOME")
                self.assertEqual(query["source_grounding"]["source_table"], "design_outcomes.txt")
                self.assertEqual(
                    query["source_grounding"]["dataset_version"],
                    "HTT-P1-AACT-20260905",
                )
        self.assertEqual(report["source"]["relationships_csv_sha256"], self.graph.relationships_sha256)
        self.assertIn("present during message passing", report["target_edge_disclosure"])

    def test_experiment_is_seed_deterministic_except_runtime(self):
        first = ranking.run_ranking_experiment(self.graph, self.features, seed=12345)
        second = ranking.run_ranking_experiment(self.graph, self.features, seed=12345)
        self.assertEqual(first["configuration"], second["configuration"])
        self.assertEqual(first["fixed_inputs"], second["fixed_inputs"])
        self.assertEqual(first["representations"], second["representations"])

    def test_report_dimensions_metrics_and_create_only_save(self):
        report = ranking.run_ranking_experiment(self.graph, self.features, seed=12345)
        expected_dimensions = {
            "layer0_minilm_semantic": 384,
            "layer1_seeded_graphsage": 128,
            "layer2_seeded_graphsage": 64,
        }
        for key, dimension in expected_dimensions.items():
            result = report["representations"][key]
            self.assertEqual(result["dimension"], dimension)
            self.assertEqual(result["metrics"]["query_count"], 10)
            self.assertEqual(len(result["queries"]), 10)
            self.assertTrue(all(len(query["rankings"]) == 5 for query in result["queries"]))
        self.assertFalse(report["training_performed"])
        self.assertFalse(report["retrieval_improvement_claimed"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ranking.json"
            ranking.save_report(report, path)
            self.assertEqual(json.loads(path.read_text())["report_schema_version"], ranking.REPORT_SCHEMA_VERSION)
            with self.assertRaises(FileExistsError):
                ranking.save_report(report, path)


if __name__ == "__main__":
    unittest.main()
