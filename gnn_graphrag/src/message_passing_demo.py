#!/usr/bin/env python3
"""Run the seeded, untrained HeartTrialTwin GraphSAGE demonstration."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch

import features
import graph_data
import model


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "gnn_graphrag" / "results" / "message_passing_demo_v1.json"
TARGET_NCT_ID = "NCT00206232"

ABLATION_RELATIONSHIPS = {
    "sponsor": ("LEAD_SPONSORED_BY",),
    "intervention": ("HAS_INTERVENTION",),
    "condition": ("HAS_SUBMITTED_CONDITION", "HAS_BROWSE_CONDITION"),
    "planned_outcome": ("HAS_PLANNED_OUTCOME",),
}


class DemoError(RuntimeError):
    """Raised when the message-passing demonstration cannot be validated."""


def _node_summary(graph: graph_data.GraphData, indices: Sequence[int]) -> list[dict[str, Any]]:
    return [
        {
            "node_index": index,
            "node_id": graph.nodes[index].node_id,
            "node_label": graph.nodes[index].label,
        }
        for index in indices
    ]


def _layer_hashes(representations: model.LayerRepresentations, target_index: int) -> dict[str, Any]:
    return {
        "layer0": {
            "dimension": int(representations.layer0.shape[1]),
            "target_representation_sha256": model.tensor_sha256(representations.layer0[target_index]),
        },
        "layer1": {
            "dimension": int(representations.layer1.shape[1]),
            "target_representation_sha256": model.tensor_sha256(representations.layer1[target_index]),
        },
        "layer2": {
            "dimension": int(representations.layer2.shape[1]),
            "target_representation_sha256": model.tensor_sha256(representations.layer2[target_index]),
        },
    }


def run_demo(
    graph: graph_data.GraphData,
    feature_bundle: features.FeatureBundle,
    *,
    seed: int = model.DEFAULT_SEED,
    target_nct_id: str = TARGET_NCT_ID,
) -> dict[str, Any]:
    started = time.perf_counter()
    if feature_bundle.matrix.shape != (len(graph.nodes), model.INPUT_DIMENSION):
        raise DemoError(f"Unexpected feature shape: {feature_bundle.matrix.shape}")
    try:
        target_index = graph.node_id_to_index[target_nct_id]
    except KeyError as exc:
        raise DemoError(f"Target trial is absent: {target_nct_id}") from exc
    if graph.nodes[target_index].label != "Trial":
        raise DemoError(f"Target node is not a Trial: {target_nct_id}")

    graph_model = model.build_seeded_model(seed)
    node_features = torch.from_numpy(
        np.asarray(feature_bundle.matrix, dtype=np.float32, order="C")
    ).to(device="cpu", dtype=torch.float32)
    semantic_edge_index = graph.edge_index()
    empty_edge_index = torch.empty((2, 0), dtype=torch.long)

    with torch.inference_mode():
        full = graph_model(node_features, semantic_edge_index)
        no_neighbors = graph_model(node_features, empty_edge_index)

    neighbor_diagnostics = {
        "comparison_rule": (
            "Each comparison uses the same seeded model weights and compares full-neighbor "
            "versus zero-neighbor representations only within the same layer/dimension."
        ),
        "layer0": model.within_space_diagnostics(
            full.layer0[target_index], no_neighbors.layer0[target_index]
        ),
        "layer1": model.within_space_diagnostics(
            full.layer1[target_index], no_neighbors.layer1[target_index]
        ),
        "layer2": model.within_space_diagnostics(
            full.layer2[target_index], no_neighbors.layer2[target_index]
        ),
    }

    ablations: dict[str, Any] = {}
    for name, relationship_types in ABLATION_RELATIONSHIPS.items():
        ablated_edge_index = graph.edge_index(relationship_types)
        with torch.inference_mode():
            ablated = graph_model(node_features, ablated_edge_index)
        ablations[name] = {
            "excluded_relationship_types": list(relationship_types),
            "removed_directed_message_edges": int(
                semantic_edge_index.shape[1] - ablated_edge_index.shape[1]
            ),
            "layer1_full_vs_ablated": model.within_space_diagnostics(
                full.layer1[target_index], ablated.layer1[target_index]
            ),
            "layer2_full_vs_ablated": model.within_space_diagnostics(
                full.layer2[target_index], ablated.layer2[target_index]
            ),
        }

    one_hop = graph.one_hop_indices(target_index)
    two_hop = graph.two_hop_exclusive_indices(target_index)
    runtime = time.perf_counter() - started

    report = {
        "report_schema_version": "HTT-GNN-MESSAGE-PASSING-DEMO-v1",
        "demonstration_status": "COMPLETED",
        "scientific_label": "Seeded, untrained GraphSAGE message-passing representations",
        "training_performed": False,
        "retrieval_improvement_claimed": False,
        "target": {
            "nct_id": target_nct_id,
            "node_index": target_index,
            "node_label": graph.nodes[target_index].label,
        },
        "source": {
            "dataset_version": graph.extraction_manifest["source"]["dataset_version"],
            "graph_version": graph.extraction_manifest["source"]["graph_version"],
            "snapshot_date": graph.extraction_manifest["source"]["snapshot_date"],
            "extraction_version": graph.extraction_manifest["extraction_version"],
            "extraction_manifest_sha256": graph.extraction_manifest_sha256,
            "nodes_csv_sha256": graph.nodes_sha256,
            "semantic_message_edges_csv_sha256": graph.semantic_edges_sha256,
        },
        "features": {
            "shape": list(feature_bundle.matrix.shape),
            "dtype": str(feature_bundle.matrix.dtype),
            "feature_order": {
                "semantic_embedding": [0, features.SEMANTIC_DIMENSION - 1],
                "node_type_one_hot": [features.SEMANTIC_DIMENSION, features.FEATURE_DIMENSION - 1],
                "node_type_order": list(feature_bundle.node_type_order),
            },
            "semantic_vectors_normalized": True,
            "all_values_finite": bool(np.isfinite(feature_bundle.matrix).all()),
            "matrix_sha256_float32_little_endian": feature_bundle.feature_sha256,
            "semantic_matrix_sha256_float32_little_endian": feature_bundle.semantic_sha256,
            "repeat_sha256": feature_bundle.repeat_sha256,
            "repeat_max_absolute_difference": feature_bundle.repeat_max_absolute_difference,
            "offline_local_files_only": True,
            "model_name": feature_bundle.model_name,
            "model_revision": feature_bundle.model_revision,
            "model_snapshot_sha256": feature_bundle.model_snapshot_sha256,
        },
        "graph": {
            "node_count": len(graph.nodes),
            "semantic_directed_message_edge_count": len(graph.semantic_edges),
            "provenance_relationship_types_excluded_from_message_passing": sorted(
                graph_data.PROVENANCE_RELATIONSHIP_TYPES
            ),
            "provenance_preserved_in_original_extraction": True,
        },
        "model": {
            "architecture": "Two-layer mean-aggregation GraphSAGE",
            "dimensions": [
                model.INPUT_DIMENSION,
                model.HIDDEN_DIMENSION,
                model.OUTPUT_DIMENSION,
            ],
            "activation": "ReLU after each layer",
            "seed": seed,
            "device": "cpu",
            "evaluation_mode": not graph_model.training,
            "trained": False,
            "state_sha256_float32_little_endian": model.model_state_sha256(graph_model),
        },
        "neighborhood": {
            "definition": (
                "Exclusive hop sets in the 80-edge semantic computational graph; "
                "provenance edges are retained in source artifacts but not traversed here."
            ),
            "one_hop_count": len(one_hop),
            "one_hop_nodes": _node_summary(graph, one_hop),
            "two_hop_exclusive_count": len(two_hop),
            "two_hop_exclusive_nodes": _node_summary(graph, two_hop),
        },
        "representations": {
            "full_neighbors": _layer_hashes(full, target_index),
            "zero_neighbors": _layer_hashes(no_neighbors, target_index),
        },
        "neighbor_influence": neighbor_diagnostics,
        "neighbor_type_ablations": ablations,
        "runtime": {
            "message_passing_and_diagnostics_seconds": runtime,
            "feature_encoding_excluded": True,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "torch": importlib.metadata.version("torch"),
            "numpy": importlib.metadata.version("numpy"),
            "sentence_transformers": importlib.metadata.version("sentence-transformers"),
        },
        "limitations": [
            "The representations are seeded and untrained; they are not learned retrieval embeddings.",
            "No model training, retrieval benchmark, or claim of improved retrieval performance was performed.",
            "The graph contains five illustrative trials, not the full 2,824-trial cohort.",
            "Message-flow ablations are architectural observations, not causal explanations.",
            "Registered planned outcomes are not observed clinical results.",
            "September 2026 snapshot values may include later amendments and are not asserted to be original-registration values.",
            "Provenance relationships are excluded only from computational message passing and remain preserved in source evidence.",
        ],
    }
    return report


def save_report(report: Mapping[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    with output_path.open("x", encoding="utf-8") as handle:
        handle.write(payload)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=graph_data.DEFAULT_DATA_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=model.DEFAULT_SEED)
    parser.add_argument("--target-nct-id", default=TARGET_NCT_ID)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    graph = graph_data.load_graph_data(args.data_dir)
    encoder = features.OfflineMiniLMEncoder()
    feature_bundle = features.build_feature_matrix(
        graph,
        encoder,
        verify_repeat=True,
        model_snapshot_sha256_value=encoder.snapshot_hash,
    )
    report = run_demo(
        graph,
        feature_bundle,
        seed=args.seed,
        target_nct_id=args.target_nct_id,
    )
    save_report(report, args.output)
    print(
        json.dumps(
            {
                "status": report["demonstration_status"],
                "output": str(args.output),
                "feature_shape": report["features"]["shape"],
                "one_hop_count": report["neighborhood"]["one_hop_count"],
                "two_hop_exclusive_count": report["neighborhood"]["two_hop_exclusive_count"],
                "runtime_seconds": report["runtime"]["message_passing_and_diagnostics_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
