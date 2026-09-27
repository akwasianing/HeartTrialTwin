"""Immutable artifact loading, exact-NCT scoring, and LR contributions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn


APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
ARTIFACTS = PROJECT_ROOT / "artifacts"
MANIFEST_PATH = ARTIFACTS / "runtime_model_manifest.json"
DISCLAIMER = "Experimental — not validated for clinical decision-making."
THRESHOLD = 0.2129
EXPECTED_SCHEMA = [
    "nct_id",
    "submission_year",
    "allocation",
    "intervention_model",
    "primary_purpose",
    "masking",
    "agency_class",
    "gender",
    "healthy_volunteers",
    "number_of_sites",
    "number_of_countries",
    "multinational_trial",
    "adult",
    "child",
    "older_adult",
    "minimum_age_years",
    "maximum_age_years",
    "criteria",
]
FORBIDDEN_COLUMNS = {
    "discontinued",
    "overall_status",
    "temporal_set",
    "modeling_period",
    "error_type",
    "why_stopped",
}


@dataclass(frozen=True)
class RuntimeBundle:
    model: Any
    inputs: pd.DataFrame
    manifest: dict[str, Any]
    summary: dict[str, Any]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verified_path(filename: str, expected_hash: str) -> Path:
    path = ARTIFACTS / filename
    if not path.is_file():
        raise FileNotFoundError(f"Required frozen artifact is missing: {filename}")
    actual = sha256_file(path)
    if actual != expected_hash:
        raise RuntimeError(f"SHA-256 mismatch for {filename}: {actual}")
    return path


def validate_inputs(frame: pd.DataFrame) -> None:
    if len(frame) != 2835:
        raise RuntimeError(f"Expected 2,835 runtime rows; found {len(frame):,}")
    if list(frame.columns) != EXPECTED_SCHEMA:
        raise RuntimeError("Runtime input schema differs from the frozen contract")
    if frame["nct_id"].isna().any() or not frame["nct_id"].is_unique:
        raise RuntimeError("Runtime NCT IDs must be present and unique")
    forbidden = FORBIDDEN_COLUMNS & set(frame.columns)
    if forbidden:
        raise RuntimeError(f"Outcome-derived runtime columns are forbidden: {sorted(forbidden)}")


def load_runtime() -> RuntimeBundle:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError("Runtime model manifest is missing")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if float(manifest["threshold"]) != THRESHOLD:
        raise RuntimeError("Frozen threshold mismatch")
    if manifest["runtime_policy"]["disclaimer"] != DISCLAIMER:
        raise RuntimeError("Required experimental-use disclaimer mismatch")
    expected_sklearn = manifest["training_versions"]["scikit_learn"]
    if sklearn.__version__ != expected_sklearn:
        raise RuntimeError(
            f"Frozen model requires scikit-learn {expected_sklearn}; found {sklearn.__version__}"
        )

    model_path = _verified_path(manifest["model_file"], manifest["model_sha256"])
    inputs_path = _verified_path(
        manifest["runtime_inputs_file"], manifest["runtime_inputs_sha256"]
    )
    summary_path = _verified_path(
        manifest["final_model_summary_file"], manifest["final_model_summary_sha256"]
    )
    _verified_path(
        manifest["training_environment_file"],
        manifest["training_environment_sha256"],
    )

    inputs = pd.read_parquet(inputs_path)
    validate_inputs(inputs)
    model = joblib.load(model_path)
    if list(model.feature_names_in_) != EXPECTED_SCHEMA[2:]:
        raise RuntimeError("Frozen pipeline feature contract mismatch")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return RuntimeBundle(model=model, inputs=inputs, manifest=manifest, summary=summary)


def get_trial_input(bundle: RuntimeBundle, nct_id: str) -> pd.DataFrame:
    key = nct_id.strip().upper()
    rows = bundle.inputs[bundle.inputs["nct_id"].str.upper() == key]
    if rows.empty:
        raise KeyError(f"{key or 'Blank NCT ID'} is not available in the frozen runtime inputs")
    if len(rows) != 1:
        raise RuntimeError(f"Exact-NCT lookup is not one-to-one for {key}")
    return rows.copy()


def _friendly_group(feature_name: str) -> tuple[str, str]:
    if feature_name.startswith("text__"):
        return "criteria_text", feature_name.removeprefix("text__")
    if feature_name.startswith("num__"):
        raw = feature_name.removeprefix("num__")
        return raw, raw
    if feature_name.startswith("cat__"):
        encoded = feature_name.removeprefix("cat__")
        categorical = EXPECTED_SCHEMA[2:9]
        for raw in sorted(categorical, key=len, reverse=True):
            prefix = raw + "_"
            if encoded.startswith(prefix):
                return raw, encoded.removeprefix(prefix)
        return "structured_other", encoded
    return "structured_other", feature_name


def _is_missing(value: Any) -> bool:
    return pd.isna(value) or (isinstance(value, str) and not value.strip())


def score_trial(bundle: RuntimeBundle, nct_id: str) -> dict[str, Any]:
    row = get_trial_input(bundle, nct_id)
    model_columns = list(bundle.model.feature_names_in_)
    model_input = row[model_columns]
    probability = float(bundle.model.predict_proba(model_input)[0, 1])
    decision = float(bundle.model.decision_function(model_input)[0])

    preprocessor = bundle.model.named_steps["prep"]
    classifier = bundle.model.named_steps["model"]
    transformed = preprocessor.transform(model_input)
    values = transformed.toarray().ravel() if hasattr(transformed, "toarray") else np.asarray(transformed).ravel()
    coefficients = np.asarray(classifier.coef_).ravel()
    feature_names = preprocessor.get_feature_names_out()
    if not (len(values) == len(coefficients) == len(feature_names)):
        raise RuntimeError("Transformed feature and coefficient dimensions differ")
    contributions = values * coefficients
    intercept = float(np.asarray(classifier.intercept_).ravel()[0])
    reconstructed = intercept + float(contributions.sum())
    additivity_error = abs(reconstructed - decision)
    if additivity_error > 1e-10:
        raise RuntimeError(f"Local contribution additivity failed: {additivity_error}")

    grouped: dict[str, float] = {}
    text_terms: list[dict[str, Any]] = []
    for name, value, contribution in zip(feature_names, values, contributions, strict=True):
        group, detail = _friendly_group(str(name))
        grouped[group] = grouped.get(group, 0.0) + float(contribution)
        if group == "criteria_text" and value != 0:
            text_terms.append(
                {
                    "term": detail,
                    "tfidf_value": float(value),
                    "log_odds_contribution": float(contribution),
                }
            )

    structured = [
        {
            "feature": feature,
            "input_value": row.iloc[0][feature] if feature in row.columns else None,
            "log_odds_contribution": contribution,
        }
        for feature, contribution in grouped.items()
        if feature != "criteria_text"
    ]
    structured.sort(key=lambda item: abs(item["log_odds_contribution"]), reverse=True)
    positive_terms = sorted(
        (item for item in text_terms if item["log_odds_contribution"] > 0),
        key=lambda item: item["log_odds_contribution"],
        reverse=True,
    )[:5]
    negative_terms = sorted(
        (item for item in text_terms if item["log_odds_contribution"] < 0),
        key=lambda item: item["log_odds_contribution"],
    )[:5]

    raw = row.iloc[0]
    missing = [column for column in model_columns if _is_missing(raw[column])]
    return {
        "nct_id": str(raw["nct_id"]),
        "submission_year": int(raw["submission_year"]),
        "probability": probability,
        "threshold": THRESHOLD,
        "threshold_position": "above_or_equal" if probability >= THRESHOLD else "below",
        "decision_log_odds": decision,
        "intercept_log_odds": intercept,
        "contribution_sum": float(contributions.sum()),
        "reconstructed_log_odds": reconstructed,
        "additivity_error": additivity_error,
        "top_structured_contributions": structured[:8],
        "criteria_text_contribution": grouped.get("criteria_text", 0.0),
        "top_positive_text_terms": positive_terms,
        "top_negative_text_terms": negative_terms,
        "input_missing_fields": missing,
        "input_record": raw.to_dict(),
        "model_version": bundle.manifest["model_version"],
        "data_version": bundle.manifest["data_version"],
        "model_sha256": bundle.manifest["model_sha256"],
        "disclaimer": DISCLAIMER,
    }
