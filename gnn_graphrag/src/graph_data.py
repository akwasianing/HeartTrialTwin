"""Load and validate deterministic HeartTrialTwin GNN graph artifacts."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = REPO_ROOT / "gnn_graphrag" / "data"
EXPECTED_EXTRACTION_VERSION = "HTT-GNN-GRAPH-EXTRACT-v1"
EXPECTED_DATASET_VERSION = "HTT-P1-AACT-20260905"
EXPECTED_GRAPH_VERSION = "HTT-KG-AACT-20260905-v1"
EXPECTED_SNAPSHOT_DATE = "2026-09-05"
EXPECTED_NODE_COUNT = 26
EXPECTED_RELATIONSHIP_COUNT = 65
EXPECTED_SEMANTIC_MESSAGE_EDGE_COUNT = 80
PROVENANCE_RELATIONSHIP_TYPES = frozenset({"MEMBER_OF_DATASET", "SOURCED_FROM"})


class GraphDataError(RuntimeError):
    """Raised when an extracted graph artifact is incompatible or corrupt."""


@dataclass(frozen=True)
class GraphNode:
    index: int
    node_id: str
    label: str
    source_file: str
    dataset_version: str
    feature_text: str
    feature_text_sha256: str


@dataclass(frozen=True)
class MessageEdge:
    index: int
    source: int
    source_label: str
    target: int
    target_label: str
    relationship_type: str
    direction: str
    original_relationship_index: int


@dataclass(frozen=True)
class OriginalRelationship:
    index: int
    source: int
    source_id: str
    source_label: str
    target: int
    target_id: str
    target_label: str
    relationship_type: str
    source_file: str
    properties: dict[str, Any]


@dataclass(frozen=True)
class GraphData:
    nodes: tuple[GraphNode, ...]
    original_relationships: tuple[OriginalRelationship, ...]
    semantic_edges: tuple[MessageEdge, ...]
    extraction_manifest: dict[str, Any]
    extraction_manifest_sha256: str
    nodes_sha256: str
    relationships_sha256: str
    semantic_edges_sha256: str

    @property
    def node_id_to_index(self) -> dict[str, int]:
        return {node.node_id: node.index for node in self.nodes}

    def edge_index(self, excluded_relationship_types: Iterable[str] = ()) -> Any:
        """Return a PyTorch [2, E] source-to-target edge tensor."""

        try:
            import torch
        except ImportError as exc:  # pragma: no cover - environment guard
            raise GraphDataError("PyTorch is required for edge tensors") from exc
        excluded = frozenset(excluded_relationship_types)
        pairs = [
            (edge.source, edge.target)
            for edge in self.semantic_edges
            if edge.relationship_type not in excluded
        ]
        if not pairs:
            return torch.empty((2, 0), dtype=torch.long)
        return torch.tensor(pairs, dtype=torch.long).t().contiguous()

    def one_hop_indices(self, node_index: int) -> tuple[int, ...]:
        self._validate_node_index(node_index)
        return tuple(sorted({edge.target for edge in self.semantic_edges if edge.source == node_index}))

    def two_hop_exclusive_indices(self, node_index: int) -> tuple[int, ...]:
        self._validate_node_index(node_index)
        one_hop = set(self.one_hop_indices(node_index))
        two_hop = {
            edge.target
            for edge in self.semantic_edges
            if edge.source in one_hop
        }
        two_hop.discard(node_index)
        two_hop.difference_update(one_hop)
        return tuple(sorted(two_hop))

    def _validate_node_index(self, node_index: int) -> None:
        if node_index < 0 or node_index >= len(self.nodes):
            raise GraphDataError(f"Node index out of range: {node_index}")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise GraphDataError(f"Required graph artifact is missing: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_graph_data(data_dir: Path = DEFAULT_DATA_DIR) -> GraphData:
    manifest_path = data_dir / "extraction_manifest.json"
    if not manifest_path.is_file():
        raise GraphDataError(f"Extraction manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("extraction_version") != EXPECTED_EXTRACTION_VERSION:
        raise GraphDataError("Unexpected extraction version")
    source = manifest.get("source", {})
    expected_source = {
        "dataset_version": EXPECTED_DATASET_VERSION,
        "graph_version": EXPECTED_GRAPH_VERSION,
        "snapshot_date": EXPECTED_SNAPSHOT_DATE,
    }
    for key, expected in expected_source.items():
        if source.get(key) != expected:
            raise GraphDataError(f"Unexpected {key}: {source.get(key)!r}")

    required_outputs = ("nodes.csv", "relationships.csv", "message_edges_semantic.csv")
    for filename in required_outputs:
        path = data_dir / filename
        expected_hash = manifest.get("outputs", {}).get(filename, {}).get("sha256")
        if not path.is_file() or sha256_path(path) != expected_hash:
            raise GraphDataError(f"Output hash mismatch: {filename}")

    node_rows = _read_csv(data_dir / "nodes.csv")
    if len(node_rows) != EXPECTED_NODE_COUNT:
        raise GraphDataError(f"Expected {EXPECTED_NODE_COUNT} nodes; found {len(node_rows)}")
    nodes: list[GraphNode] = []
    for expected_index, row in enumerate(node_rows):
        actual_index = int(row["node_index"])
        if actual_index != expected_index:
            raise GraphDataError("Node indices are not contiguous and ordered")
        if row["dataset_version"] != EXPECTED_DATASET_VERSION:
            raise GraphDataError(f"Dataset version mismatch for node {row['node_id']}")
        expected_text_hash = hashlib.sha256(row["feature_text"].encode("utf-8")).hexdigest()
        if row["feature_text_sha256"] != expected_text_hash:
            raise GraphDataError(f"Feature-text hash mismatch for node {row['node_id']}")
        nodes.append(
            GraphNode(
                index=actual_index,
                node_id=row["node_id"],
                label=row["node_label"],
                source_file=row["source_file"],
                dataset_version=row["dataset_version"],
                feature_text=row["feature_text"],
                feature_text_sha256=row["feature_text_sha256"],
            )
        )
    if len({node.node_id for node in nodes}) != len(nodes):
        raise GraphDataError("Node identifiers are not unique")

    original_relationship_rows = _read_csv(data_dir / "relationships.csv")
    if len(original_relationship_rows) != EXPECTED_RELATIONSHIP_COUNT:
        raise GraphDataError("Original relationship count mismatch")
    original_relationships: list[OriginalRelationship] = []
    for expected_index, row in enumerate(original_relationship_rows):
        actual_index = int(row["relationship_index"])
        source_index = int(row["source_node_index"])
        target_index = int(row["target_node_index"])
        if actual_index != expected_index:
            raise GraphDataError("Original relationship indices are not contiguous and ordered")
        if source_index not in range(len(nodes)) or target_index not in range(len(nodes)):
            raise GraphDataError("Original relationship has an invalid endpoint")
        if row["source_node_id"] != nodes[source_index].node_id:
            raise GraphDataError("Original relationship source ID does not match node table")
        if row["target_node_id"] != nodes[target_index].node_id:
            raise GraphDataError("Original relationship target ID does not match node table")
        if row["source_node_label"] != nodes[source_index].label:
            raise GraphDataError("Original relationship source label does not match node table")
        if row["target_node_label"] != nodes[target_index].label:
            raise GraphDataError("Original relationship target label does not match node table")
        try:
            properties = json.loads(row["properties_json"])
        except json.JSONDecodeError as exc:
            raise GraphDataError(
                f"Invalid relationship properties JSON at index {actual_index}"
            ) from exc
        original_relationships.append(
            OriginalRelationship(
                index=actual_index,
                source=source_index,
                source_id=row["source_node_id"],
                source_label=row["source_node_label"],
                target=target_index,
                target_id=row["target_node_id"],
                target_label=row["target_node_label"],
                relationship_type=row["relationship_type"],
                source_file=row["source_file"],
                properties=properties,
            )
        )

    edge_rows = _read_csv(data_dir / "message_edges_semantic.csv")
    if len(edge_rows) != EXPECTED_SEMANTIC_MESSAGE_EDGE_COUNT:
        raise GraphDataError(
            f"Expected {EXPECTED_SEMANTIC_MESSAGE_EDGE_COUNT} semantic edges; found {len(edge_rows)}"
        )
    edges: list[MessageEdge] = []
    for expected_index, row in enumerate(edge_rows):
        actual_index = int(row["message_edge_index"])
        source_index = int(row["source_node_index"])
        target_index = int(row["target_node_index"])
        if actual_index != expected_index:
            raise GraphDataError("Message-edge indices are not contiguous and ordered")
        if source_index not in range(len(nodes)) or target_index not in range(len(nodes)):
            raise GraphDataError("Message edge has an invalid endpoint")
        if row["relationship_type"] in PROVENANCE_RELATIONSHIP_TYPES:
            raise GraphDataError("Semantic message graph contains a provenance relationship")
        if row["source_node_label"] != nodes[source_index].label:
            raise GraphDataError("Message-edge source label does not match node table")
        if row["target_node_label"] != nodes[target_index].label:
            raise GraphDataError("Message-edge target label does not match node table")
        edges.append(
            MessageEdge(
                index=actual_index,
                source=source_index,
                source_label=row["source_node_label"],
                target=target_index,
                target_label=row["target_node_label"],
                relationship_type=row["relationship_type"],
                direction=row["message_direction"],
                original_relationship_index=int(row["original_relationship_index"]),
            )
        )

    # Each original semantic relationship must appear once in each direction.
    grouped: dict[int, list[MessageEdge]] = {}
    for edge in edges:
        grouped.setdefault(edge.original_relationship_index, []).append(edge)
    for relationship_index, pair in grouped.items():
        if len(pair) != 2 or {item.direction for item in pair} != {"forward", "reverse"}:
            raise GraphDataError(f"Invalid bidirectional pair for relationship {relationship_index}")
        forward = next(item for item in pair if item.direction == "forward")
        reverse = next(item for item in pair if item.direction == "reverse")
        if (forward.source, forward.target) != (reverse.target, reverse.source):
            raise GraphDataError(f"Reverse edge mismatch for relationship {relationship_index}")

    return GraphData(
        nodes=tuple(nodes),
        original_relationships=tuple(original_relationships),
        semantic_edges=tuple(edges),
        extraction_manifest=manifest,
        extraction_manifest_sha256=sha256_path(manifest_path),
        nodes_sha256=sha256_path(data_dir / "nodes.csv"),
        relationships_sha256=sha256_path(data_dir / "relationships.csv"),
        semantic_edges_sha256=sha256_path(data_dir / "message_edges_semantic.csv"),
    )
