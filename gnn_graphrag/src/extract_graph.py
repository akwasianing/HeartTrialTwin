#!/usr/bin/env python3
"""Deterministically extract the verified HeartTrialTwin graph for GNN use.

This module reads only the checked-in Knowledge Graph import artifacts. It
does not connect to Neo4j, construct embeddings, train a model, or alter the
source graph.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = REPO_ROOT / "artifacts" / "knowledge_graph"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "gnn_graphrag" / "data"

EXTRACTION_VERSION = "HTT-GNN-GRAPH-EXTRACT-v1"
EXPECTED_DATASET_VERSION = "HTT-P1-AACT-20260905"
EXPECTED_GRAPH_VERSION = "HTT-KG-AACT-20260905-v1"
EXPECTED_SNAPSHOT_DATE = "2026-09-05"
EXPECTED_NODE_COUNT = 26
EXPECTED_RELATIONSHIP_COUNT = 65
EXPECTED_FULL_MESSAGE_EDGE_COUNT = 130
EXPECTED_SEMANTIC_MESSAGE_EDGE_COUNT = 80

NODE_LABEL_ORDER = (
    "Trial",
    "ConditionTerm",
    "Intervention",
    "Sponsor",
    "PlannedOutcome",
    "SourceDataset",
)

RELATIONSHIP_TYPE_ORDER = (
    "HAS_SUBMITTED_CONDITION",
    "HAS_BROWSE_CONDITION",
    "HAS_INTERVENTION",
    "LEAD_SPONSORED_BY",
    "HAS_PLANNED_OUTCOME",
    "MEMBER_OF_DATASET",
    "SOURCED_FROM",
)

PROVENANCE_RELATIONSHIP_TYPES = frozenset({"MEMBER_OF_DATASET", "SOURCED_FROM"})
PLANNED_OUTCOME_SAFEGUARD = "Registered planned outcome — not a clinical result."

FEATURE_FIELDS: dict[str, tuple[str, ...]] = {
    "Trial": ("nct_id", "brief_title", "study_type", "phase"),
    "ConditionTerm": ("name", "source_kind"),
    "Intervention": ("name", "intervention_type"),
    "Sponsor": ("name", "agency_class"),
    "PlannedOutcome": ("outcome_type", "measure", "time_frame"),
    "SourceDataset": ("dataset_version", "graph_version", "snapshot_date"),
}

PROHIBITED_FEATURE_FIELDS = (
    "overall_status",
    "status",
    "termination_reason",
    "why_stopped",
    "discontinued",
    "prediction",
    "prediction_label",
    "prediction_score",
    "observed_result",
    "results",
    "completion_date",
    "enrollment",
    "start_date",
    "study_first_submitted_date",
    "submission_year",
    "temporal_group",
)


@dataclass(frozen=True)
class NodeSpec:
    filename: str
    label: str
    id_header: str
    header: tuple[str, ...]


@dataclass(frozen=True)
class RelationshipSpec:
    filename: str
    relationship_type: str
    source_label: str
    target_label: str
    source_header: str
    target_header: str
    header: tuple[str, ...]


NODE_SPECS = (
    NodeSpec(
        "nodes_trial.csv",
        "Trial",
        "trial_id:ID(Trial)",
        (
            "trial_id:ID(Trial)",
            "nct_id",
            "brief_title",
            "study_type",
            "phase",
            "enrollment",
            "start_date",
            "completion_date",
            "study_first_submitted_date",
            "submission_year:int",
            "temporal_group",
            "dataset_version",
            ":LABEL",
        ),
    ),
    NodeSpec(
        "nodes_condition_term.csv",
        "ConditionTerm",
        "condition_id:ID(ConditionTerm)",
        (
            "condition_id:ID(ConditionTerm)",
            "name",
            "normalized_name",
            "source_kind",
            "source_table",
            "dataset_version",
            ":LABEL",
        ),
    ),
    NodeSpec(
        "nodes_intervention.csv",
        "Intervention",
        "intervention_id:ID(Intervention)",
        (
            "intervention_id:ID(Intervention)",
            "name",
            "normalized_name",
            "intervention_type",
            "normalized_intervention_type",
            "source_table",
            "dataset_version",
            ":LABEL",
        ),
    ),
    NodeSpec(
        "nodes_sponsor.csv",
        "Sponsor",
        "sponsor_id:ID(Sponsor)",
        (
            "sponsor_id:ID(Sponsor)",
            "name",
            "normalized_name",
            "agency_class",
            "source_table",
            "dataset_version",
            ":LABEL",
        ),
    ),
    NodeSpec(
        "nodes_planned_outcome.csv",
        "PlannedOutcome",
        "planned_outcome_id:ID(PlannedOutcome)",
        (
            "planned_outcome_id:ID(PlannedOutcome)",
            "source_record_id",
            "nct_id",
            "outcome_type",
            "measure",
            "time_frame",
            "population",
            "description",
            "source_table",
            "dataset_version",
            ":LABEL",
        ),
    ),
    NodeSpec(
        "nodes_source_dataset.csv",
        "SourceDataset",
        "source_dataset_id:ID(SourceDataset)",
        (
            "source_dataset_id:ID(SourceDataset)",
            "dataset_version",
            "graph_version",
            "snapshot_date",
            "snapshot_file",
            "snapshot_url",
            "archive_size_bytes:long",
            "archive_etag",
            "archive_last_modified",
            "pinned_manifest_sha256",
            ":LABEL",
        ),
    ),
)

RELATIONSHIP_SPECS = (
    RelationshipSpec(
        "relationships_trial_submitted_condition.csv",
        "HAS_SUBMITTED_CONDITION",
        "Trial",
        "ConditionTerm",
        ":START_ID(Trial)",
        ":END_ID(ConditionTerm)",
        (
            ":START_ID(Trial)",
            ":END_ID(ConditionTerm)",
            "source_table",
            "source_record_id",
            "source_record_id_status",
            "dataset_version",
            ":TYPE",
        ),
    ),
    RelationshipSpec(
        "relationships_trial_browse_condition.csv",
        "HAS_BROWSE_CONDITION",
        "Trial",
        "ConditionTerm",
        ":START_ID(Trial)",
        ":END_ID(ConditionTerm)",
        (
            ":START_ID(Trial)",
            ":END_ID(ConditionTerm)",
            "source_table",
            "source_record_id",
            "source_record_id_status",
            "dataset_version",
            ":TYPE",
        ),
    ),
    RelationshipSpec(
        "relationships_trial_intervention.csv",
        "HAS_INTERVENTION",
        "Trial",
        "Intervention",
        ":START_ID(Trial)",
        ":END_ID(Intervention)",
        (
            ":START_ID(Trial)",
            ":END_ID(Intervention)",
            "source_table",
            "source_record_ids",
            "dataset_version",
            ":TYPE",
        ),
    ),
    RelationshipSpec(
        "relationships_trial_sponsor.csv",
        "LEAD_SPONSORED_BY",
        "Trial",
        "Sponsor",
        ":START_ID(Trial)",
        ":END_ID(Sponsor)",
        (
            ":START_ID(Trial)",
            ":END_ID(Sponsor)",
            "source_table",
            "source_record_ids",
            "dataset_version",
            ":TYPE",
        ),
    ),
    RelationshipSpec(
        "relationships_trial_planned_outcome.csv",
        "HAS_PLANNED_OUTCOME",
        "Trial",
        "PlannedOutcome",
        ":START_ID(Trial)",
        ":END_ID(PlannedOutcome)",
        (
            ":START_ID(Trial)",
            ":END_ID(PlannedOutcome)",
            "source_table",
            "source_record_id",
            "dataset_version",
            ":TYPE",
        ),
    ),
    RelationshipSpec(
        "relationships_trial_source_dataset.csv",
        "MEMBER_OF_DATASET",
        "Trial",
        "SourceDataset",
        ":START_ID(Trial)",
        ":END_ID(SourceDataset)",
        (":START_ID(Trial)", ":END_ID(SourceDataset)", "dataset_version", ":TYPE"),
    ),
    RelationshipSpec(
        "relationships_condition_source_dataset.csv",
        "SOURCED_FROM",
        "ConditionTerm",
        "SourceDataset",
        ":START_ID(ConditionTerm)",
        ":END_ID(SourceDataset)",
        (":START_ID(ConditionTerm)", ":END_ID(SourceDataset)", "dataset_version", ":TYPE"),
    ),
    RelationshipSpec(
        "relationships_intervention_source_dataset.csv",
        "SOURCED_FROM",
        "Intervention",
        "SourceDataset",
        ":START_ID(Intervention)",
        ":END_ID(SourceDataset)",
        (":START_ID(Intervention)", ":END_ID(SourceDataset)", "dataset_version", ":TYPE"),
    ),
    RelationshipSpec(
        "relationships_sponsor_source_dataset.csv",
        "SOURCED_FROM",
        "Sponsor",
        "SourceDataset",
        ":START_ID(Sponsor)",
        ":END_ID(SourceDataset)",
        (":START_ID(Sponsor)", ":END_ID(SourceDataset)", "dataset_version", ":TYPE"),
    ),
    RelationshipSpec(
        "relationships_outcome_source_dataset.csv",
        "SOURCED_FROM",
        "PlannedOutcome",
        "SourceDataset",
        ":START_ID(PlannedOutcome)",
        ":END_ID(SourceDataset)",
        (":START_ID(PlannedOutcome)", ":END_ID(SourceDataset)", "dataset_version", ":TYPE"),
    ),
)


class ExtractionError(RuntimeError):
    """Raised when source integrity or graph structure does not match the pin."""


@dataclass(frozen=True)
class SourceNode:
    node_id: str
    label: str
    source_file: str
    properties: dict[str, str]


@dataclass(frozen=True)
class SourceRelationship:
    source_id: str
    target_id: str
    relationship_type: str
    source_label: str
    target_label: str
    source_file: str
    properties: dict[str, str]


@dataclass(frozen=True)
class VerifiedGraph:
    source_manifest: dict[str, Any]
    source_manifest_sha256: str
    source_file_hashes: dict[str, str]
    nodes: tuple[SourceNode, ...]
    relationships: tuple[SourceRelationship, ...]


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv(path: Path, expected_header: Sequence[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise ExtractionError(f"Required source file is missing: {path.name}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != tuple(expected_header):
            raise ExtractionError(
                f"Unexpected header for {path.name}: {reader.fieldnames}; expected {list(expected_header)}"
            )
        return [dict(row) for row in reader]


def _clean(value: str | None) -> str:
    return " ".join((value or "").split())


def canonical_feature_text(label: str, properties: Mapping[str, str]) -> str:
    """Construct source-bound text from the approved per-label fields only."""

    if label not in FEATURE_FIELDS:
        raise ExtractionError(f"No feature-field policy for label {label}")

    labels: dict[str, tuple[tuple[str, str], ...]] = {
        "Trial": (
            ("NCT ID", "nct_id"),
            ("Title", "brief_title"),
            ("Study type", "study_type"),
            ("Phase", "phase"),
        ),
        "ConditionTerm": (
            ("Condition name", "name"),
            ("Condition source classification", "source_kind"),
        ),
        "Intervention": (
            ("Intervention name", "name"),
            ("Intervention type", "intervention_type"),
        ),
        "Sponsor": (
            ("Sponsor name", "name"),
            ("Agency class", "agency_class"),
        ),
        "PlannedOutcome": (
            ("Outcome type", "outcome_type"),
            ("Registered measure", "measure"),
            ("Time frame", "time_frame"),
        ),
        "SourceDataset": (
            ("Dataset version", "dataset_version"),
            ("Graph version", "graph_version"),
            ("Snapshot date", "snapshot_date"),
        ),
    }
    parts = [f"Node type: {label}"]
    for display_name, field in labels[label]:
        value = _clean(properties.get(field))
        if value:
            parts.append(f"{display_name}: {value}")
    if label == "PlannedOutcome":
        parts.append(PLANNED_OUTCOME_SAFEGUARD)
    return " | ".join(parts)


def load_verified_graph(source_dir: Path = DEFAULT_SOURCE_DIR) -> VerifiedGraph:
    manifest_path = source_dir / "graph_import_manifest.json"
    if not manifest_path.is_file():
        raise ExtractionError("graph_import_manifest.json is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("authoritative_dataset_version") != EXPECTED_DATASET_VERSION:
        raise ExtractionError("Unexpected authoritative dataset version")
    if manifest.get("graph_version") != EXPECTED_GRAPH_VERSION:
        raise ExtractionError("Unexpected graph version")
    if manifest.get("archive", {}).get("snapshot_date") != EXPECTED_SNAPSHOT_DATE:
        raise ExtractionError("Unexpected snapshot date")
    if manifest.get("total_nodes") != EXPECTED_NODE_COUNT:
        raise ExtractionError("Unexpected manifest node total")
    if manifest.get("total_relationships") != EXPECTED_RELATIONSHIP_COUNT:
        raise ExtractionError("Unexpected manifest relationship total")

    expected_hashes = manifest.get("files_sha256", {})
    source_hashes: dict[str, str] = {}
    nodes: list[SourceNode] = []
    node_ids: set[str] = set()

    for spec in NODE_SPECS:
        path = source_dir / spec.filename
        actual_hash = sha256_path(path) if path.is_file() else ""
        if expected_hashes.get(spec.filename) != actual_hash:
            raise ExtractionError(f"Source hash mismatch: {spec.filename}")
        source_hashes[spec.filename] = actual_hash
        rows = _read_csv(path, spec.header)
        for row in rows:
            node_id = _clean(row.get(spec.id_header))
            if not node_id:
                raise ExtractionError(f"Missing node identifier in {spec.filename}")
            if node_id in node_ids:
                raise ExtractionError(f"Duplicate node identifier: {node_id}")
            if row.get(":LABEL") != spec.label:
                raise ExtractionError(f"Label mismatch for {node_id}")
            if row.get("dataset_version") != EXPECTED_DATASET_VERSION:
                raise ExtractionError(f"Dataset version mismatch for node {node_id}")
            node_ids.add(node_id)
            nodes.append(SourceNode(node_id, spec.label, spec.filename, row))

    label_counts = Counter(node.label for node in nodes)
    if dict(label_counts) != manifest.get("node_counts"):
        raise ExtractionError(
            f"Node counts do not match manifest: {dict(label_counts)} != {manifest.get('node_counts')}"
        )
    if len(nodes) != EXPECTED_NODE_COUNT:
        raise ExtractionError(f"Expected {EXPECTED_NODE_COUNT} nodes; found {len(nodes)}")

    node_label_by_id = {node.node_id: node.label for node in nodes}
    relationships: list[SourceRelationship] = []
    triples: set[tuple[str, str, str]] = set()
    for spec in RELATIONSHIP_SPECS:
        path = source_dir / spec.filename
        actual_hash = sha256_path(path) if path.is_file() else ""
        if expected_hashes.get(spec.filename) != actual_hash:
            raise ExtractionError(f"Source hash mismatch: {spec.filename}")
        source_hashes[spec.filename] = actual_hash
        rows = _read_csv(path, spec.header)
        for row in rows:
            source_id = _clean(row.get(spec.source_header))
            target_id = _clean(row.get(spec.target_header))
            relation_type = _clean(row.get(":TYPE"))
            if relation_type != spec.relationship_type:
                raise ExtractionError(f"Relationship type mismatch in {spec.filename}")
            if source_id not in node_label_by_id or target_id not in node_label_by_id:
                raise ExtractionError(
                    f"Invalid relationship endpoint in {spec.filename}: {source_id} -> {target_id}"
                )
            if node_label_by_id[source_id] != spec.source_label:
                raise ExtractionError(f"Source label mismatch for {source_id} in {spec.filename}")
            if node_label_by_id[target_id] != spec.target_label:
                raise ExtractionError(f"Target label mismatch for {target_id} in {spec.filename}")
            if row.get("dataset_version") != EXPECTED_DATASET_VERSION:
                raise ExtractionError(f"Dataset version mismatch in {spec.filename}")
            triple = (source_id, relation_type, target_id)
            if triple in triples:
                raise ExtractionError(f"Duplicate relationship triple: {triple}")
            triples.add(triple)
            properties = {
                key: value
                for key, value in row.items()
                if key not in {spec.source_header, spec.target_header, ":TYPE"}
            }
            relationships.append(
                SourceRelationship(
                    source_id,
                    target_id,
                    relation_type,
                    spec.source_label,
                    spec.target_label,
                    spec.filename,
                    properties,
                )
            )

    relationship_counts = Counter(item.relationship_type for item in relationships)
    if dict(relationship_counts) != manifest.get("relationship_counts"):
        raise ExtractionError(
            "Relationship counts do not match manifest: "
            f"{dict(relationship_counts)} != {manifest.get('relationship_counts')}"
        )
    if len(relationships) != EXPECTED_RELATIONSHIP_COUNT:
        raise ExtractionError(
            f"Expected {EXPECTED_RELATIONSHIP_COUNT} relationships; found {len(relationships)}"
        )

    source_nodes = [node for node in nodes if node.label == "SourceDataset"]
    if len(source_nodes) != 1:
        raise ExtractionError("Expected exactly one SourceDataset node")
    source_properties = source_nodes[0].properties
    if source_properties.get("graph_version") != EXPECTED_GRAPH_VERSION:
        raise ExtractionError("SourceDataset graph version mismatch")
    if source_properties.get("snapshot_date") != EXPECTED_SNAPSHOT_DATE:
        raise ExtractionError("SourceDataset snapshot date mismatch")

    label_rank = {label: index for index, label in enumerate(NODE_LABEL_ORDER)}
    relation_rank = {
        relationship_type: index
        for index, relationship_type in enumerate(RELATIONSHIP_TYPE_ORDER)
    }
    ordered_nodes = tuple(sorted(nodes, key=lambda node: (label_rank[node.label], node.node_id)))
    node_index = {node.node_id: index for index, node in enumerate(ordered_nodes)}
    ordered_relationships = tuple(
        sorted(
            relationships,
            key=lambda item: (
                relation_rank[item.relationship_type],
                node_index[item.source_id],
                node_index[item.target_id],
                item.source_file,
                json.dumps(item.properties, sort_keys=True, ensure_ascii=False),
            ),
        )
    )

    # The original source graph must be connected when direction is ignored.
    adjacency: dict[str, set[str]] = defaultdict(set)
    for relationship in ordered_relationships:
        adjacency[relationship.source_id].add(relationship.target_id)
        adjacency[relationship.target_id].add(relationship.source_id)
    seen = {ordered_nodes[0].node_id}
    queue = deque(seen)
    while queue:
        current = queue.popleft()
        for neighbor in adjacency[current]:
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    if len(seen) != len(ordered_nodes):
        raise ExtractionError("Source graph is not connected")

    return VerifiedGraph(
        source_manifest=manifest,
        source_manifest_sha256=sha256_path(manifest_path),
        source_file_hashes=dict(sorted(source_hashes.items())),
        nodes=ordered_nodes,
        relationships=ordered_relationships,
    )


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _node_rows(graph: VerifiedGraph) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, node in enumerate(graph.nodes):
        feature_text = canonical_feature_text(node.label, node.properties)
        rows.append(
            {
                "node_index": index,
                "node_id": node.node_id,
                "node_label": node.label,
                "source_file": node.source_file,
                "dataset_version": EXPECTED_DATASET_VERSION,
                "feature_text": feature_text,
                "feature_text_sha256": hashlib.sha256(feature_text.encode("utf-8")).hexdigest(),
            }
        )
    return rows


def _relationship_rows(graph: VerifiedGraph) -> list[dict[str, Any]]:
    node_index = {node.node_id: index for index, node in enumerate(graph.nodes)}
    rows: list[dict[str, Any]] = []
    for index, relationship in enumerate(graph.relationships):
        rows.append(
            {
                "relationship_index": index,
                "source_node_index": node_index[relationship.source_id],
                "source_node_id": relationship.source_id,
                "source_node_label": relationship.source_label,
                "target_node_index": node_index[relationship.target_id],
                "target_node_id": relationship.target_id,
                "target_node_label": relationship.target_label,
                "relationship_type": relationship.relationship_type,
                "source_file": relationship.source_file,
                "properties_json": json.dumps(
                    relationship.properties,
                    sort_keys=True,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            }
        )
    return rows


def _message_rows(
    relationship_rows: Sequence[Mapping[str, Any]],
    *,
    excluded_types: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relationship in relationship_rows:
        if relationship["relationship_type"] in excluded_types:
            continue
        forward = {
            "message_edge_index": len(rows),
            "source_node_index": relationship["source_node_index"],
            "source_node_label": relationship["source_node_label"],
            "target_node_index": relationship["target_node_index"],
            "target_node_label": relationship["target_node_label"],
            "relationship_type": relationship["relationship_type"],
            "message_direction": "forward",
            "original_relationship_index": relationship["relationship_index"],
        }
        rows.append(forward)
        rows.append(
            {
                "message_edge_index": len(rows),
                "source_node_index": relationship["target_node_index"],
                "source_node_label": relationship["target_node_label"],
                "target_node_index": relationship["source_node_index"],
                "target_node_label": relationship["source_node_label"],
                "relationship_type": relationship["relationship_type"],
                "message_direction": "reverse",
                "original_relationship_index": relationship["relationship_index"],
            }
        )
    return rows


def extract_graph(
    source_dir: Path = DEFAULT_SOURCE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    graph = load_verified_graph(source_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    nodes = _node_rows(graph)
    relationships = _relationship_rows(graph)
    full_messages = _message_rows(relationships)
    semantic_messages = _message_rows(
        relationships,
        excluded_types=PROVENANCE_RELATIONSHIP_TYPES,
    )

    if len(full_messages) != EXPECTED_FULL_MESSAGE_EDGE_COUNT:
        raise ExtractionError(f"Unexpected full message-edge count: {len(full_messages)}")
    if len(semantic_messages) != EXPECTED_SEMANTIC_MESSAGE_EDGE_COUNT:
        raise ExtractionError(f"Unexpected semantic message-edge count: {len(semantic_messages)}")

    output_specs = {
        "nodes.csv": (
            (
                "node_index",
                "node_id",
                "node_label",
                "source_file",
                "dataset_version",
                "feature_text",
                "feature_text_sha256",
            ),
            nodes,
        ),
        "relationships.csv": (
            (
                "relationship_index",
                "source_node_index",
                "source_node_id",
                "source_node_label",
                "target_node_index",
                "target_node_id",
                "target_node_label",
                "relationship_type",
                "source_file",
                "properties_json",
            ),
            relationships,
        ),
        "message_edges_full.csv": (
            (
                "message_edge_index",
                "source_node_index",
                "source_node_label",
                "target_node_index",
                "target_node_label",
                "relationship_type",
                "message_direction",
                "original_relationship_index",
            ),
            full_messages,
        ),
        "message_edges_semantic.csv": (
            (
                "message_edge_index",
                "source_node_index",
                "source_node_label",
                "target_node_index",
                "target_node_label",
                "relationship_type",
                "message_direction",
                "original_relationship_index",
            ),
            semantic_messages,
        ),
    }
    for filename, (fieldnames, rows) in output_specs.items():
        _write_csv(output_dir / filename, fieldnames, rows)

    output_hashes = {
        filename: sha256_path(output_dir / filename) for filename in sorted(output_specs)
    }
    manifest = {
        "extraction_version": EXTRACTION_VERSION,
        "deterministic": True,
        "created_utc": None,
        "source": {
            "graph_import_manifest": "artifacts/knowledge_graph/graph_import_manifest.json",
            "graph_import_manifest_sha256": graph.source_manifest_sha256,
            "dataset_version": EXPECTED_DATASET_VERSION,
            "graph_version": EXPECTED_GRAPH_VERSION,
            "snapshot_date": EXPECTED_SNAPSHOT_DATE,
            "pinned_cohort_size": graph.source_manifest["pinned_cohort_size"],
            "prototype_trial_count": graph.source_manifest["node_counts"]["Trial"],
            "source_file_sha256": graph.source_file_hashes,
        },
        "node_ordering": {
            "label_order": list(NODE_LABEL_ORDER),
            "within_label": "ascending stable Neo4j import identifier",
            "node_index_range": [0, len(nodes) - 1],
        },
        "relationship_ordering": {
            "type_order": list(RELATIONSHIP_TYPE_ORDER),
            "within_type": "source node index, target node index, source filename, properties JSON",
            "source_direction_preserved": True,
        },
        "feature_field_policy": {
            "approved_fields_by_label": {
                label: list(fields) for label, fields in FEATURE_FIELDS.items()
            },
            "prohibited_fields": list(PROHIBITED_FEATURE_FIELDS),
            "planned_outcome_safeguard": PLANNED_OUTCOME_SAFEGUARD,
            "historical_claim_policy": (
                "Snapshot attributes are not asserted to represent original registration-time values."
            ),
            "feature_text_is_source_bound": True,
            "llm_generated_text": False,
        },
        "counts": {
            "nodes_total": len(nodes),
            "nodes_by_label": dict(sorted(Counter(row["node_label"] for row in nodes).items())),
            "original_directed_relationships_total": len(relationships),
            "original_relationships_by_type": dict(
                sorted(Counter(row["relationship_type"] for row in relationships).items())
            ),
            "full_message_edges_total": len(full_messages),
            "semantic_original_relationships_total": len(semantic_messages) // 2,
            "semantic_message_edges_total": len(semantic_messages),
            "provenance_original_relationships_total": sum(
                row["relationship_type"] in PROVENANCE_RELATIONSHIP_TYPES
                for row in relationships
            ),
        },
        "message_passing": {
            "full_graph": {
                "source_relationships": "all original directed relationships",
                "reverse_edges_added": True,
                "provenance_relationships_present": True,
            },
            "semantic_graph": {
                "excluded_relationship_types": sorted(PROVENANCE_RELATIONSHIP_TYPES),
                "reverse_edges_added": True,
                "provenance_preserved_in_original_graph": True,
            },
        },
        "outputs": {
            filename: {"sha256": output_hashes[filename], "row_count": len(rows)}
            for filename, (_, rows) in sorted(output_specs.items())
        },
        "validation": {
            "source_hashes_match": True,
            "versions_match": True,
            "node_identifiers_unique": True,
            "relationship_triples_unique": True,
            "relationship_endpoints_valid": True,
            "source_graph_connected": True,
            "original_directions_preserved": True,
            "provenance_preserved": True,
            "feature_policy_applied": True,
        },
    }
    manifest_path = output_dir / "extraction_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = extract_graph(args.source_dir, args.output_dir)
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir),
                "nodes": manifest["counts"]["nodes_total"],
                "relationships": manifest["counts"]["original_directed_relationships_total"],
                "full_message_edges": manifest["counts"]["full_message_edges_total"],
                "semantic_message_edges": manifest["counts"]["semantic_message_edges_total"],
                "manifest": str(args.output_dir / "extraction_manifest.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
