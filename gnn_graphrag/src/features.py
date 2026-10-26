"""Deterministic, offline node features for HeartTrialTwin GraphSAGE."""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence

import numpy as np

from graph_data import GraphData


REPO_ROOT = Path(__file__).resolve().parents[2]
VECTOR_INDEX_MANIFEST = REPO_ROOT / "vector_rag" / "data" / "index_manifest.json"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
EXPECTED_MODEL_SNAPSHOT_SHA256 = "fa4e0ce8c98e7af6762dcc8d1930113fab9c487f5c59ba80c5e9d3e098b0f8b2"
SEMANTIC_DIMENSION = 384
NODE_TYPE_ORDER = (
    "Trial",
    "ConditionTerm",
    "Intervention",
    "Sponsor",
    "PlannedOutcome",
    "SourceDataset",
)
NODE_TYPE_DIMENSION = len(NODE_TYPE_ORDER)
FEATURE_DIMENSION = SEMANTIC_DIMENSION + NODE_TYPE_DIMENSION


class FeatureError(RuntimeError):
    """Raised when the pinned encoder or generated features are invalid."""


class TextEncoder(Protocol):
    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Return normalized float vectors in input order."""


@dataclass(frozen=True)
class FeatureBundle:
    matrix: np.ndarray
    feature_sha256: str
    semantic_sha256: str
    repeat_sha256: str | None
    repeat_max_absolute_difference: float | None
    model_name: str
    model_revision: str
    model_snapshot_sha256: str
    node_type_order: tuple[str, ...]


def matrix_sha256(matrix: np.ndarray) -> str:
    canonical = np.asarray(matrix, dtype="<f4", order="C")
    return hashlib.sha256(canonical.tobytes(order="C")).hexdigest()


def model_snapshot_sha256(snapshot_path: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(path for path in snapshot_path.rglob("*") if path.is_file())
    if not files:
        raise FeatureError(f"Resolved model snapshot is empty: {snapshot_path}")
    for path in files:
        relative = path.relative_to(snapshot_path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def validate_vector_model_pin() -> dict[str, Any]:
    if not VECTOR_INDEX_MANIFEST.is_file():
        raise FeatureError("Pinned Vector RAG index manifest is missing")
    manifest = json.loads(VECTOR_INDEX_MANIFEST.read_text(encoding="utf-8"))
    embedding = manifest.get("embedding", {})
    expected = {
        "model_name": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "dimension": SEMANTIC_DIMENSION,
        "normalized": True,
        "device": "cpu",
        "model_snapshot_sha256": EXPECTED_MODEL_SNAPSHOT_SHA256,
    }
    mismatches = {
        key: {"expected": value, "actual": embedding.get(key)}
        for key, value in expected.items()
        if embedding.get(key) != value
    }
    if mismatches:
        raise FeatureError(f"Vector model pin mismatch: {mismatches}")
    return manifest


class OfflineMiniLMEncoder:
    """Exact cached MiniLM encoder with network access disabled."""

    def __init__(self) -> None:
        validate_vector_model_pin()
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        try:
            from huggingface_hub import snapshot_download
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - environment guard
            raise FeatureError(
                "Use the existing .venv-vector-rag environment; required embedding packages are unavailable"
            ) from exc
        try:
            snapshot = Path(
                snapshot_download(
                    repo_id=MODEL_NAME,
                    revision=MODEL_REVISION,
                    local_files_only=True,
                )
            ).resolve()
        except Exception as exc:
            raise FeatureError(
                f"Exact MiniLM revision is not available in the local cache: {MODEL_REVISION}"
            ) from exc
        snapshot_hash = model_snapshot_sha256(snapshot)
        if snapshot_hash != EXPECTED_MODEL_SNAPSHOT_SHA256:
            raise FeatureError(
                f"MiniLM snapshot hash mismatch: {snapshot_hash} != {EXPECTED_MODEL_SNAPSHOT_SHA256}"
            )
        self.snapshot_path = snapshot
        self.snapshot_hash = snapshot_hash
        self.model = SentenceTransformer(
            MODEL_NAME,
            revision=MODEL_REVISION,
            device="cpu",
            local_files_only=True,
        )
        if self.model.get_sentence_embedding_dimension() != SEMANTIC_DIMENSION:
            raise FeatureError("Unexpected MiniLM embedding dimension")
        if str(self.model.device) != "cpu":
            raise FeatureError(f"MiniLM must run on CPU; found {self.model.device}")

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        values = self.model.encode(
            list(texts),
            batch_size=16,
            convert_to_numpy=True,
            device="cpu",
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(values, dtype=np.float32)


def _validate_semantic_embeddings(values: np.ndarray, node_count: int) -> np.ndarray:
    matrix = np.asarray(values, dtype=np.float32)
    if matrix.shape != (node_count, SEMANTIC_DIMENSION):
        raise FeatureError(
            f"Expected semantic shape {(node_count, SEMANTIC_DIMENSION)}; found {matrix.shape}"
        )
    if not np.isfinite(matrix).all():
        raise FeatureError("Semantic embeddings contain non-finite values")
    norms = np.linalg.norm(matrix, axis=1)
    if not np.allclose(norms, np.ones_like(norms), rtol=1e-5, atol=1e-5):
        raise FeatureError(
            f"Semantic embeddings are not normalized; norm range={norms.min()}..{norms.max()}"
        )
    return matrix


def build_feature_matrix(
    graph: GraphData,
    encoder: TextEncoder,
    *,
    verify_repeat: bool = True,
    model_snapshot_sha256_value: str = EXPECTED_MODEL_SNAPSHOT_SHA256,
) -> FeatureBundle:
    texts = [node.feature_text for node in graph.nodes]
    semantic = _validate_semantic_embeddings(encoder.encode(texts), len(graph.nodes))

    repeat_hash: str | None = None
    max_difference: float | None = None
    if verify_repeat:
        repeated = _validate_semantic_embeddings(encoder.encode(texts), len(graph.nodes))
        max_difference = float(np.max(np.abs(semantic - repeated)))
        repeat_hash = matrix_sha256(repeated)
        if repeat_hash != matrix_sha256(semantic) or not math.isclose(
            max_difference, 0.0, rel_tol=0.0, abs_tol=0.0
        ):
            raise FeatureError(
                f"Repeated embedding generation was not byte-identical; max difference={max_difference}"
            )

    label_to_offset = {label: offset for offset, label in enumerate(NODE_TYPE_ORDER)}
    one_hot = np.zeros((len(graph.nodes), NODE_TYPE_DIMENSION), dtype=np.float32)
    for row, node in enumerate(graph.nodes):
        if node.label not in label_to_offset:
            raise FeatureError(f"Unexpected node label: {node.label}")
        one_hot[row, label_to_offset[node.label]] = 1.0
    matrix = np.concatenate((semantic, one_hot), axis=1).astype(np.float32, copy=False)
    if matrix.shape != (len(graph.nodes), FEATURE_DIMENSION):
        raise FeatureError(f"Unexpected feature matrix shape: {matrix.shape}")
    if not np.isfinite(matrix).all():
        raise FeatureError("Combined node features contain non-finite values")
    if not np.all(one_hot.sum(axis=1) == 1.0):
        raise FeatureError("Node-type one-hot features are invalid")

    return FeatureBundle(
        matrix=matrix,
        feature_sha256=matrix_sha256(matrix),
        semantic_sha256=matrix_sha256(semantic),
        repeat_sha256=repeat_hash,
        repeat_max_absolute_difference=max_difference,
        model_name=MODEL_NAME,
        model_revision=MODEL_REVISION,
        model_snapshot_sha256=model_snapshot_sha256_value,
        node_type_order=NODE_TYPE_ORDER,
    )
