#!/usr/bin/env python3
"""Run the bounded HeartTrialTwin PlannedOutcome-to-Trial ranking check.

This is an in-graph structural sanity check. Every target
PlannedOutcome--Trial relationship remains present during message passing, so
the results are not held-out retrieval or evidence of generalization.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch
from torch.nn import functional as F

import features
import graph_data
import model


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "gnn_graphrag" / "results" / "trial_ranking_demo_v1.json"
REPORT_SCHEMA_VERSION = "HTT-GNN-TRIAL-RANKING-DEMO-v1"


class RankingError(RuntimeError):
    """Raised when a ranking input or source association is invalid."""


def planned_outcome_trial_associations(
    graph: graph_data.GraphData,
) -> dict[int, graph_data.OriginalRelationship]:
    """Return one verified Trial -> PlannedOutcome relationship per outcome."""

    associations: dict[int, graph_data.OriginalRelationship] = {}
    for relationship in graph.original_relationships:
        if relationship.relationship_type != "HAS_PLANNED_OUTCOME":
            continue
        if relationship.source_label != "Trial" or relationship.target_label != "PlannedOutcome":
            raise RankingError("HAS_PLANNED_OUTCOME has unexpected endpoint labels")
        if relationship.target in associations:
            raise RankingError(
                f"PlannedOutcome has multiple direct trials: {relationship.target_id}"
            )
        if relationship.source_file != "relationships_trial_planned_outcome.csv":
            raise RankingError("PlannedOutcome association has unexpected source file")
        if relationship.properties.get("dataset_version") != graph.extraction_manifest["source"]["dataset_version"]:
            raise RankingError("PlannedOutcome association dataset version mismatch")
        associations[relationship.target] = relationship

    expected_outcomes = {
        node.index for node in graph.nodes if node.label == "PlannedOutcome"
    }
    if set(associations) != expected_outcomes or len(associations) != 10:
        raise RankingError(
            f"Expected one source-grounded association for 10 PlannedOutcome nodes; found {len(associations)}"
        )
    return dict(sorted(associations.items()))


def rank_candidates(
    query_vector: torch.Tensor,
    candidate_matrix: torch.Tensor,
    candidate_ids: Sequence[str],
) -> list[dict[str, Any]]:
    """Rank candidates by cosine similarity with stable ID tie-breaking."""

    if query_vector.ndim != 1:
        raise RankingError("query_vector must be one-dimensional")
    if candidate_matrix.ndim != 2 or candidate_matrix.shape[1] != query_vector.shape[0]:
        raise RankingError("Candidate vectors and query must occupy the same space")
    if candidate_matrix.shape[0] != len(candidate_ids):
        raise RankingError("Candidate ID count does not match candidate matrix")
    if len(set(candidate_ids)) != len(candidate_ids):
        raise RankingError("Candidate IDs must be unique")
    if not torch.isfinite(query_vector).all() or not torch.isfinite(candidate_matrix).all():
        raise RankingError("Ranking vectors must be finite")

    similarities = F.cosine_similarity(
        candidate_matrix,
        query_vector.unsqueeze(0).expand_as(candidate_matrix),
        dim=1,
        eps=1e-12,
    )
    ranked = sorted(
        zip(candidate_ids, similarities.tolist()),
        key=lambda item: (-float(item[1]), item[0]),
    )
    return [
        {"rank": rank, "trial_id": trial_id, "cosine_similarity": float(score)}
        for rank, (trial_id, score) in enumerate(ranked, start=1)
    ]


def summarize_ranks(ranks: Sequence[int]) -> dict[str, Any]:
    if not ranks or any(isinstance(value, bool) or value < 1 for value in ranks):
        raise RankingError("Ranks must be non-empty positive integers")
    hit_count = sum(value == 1 for value in ranks)
    return {
        "query_count": len(ranks),
        "hit_at_1_count": hit_count,
        "hit_at_1": hit_count / len(ranks),
        "mean_reciprocal_rank": sum(1.0 / value for value in ranks) / len(ranks),
    }


def evaluate_representation(
    *,
    representation_name: str,
    representation_matrix: torch.Tensor,
    dimension: int,
    graph: graph_data.GraphData,
    associations: Mapping[int, graph_data.OriginalRelationship],
    trial_indices: Sequence[int],
) -> dict[str, Any]:
    if representation_matrix.shape != (len(graph.nodes), dimension):
        raise RankingError(
            f"Unexpected {representation_name} shape: {tuple(representation_matrix.shape)}"
        )
    candidate_ids = [graph.nodes[index].node_id for index in trial_indices]
    candidate_matrix = representation_matrix[list(trial_indices)]
    query_results: list[dict[str, Any]] = []
    correct_ranks: list[int] = []

    for outcome_index, relationship in associations.items():
        rankings = rank_candidates(
            representation_matrix[outcome_index],
            candidate_matrix,
            candidate_ids,
        )
        correct_trial_id = relationship.source_id
        correct_rank = next(
            item["rank"] for item in rankings if item["trial_id"] == correct_trial_id
        )
        correct_ranks.append(correct_rank)
        query_results.append(
            {
                "query_node_index": outcome_index,
                "query_planned_outcome_id": relationship.target_id,
                "source_record_id": relationship.properties.get("source_record_id"),
                "correct_trial_id": correct_trial_id,
                "correct_trial_node_index": relationship.source,
                "correct_trial_rank": correct_rank,
                "hit_at_1": correct_rank == 1,
                "reciprocal_rank": 1.0 / correct_rank,
                "source_grounding": {
                    "relationship_index": relationship.index,
                    "relationship_type": relationship.relationship_type,
                    "source_file": relationship.source_file,
                    "source_table": relationship.properties.get("source_table"),
                    "dataset_version": relationship.properties.get("dataset_version"),
                },
                "rankings": rankings,
            }
        )

    return {
        "representation_name": representation_name,
        "dimension": dimension,
        "query_node_ids": [item["query_planned_outcome_id"] for item in query_results],
        "candidate_trial_ids": candidate_ids,
        "metrics": summarize_ranks(correct_ranks),
        "queries": query_results,
    }


def run_ranking_experiment(
    graph: graph_data.GraphData,
    feature_bundle: features.FeatureBundle,
    *,
    seed: int = model.DEFAULT_SEED,
) -> dict[str, Any]:
    started = time.perf_counter()
    if feature_bundle.matrix.shape != (len(graph.nodes), model.INPUT_DIMENSION):
        raise RankingError(f"Unexpected feature shape: {feature_bundle.matrix.shape}")

    associations = planned_outcome_trial_associations(graph)
    trial_indices = tuple(node.index for node in graph.nodes if node.label == "Trial")
    if len(trial_indices) != 5:
        raise RankingError(f"Expected five Trial candidates; found {len(trial_indices)}")

    # Confirm each target edge is present in both computational directions.
    semantic_pairs = {
        (edge.source, edge.target, edge.relationship_type)
        for edge in graph.semantic_edges
    }
    for outcome_index, relationship in associations.items():
        forward = (relationship.source, outcome_index, "HAS_PLANNED_OUTCOME")
        reverse = (outcome_index, relationship.source, "HAS_PLANNED_OUTCOME")
        if forward not in semantic_pairs or reverse not in semantic_pairs:
            raise RankingError(
                f"Target relationship is absent from message passing: {relationship.target_id}"
            )

    node_features = torch.from_numpy(
        np.asarray(feature_bundle.matrix, dtype=np.float32, order="C")
    ).to(device="cpu", dtype=torch.float32)
    graph_model = model.build_seeded_model(seed)
    with torch.inference_mode():
        layers = graph_model(node_features, graph.edge_index())

    representations = {
        "layer0_minilm_semantic": evaluate_representation(
            representation_name="Layer 0 — normalized MiniLM semantic embeddings only",
            representation_matrix=layers.layer0[:, : features.SEMANTIC_DIMENSION],
            dimension=features.SEMANTIC_DIMENSION,
            graph=graph,
            associations=associations,
            trial_indices=trial_indices,
        ),
        "layer1_seeded_graphsage": evaluate_representation(
            representation_name="Layer 1 — seeded untrained GraphSAGE",
            representation_matrix=layers.layer1,
            dimension=model.HIDDEN_DIMENSION,
            graph=graph,
            associations=associations,
            trial_indices=trial_indices,
        ),
        "layer2_seeded_graphsage": evaluate_representation(
            representation_name="Layer 2 — seeded untrained GraphSAGE",
            representation_matrix=layers.layer2,
            dimension=model.OUTPUT_DIMENSION,
            graph=graph,
            associations=associations,
            trial_indices=trial_indices,
        ),
    }

    query_ids = next(iter(representations.values()))["query_node_ids"]
    candidate_ids = next(iter(representations.values()))["candidate_trial_ids"]
    if any(result["query_node_ids"] != query_ids for result in representations.values()):
        raise RankingError("Representations did not use identical query nodes")
    if any(result["candidate_trial_ids"] != candidate_ids for result in representations.values()):
        raise RankingError("Representations did not use identical Trial candidates")

    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "experiment_status": "COMPLETED",
        "scientific_label": "In-graph structural ranking sanity check",
        "training_performed": False,
        "hyperparameter_or_seed_tuning_performed": False,
        "retrieval_improvement_claimed": False,
        "target_edge_disclosure": (
            "Every target PlannedOutcome–Trial relationship is present during message passing. "
            "This is an in-graph structural sanity check, not held-out retrieval or generalization."
        ),
        "source": {
            "dataset_version": graph.extraction_manifest["source"]["dataset_version"],
            "graph_version": graph.extraction_manifest["source"]["graph_version"],
            "snapshot_date": graph.extraction_manifest["source"]["snapshot_date"],
            "extraction_version": graph.extraction_manifest["extraction_version"],
            "extraction_manifest_sha256": graph.extraction_manifest_sha256,
            "nodes_csv_sha256": graph.nodes_sha256,
            "relationships_csv_sha256": graph.relationships_sha256,
            "semantic_message_edges_csv_sha256": graph.semantic_edges_sha256,
        },
        "configuration": {
            "seed": seed,
            "device": "cpu",
            "model_dimensions": [390, 128, 64],
            "model_state_sha256_float32_little_endian": model.model_state_sha256(graph_model),
            "node_feature_matrix_sha256_float32_little_endian": feature_bundle.feature_sha256,
            "minilm_model": feature_bundle.model_name,
            "minilm_revision": feature_bundle.model_revision,
            "minilm_snapshot_sha256": feature_bundle.model_snapshot_sha256,
            "semantic_message_edge_count": len(graph.semantic_edges),
            "query_count": len(associations),
            "candidate_trial_count": len(trial_indices),
            "ranking_metric": "cosine similarity within each representation space",
            "tie_breaking": "descending cosine similarity, then ascending NCT ID",
        },
        "fixed_inputs": {
            "query_planned_outcome_ids": query_ids,
            "candidate_trial_ids": candidate_ids,
            "identical_across_representations": True,
        },
        "architecture_integration": (
            "User question -> optional GNN trial candidate ranking -> exact ranked NCT IDs -> "
            "existing parameterized Neo4j evidence retrieval -> grounded answer generation. "
            "The GNN ranker never replaces source evidence or provenance validation."
        ),
        "representations": representations,
        "runtime": {
            "ranking_and_graphsage_seconds": time.perf_counter() - started,
            "feature_encoding_excluded": True,
        },
        "limitations": [
            "The target PlannedOutcome–Trial relationship is present during message passing.",
            "This experiment is transductive and in-graph; it is not held-out retrieval or generalization.",
            "The GraphSAGE weights are seeded and untrained.",
            "The prototype contains five selected trials and ten registered planned outcomes.",
            "Registered planned outcomes are not observed clinical results.",
            "No improvement claim should be made solely from this structural sanity check.",
        ],
    }


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
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    total_started = time.perf_counter()
    graph = graph_data.load_graph_data(args.data_dir)
    feature_started = time.perf_counter()
    encoder = features.OfflineMiniLMEncoder()
    feature_bundle = features.build_feature_matrix(
        graph,
        encoder,
        verify_repeat=True,
        model_snapshot_sha256_value=encoder.snapshot_hash,
    )
    feature_seconds = time.perf_counter() - feature_started
    report = run_ranking_experiment(graph, feature_bundle, seed=args.seed)
    report["runtime"]["feature_loading_and_encoding_seconds"] = feature_seconds
    report["runtime"]["total_execution_seconds_before_serialization"] = (
        time.perf_counter() - total_started
    )
    save_report(report, args.output)
    print(
        json.dumps(
            {
                "status": report["experiment_status"],
                "output": str(args.output),
                "metrics": {
                    key: value["metrics"] for key, value in report["representations"].items()
                },
                "runtime": report["runtime"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
