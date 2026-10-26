"""Allowlisted training-input reader; no validation/test truth is opened.

The current protocol is provisional: only audit_only inspection is authorized.
This is API isolation, not a claim of operating-system access control.
"""

from dataclasses import dataclass
import json
from pathlib import Path
import re

try:
    from . import prepare_association_protocol_v2 as protocol
except ImportError:
    import prepare_association_protocol_v2 as protocol

TRAIN_FILES = frozenset({"queries.jsonl", "candidates.csv", "families.csv", "context_nodes.jsonl", "message_edges.csv"})
CONTEXT_LABELS = frozenset({"Trial", "ConditionTerm", "Intervention", "Sponsor"})
CONTEXT_RELATIONSHIPS = frozenset({"HAS_SUBMITTED_CONDITION", "HAS_BROWSE_CONDITION", "HAS_INTERVENTION", "LEAD_SPONSORED_BY"})


@dataclass(frozen=True)
class TrainingInputs:
    queries: tuple
    candidate_ids: tuple
    context_nodes: tuple
    message_edges: tuple
    training_permitted: bool = False


def load_training_data(protocol_dir=protocol.DEFAULT_OUTPUT, *, audit_only=False):
    """Read only training/manifest.json and five fixed, non-symlink inputs."""
    location = Path(protocol_dir) / "training"
    protocol.require(not location.is_symlink(), "Training directory symlink prohibited")
    directory = location.resolve()
    manifest_path = directory / "manifest.json"
    protocol.require(not manifest_path.is_symlink(), "Training manifest symlink prohibited")
    manifest = json.loads(manifest_path.read_text())
    protocol.require(manifest.get("schema_version") == protocol.VERSION + "-TRAIN-INPUTS"
        and manifest.get("status") == protocol.STATE and manifest.get("training_permitted") is False,
        "Unexpected training manifest readiness/version")
    if not audit_only:
        raise protocol.ProtocolError("PROVISIONAL protocol: training is blocked pending human review")
    hashes = manifest["files_sha256"]
    protocol.require(set(hashes) == TRAIN_FILES, "Unexpected training input paths")
    for name, expected in hashes.items():
        path = directory / name
        protocol.require(not path.is_symlink() and path.resolve().parent == directory, "Training input symlink/escape prohibited")
        protocol.require(protocol.extraction.sha256(path) == expected, "Training input checksum mismatch: " + name)
    candidates = protocol.read_csv(directory / "candidates.csv")
    protocol.require(all(set(r) == {"nct_id"} for r in candidates), "Unexpected candidate fields")
    ids = tuple(r["nct_id"] for r in candidates)
    allowed = set(ids)
    protocol.require(ids == tuple(sorted(allowed)) and all(re.fullmatch(r"NCT\d{8}", n) for n in ids), "Invalid training candidate IDs")
    families = protocol.read_csv(directory / "families.csv")
    protocol.require(len(families) == len(ids) and {r["nct_id"] for r in families} == allowed
                     and all(set(r) == {"nct_id", "family_id"} for r in families), "Invalid training families")
    queries = protocol.read_jsonl(directory / "queries.jsonl")
    seen = set()
    for q in queries:
        protocol.require(set(q) == {"query_id", "query_text", "positive_trial_ids", "ambiguous_trial_ids"}, "Unexpected training query fields")
        protocol.require(q["query_text"] == protocol.normalize(q["query_text"])
            and not protocol.extraction.NCT_TOKEN.search(q["query_text"])
            and q["query_id"] == protocol.key("Q-", q["query_text"]) and q["query_id"] not in seen,
            "Invalid measure-only training input")
        seen.add(q["query_id"])
        for field in ("positive_trial_ids", "ambiguous_trial_ids"):
            protocol.require(q[field] == sorted(set(q[field])) and set(q[field]) <= allowed, "Non-training/duplicate owner in training labels")
        protocol.require(bool(q["positive_trial_ids"]), "Training query lacks a positive")
    context = protocol.read_jsonl(directory / "context_nodes.jsonl")
    by_index = {}
    for row in context:
        protocol.require(set(row) == {"node_index", "node_id", "node_label", "feature_text"}
            and row["node_label"] in CONTEXT_LABELS and not protocol.extraction.NCT_TOKEN.search(row["feature_text"]),
            "Unsafe context feature projection")
        protocol.require(row["node_index"] not in by_index, "Duplicate context node")
        by_index[row["node_index"]] = row
    protocol.require(len(context) == 9036, "Context node count mismatch")
    edges = protocol.extraction.read_csv(directory / "message_edges.csv", protocol.extraction.MESSAGE_FIELDS)
    seen_edges = set()
    for row in edges:
        s, t = row["source_node_index"], row["target_node_index"]
        protocol.require(row["relationship_type"] in CONTEXT_RELATIONSHIPS and s in by_index and t in by_index,
            "Target or invalid edge in training context")
        protocol.require(row["source_node_label"] == by_index[s]["node_label"]
            and row["target_node_label"] == by_index[t]["node_label"], "Context endpoint label mismatch")
        identity = (s, row["relationship_type"], t)
        protocol.require(identity not in seen_edges, "Duplicate training edge")
        seen_edges.add(identity)
    protocol.require(len(edges) == 61218, "Training context edge count mismatch")
    return TrainingInputs(tuple(queries), ids, tuple(context), tuple(edges))


def negative_candidates(inputs, query_id):
    """Return eligible training negatives; no sampling or held-out lookup."""
    query = next((q for q in inputs.queries if q["query_id"] == query_id), None)
    protocol.require(query is not None, "Unknown training query")
    excluded = set(query["positive_trial_ids"]) | set(query["ambiguous_trial_ids"])
    return tuple(n for n in inputs.candidate_ids if n not in excluded)
