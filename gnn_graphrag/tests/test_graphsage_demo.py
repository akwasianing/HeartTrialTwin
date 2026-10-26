"""Tests for HeartTrialTwin GraphSAGE features and message passing."""

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
import message_passing_demo  # noqa: E402
import model  # noqa: E402


class FakeEncoder:
    """Deterministic normalized 384-vector encoder for lightweight tests."""

    def encode(self, texts):
        values = np.zeros((len(texts), features.SEMANTIC_DIMENSION), dtype=np.float32)
        for row, text in enumerate(texts):
            first = row % features.SEMANTIC_DIMENSION
            second = (len(text) + row * 7) % features.SEMANTIC_DIMENSION
            values[row, first] += 1.0
            values[row, second] += 0.5
        values /= np.linalg.norm(values, axis=1, keepdims=True)
        return values


class GraphSAGEDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = graph_data.load_graph_data()
        cls.features = features.build_feature_matrix(
            cls.graph,
            FakeEncoder(),
            verify_repeat=True,
            model_snapshot_sha256_value="test-snapshot",
        )

    def test_feature_shape_order_finiteness_and_one_hot(self):
        matrix = self.features.matrix
        self.assertEqual(matrix.shape, (26, 390))
        self.assertTrue(np.isfinite(matrix).all())
        semantic_norms = np.linalg.norm(matrix[:, :384], axis=1)
        self.assertTrue(np.allclose(semantic_norms, 1.0, atol=1e-6))
        one_hot = matrix[:, 384:]
        self.assertTrue(np.all(one_hot.sum(axis=1) == 1.0))
        self.assertEqual(self.features.node_type_order, features.NODE_TYPE_ORDER)
        self.assertEqual(self.features.repeat_max_absolute_difference, 0.0)

    def test_mean_aggregation_and_zero_neighbor_behavior(self):
        node_features = torch.tensor([[1.0, 0.0], [3.0, 2.0], [5.0, 4.0]])
        edge_index = torch.tensor([[0, 1], [2, 2]], dtype=torch.long)
        aggregated = model.mean_aggregate(node_features, edge_index)
        self.assertTrue(torch.equal(aggregated[0], torch.zeros(2)))
        self.assertTrue(torch.equal(aggregated[1], torch.zeros(2)))
        self.assertTrue(torch.allclose(aggregated[2], torch.tensor([2.0, 1.0])))
        empty = model.mean_aggregate(node_features, torch.empty((2, 0), dtype=torch.long))
        self.assertTrue(torch.equal(empty, torch.zeros_like(node_features)))

    def test_seed_reproduces_model_weights_and_outputs(self):
        node_features = torch.from_numpy(self.features.matrix)
        edge_index = self.graph.edge_index()
        first = model.build_seeded_model(12345)
        second = model.build_seeded_model(12345)
        self.assertEqual(model.model_state_sha256(first), model.model_state_sha256(second))
        with torch.inference_mode():
            first_output = first(node_features, edge_index)
            second_output = second(node_features, edge_index)
        self.assertTrue(torch.equal(first_output.layer1, second_output.layer1))
        self.assertTrue(torch.equal(first_output.layer2, second_output.layer2))

    def test_semantic_graph_excludes_provenance_edges(self):
        self.assertEqual(len(self.graph.semantic_edges), 80)
        self.assertFalse(
            graph_data.PROVENANCE_RELATIONSHIP_TYPES
            & {edge.relationship_type for edge in self.graph.semantic_edges}
        )
        self.assertEqual(self.graph.edge_index().shape, (2, 80))

    def test_target_neighborhood_membership(self):
        target = self.graph.node_id_to_index["NCT00206232"]
        one_hop = self.graph.one_hop_indices(target)
        two_hop = self.graph.two_hop_exclusive_indices(target)
        self.assertEqual(len(one_hop), 8)
        self.assertEqual(len(two_hop), 4)
        self.assertEqual(
            {self.graph.nodes[index].node_id for index in two_hop},
            {"NCT00391846", "NCT00574119", "NCT00604006", "NCT01130597"},
        )

    def test_report_schema_dimensions_ablations_and_safeguards(self):
        report = message_passing_demo.run_demo(
            self.graph,
            self.features,
            seed=12345,
        )
        self.assertEqual(report["demonstration_status"], "COMPLETED")
        self.assertFalse(report["training_performed"])
        self.assertFalse(report["retrieval_improvement_claimed"])
        self.assertEqual(report["features"]["shape"], [26, 390])
        self.assertEqual(report["model"]["dimensions"], [390, 128, 64])
        self.assertEqual(report["representations"]["full_neighbors"]["layer0"]["dimension"], 390)
        self.assertEqual(report["representations"]["full_neighbors"]["layer1"]["dimension"], 128)
        self.assertEqual(report["representations"]["full_neighbors"]["layer2"]["dimension"], 64)
        self.assertEqual(
            set(report["neighbor_type_ablations"]),
            {"sponsor", "intervention", "condition", "planned_outcome"},
        )
        self.assertTrue(any("not causal" in item for item in report["limitations"]))
        self.assertTrue(any("not observed clinical results" in item for item in report["limitations"]))

    def test_saved_report_is_valid_json_and_never_overwritten(self):
        report = message_passing_demo.run_demo(self.graph, self.features, seed=12345)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            message_passing_demo.save_report(report, path)
            stored = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(stored["report_schema_version"], "HTT-GNN-MESSAGE-PASSING-DEMO-v1")
            with self.assertRaises(FileExistsError):
                message_passing_demo.save_report(report, path)


if __name__ == "__main__":
    unittest.main()
