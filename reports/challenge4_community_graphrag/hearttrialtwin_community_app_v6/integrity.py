"""Read-only preflight for the v6 runtime; never repairs or re-pins inputs."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RECEIPT = HERE / "runtime_integrity_v1.json"
# Set from the completed, independently checked receipt, not from user input.
RECEIPT_SHA256 = "958f09f86117ee7cdad8315ffa7d1f1ffdcf8d2ce931d58293654fa70e846655"
GRAPH = "artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1"
COMMUNITY = "reports/challenge4_community_graphrag/full_cohort_results/community_sensitivity_v2.json"


class IntegrityError(ValueError):
    """Safe authored error; contains no configuration or source values."""


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_path(root, relative):
    root = Path(root).resolve()
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or any(p.startswith(".env") for p in rel.parts):
        raise IntegrityError("Unsafe runtime inventory path")
    path = (root / rel).resolve()
    if not path.is_relative_to(root):
        raise IntegrityError("Runtime asset escapes project root")
    return path


def load_receipt():
    if not RECEIPT.is_file() or sha(RECEIPT) != RECEIPT_SHA256:
        raise IntegrityError("v6 integrity receipt missing or modified")
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def check_files(root, receipt):
    """Also used by the offline provisioning checker against an isolated root."""
    if receipt.get("schema_version") != "HTT-COMMUNITY-V6-RUNTIME-v1":
        raise IntegrityError("Unsupported runtime receipt schema")
    entries = receipt.get("assets")
    if not isinstance(entries, list) or not entries:
        raise IntegrityError("Empty runtime inventory")
    seen, failures = set(), []
    for entry in entries:
        rel = entry["path"]
        if rel in seen:
            raise IntegrityError("Duplicate runtime inventory path")
        seen.add(rel)
        path = safe_path(root, rel)
        if not path.is_file():
            failures.append({"path": rel, "reason": "MISSING"})
        elif sha(path) != entry["sha256"]:
            failures.append({"path": rel, "reason": "CHECKSUM_MISMATCH"})
    return failures


def graph_membership(root):
    path = Path(root) / GRAPH / "nodes_trial.csv"
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    ids = [r["nct_id"] for r in rows]
    if len(ids) != 2824 or len(set(ids)) != 2824:
        raise IntegrityError("Trial membership count or uniqueness mismatch")
    return set(ids)


def b3_membership(root, trial_ids):
    data = json.loads((Path(root) / COMMUNITY).read_text(encoding="utf-8"))
    projections = [r for r in data["results"] if r["projection"] == "B3_exact_normalization"]
    if len(projections) != 1:
        raise IntegrityError("B3 projection identity mismatch")
    runs = [r for r in projections[0]["runs"] if r["seed"] == 42]
    if len(runs) != 1:
        raise IntegrityError("B3 seed identity mismatch")
    membership = runs[0]["membership"]
    if set(membership) != set(trial_ids):
        raise IntegrityError("B3 and trial membership mismatch")
    counts = Counter(membership.values())
    if len(counts) != 904 or sum(v == 1 for v in counts.values()) != 820:
        raise IntegrityError("B3 community counts mismatch")
    return membership


def verify_runtime(root=ROOT):
    receipt = load_receipt()
    failures = check_files(root, receipt)
    if failures:
        raise IntegrityError("Required runtime asset missing or changed: " + failures[0]["path"])
    ids = graph_membership(root)
    membership = b3_membership(root, ids)
    return {
        "status": "OK", "version": "HTT-COMMUNITY-V6-RUNTIME-v1",
        "receipt_sha256": RECEIPT_SHA256, "assets_verified": len(receipt["assets"]),
        "trials": len(ids), "communities": len(set(membership.values())),
        "snapshot_date": "2026-09-05", "network_calls": False,
        "source_writes": False, "ollama_enabled": False,
    }
