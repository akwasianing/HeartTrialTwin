#!/usr/bin/env python3
"""Score the frozen cohort and calculate one-feature SHAP on log-odds scale."""

from __future__ import annotations

import json
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import shap


ARTEFACTS = Path(__file__).resolve().parent / "artefacts"
FEATURES = ["submission_year"]
ADDITIVITY_TOLERANCE = 1e-8


def score_and_explain() -> None:
    feature_path = ARTEFACTS / "features.parquet"
    model_path = ARTEFACTS / "model.pkl"
    if not feature_path.exists() or not model_path.exists():
        raise RuntimeError("Run feature_build.py and train_model.py first")

    data = pd.read_parquet(feature_path)
    with model_path.open("rb") as handle:
        bundle = pickle.load(handle)

    if bundle["features"] != FEATURES:
        raise RuntimeError(f"Unexpected predictors in model bundle: {bundle['features']}")
    pipeline = bundle["pipeline"]
    probabilities = pipeline.predict_proba(data[FEATURES])[:, 1]
    if not np.isfinite(probabilities).all() or not (
        (probabilities >= 0.0) & (probabilities <= 1.0)
    ).all():
        raise RuntimeError("Invalid predict_proba output")

    predictions = data[
        ["nct_id", "study_first_submitted_date", "submission_year", "temporal_group", "dataset_version"]
    ].copy()
    predictions["predicted_probability"] = probabilities
    predictions["model_version"] = bundle["model_version"]
    predictions["model_release_status"] = bundle["release_status"]
    predictions.to_parquet(ARTEFACTS / "predictions.parquet", index=False)

    scaler = pipeline.named_steps["scaler"]
    classifier = pipeline.named_steps["logistic_regression"]
    development = data[data.temporal_group == "development"]
    X_dev_scaled = scaler.transform(development[FEATURES])
    X_all_scaled = scaler.transform(data[FEATURES])

    # LinearExplainer returns additive contributions for the actual fitted
    # LogisticRegression on its raw decision-function (log-odds) scale.
    masker = shap.maskers.Independent(X_dev_scaled)
    explainer = shap.LinearExplainer(classifier, masker)
    explanation = explainer(X_all_scaled)
    contributions = np.asarray(explanation.values).reshape(-1)
    base_values = np.asarray(explanation.base_values)
    if base_values.ndim == 0:
        base_values = np.repeat(float(base_values), len(data))
    else:
        base_values = base_values.reshape(-1)
        if base_values.size == 1:
            base_values = np.repeat(float(base_values[0]), len(data))

    decision_scores = np.asarray(classifier.decision_function(X_all_scaled)).reshape(-1)
    additivity_error = np.abs(base_values + contributions - decision_scores)
    maximum_error = float(additivity_error.max())
    shap_enabled = maximum_error <= ADDITIVITY_TOLERANCE

    shap_table = pd.DataFrame(
        {
            "nct_id": data["nct_id"],
            "shap_base_log_odds": base_values,
            "submission_year_shap_log_odds": contributions,
            "model_decision_log_odds": decision_scores,
            "additivity_error": additivity_error,
            "shap_enabled": shap_enabled,
            "model_version": bundle["model_version"],
        }
    )
    shap_table.to_parquet(ARTEFACTS / "shap_values.parquet", index=False)

    audit = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model_version": bundle["model_version"],
        "explainer": "shap.LinearExplainer",
        "explained_output": "LogisticRegression decision_function (log-odds)",
        "feature": "submission_year",
        "rows": len(shap_table),
        "additivity_equation": "base_log_odds + submission_year_SHAP = model_decision_log_odds",
        "additivity_tolerance": ADDITIVITY_TOLERANCE,
        "maximum_absolute_additivity_error": maximum_error,
        "shap_enabled": shap_enabled,
        "probability_source": "pipeline.predict_proba",
        "final_test_outcomes_accessed": False,
    }
    (ARTEFACTS / "shap_audit.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Saved predictions: {len(predictions)} rows")
    print(f"Maximum SHAP additivity error: {maximum_error:.3e}")
    print(f"SHAP display enabled: {shap_enabled}")
    print("Final-test outcomes accessed: False")


if __name__ == "__main__":
    try:
        score_and_explain()
    except Exception as exc:
        sys.exit(f"ABORT: {exc}")
