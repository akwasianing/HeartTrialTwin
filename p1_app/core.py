"""Shared artifact loading, exact-NCT lookup, and review records."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


APP_DIR = Path(__file__).resolve().parent
ARTEFACTS = APP_DIR / "artefacts"
REQUIRED_ARTEFACTS = (
    "features.parquet",
    "model.pkl",
    "predictions.parquet",
    "shap_values.parquet",
    "validation_metrics.json",
    "model_card.json",
    "shap_audit.json",
    "evidence_cache.json",
)


def missing_artefacts() -> list[str]:
    return [name for name in REQUIRED_ARTEFACTS if not (ARTEFACTS / name).exists()]


def load_runtime() -> tuple[pd.DataFrame, pd.DataFrame, dict, dict, dict]:
    missing = missing_artefacts()
    if missing:
        raise FileNotFoundError(f"Missing application artifacts: {', '.join(missing)}")
    predictions = pd.read_parquet(ARTEFACTS / "predictions.parquet")
    shap_values = pd.read_parquet(ARTEFACTS / "shap_values.parquet")
    evidence = json.loads((ARTEFACTS / "evidence_cache.json").read_text(encoding="utf-8"))
    metrics = json.loads((ARTEFACTS / "validation_metrics.json").read_text(encoding="utf-8"))
    shap_audit = json.loads((ARTEFACTS / "shap_audit.json").read_text(encoding="utf-8"))
    return predictions, shap_values, evidence, metrics, shap_audit


def get_exact_evidence(nct_id: str, evidence_cache: dict[str, dict]) -> dict[str, Any]:
    key = nct_id.strip().upper()
    if key not in evidence_cache:
        raise KeyError(f"{key} is not available in the frozen cohort evidence")
    evidence = evidence_cache[key]
    forbidden = {"discontinued", "overall_status", "source_overall_status", "why_stopped"}
    if forbidden & set(evidence):
        raise RuntimeError("Outcome information leaked into exact-NCT evidence")
    if evidence.get("nct_id") != key:
        raise RuntimeError(f"Evidence key mismatch for {key}")
    return evidence


def get_trial_result(
    nct_id: str,
    predictions: pd.DataFrame,
    shap_values: pd.DataFrame,
    evidence_cache: dict[str, dict],
) -> tuple[dict[str, Any], dict[str, Any]]:
    key = nct_id.strip().upper()
    prediction_rows = predictions[predictions.nct_id == key]
    shap_rows = shap_values[shap_values.nct_id == key]
    if prediction_rows.empty or shap_rows.empty or key not in evidence_cache:
        raise KeyError(f"{key} is not available in the frozen cohort artifacts")
    if len(prediction_rows) != 1 or len(shap_rows) != 1:
        raise RuntimeError(f"Exact-NCT lookup is not one-to-one for {key}")

    result = prediction_rows.iloc[0].to_dict()
    result.update(shap_rows.iloc[0].to_dict())
    evidence = get_exact_evidence(key, evidence_cache)
    if result["model_version"] != evidence["model_version"]:
        raise RuntimeError("Model-version mismatch between prediction and evidence")
    if int(result["submission_year"]) != int(evidence["submission_year"]):
        raise RuntimeError("Submission-year mismatch between prediction and evidence")
    forbidden = {"discontinued", "overall_status", "source_overall_status", "why_stopped"}
    if forbidden & set(result) or forbidden & set(evidence):
        raise RuntimeError("Outcome information leaked into runtime result")
    return result, evidence


def make_review_record(
    nct_id: str,
    action: str,
    reviewer_comment: str,
    explanation: dict[str, Any],
) -> dict[str, Any]:
    if action not in {"accept", "reject", "request_revision"}:
        raise ValueError(f"Unsupported review action: {action}")
    if action in {"reject", "request_revision"} and not reviewer_comment.strip():
        raise ValueError("Reviewer feedback is required for rejection or revision")
    text = explanation["text"]
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "nct_id": nct_id,
        "action": action,
        "reviewer_comment": reviewer_comment.strip(),
        "reviewer_comment_is_separate_from_system_text": True,
        "system_explanation_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "generator": explanation["generator"],
        "revision_mode": explanation["revision_mode"],
        "numeric_facts": explanation["numeric_facts"],
    }
