"""Integrity, reproducibility, explanation, and review tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = PROJECT_ROOT / "full_system_app"
sys.path.insert(0, str(APP_DIR))

from explanation import FORBIDDEN_CLAIMS, generate_explanation, make_review_record
from runtime import (
    DISCLAIMER,
    EXPECTED_SCHEMA,
    FORBIDDEN_COLUMNS,
    THRESHOLD,
    get_trial_input,
    load_runtime,
    score_trial,
    sha256_file,
)


@pytest.fixture(scope="session")
def bundle():
    return load_runtime()


@pytest.fixture(scope="session")
def stored_predictions():
    return pd.read_csv(
        PROJECT_ROOT / "results" / "final_temporal_test_predictions.csv",
        usecols=["nct_id", "predicted_risk"],
    )


def test_01_frozen_model_hash(bundle):
    path = PROJECT_ROOT / "artifacts" / bundle.manifest["model_file"]
    assert sha256_file(path) == bundle.manifest["model_sha256"]
    assert bundle.manifest["model_sha256"] == (
        "a47ef63f5d7408d2525946df57a28e4b781e36c3355bf9ab1840f64c58db8083"
    )


def test_02_compatible_model_load(bundle):
    assert bundle.model.__class__.__name__ == "Pipeline"
    assert bundle.model.named_steps["model"].__class__.__name__ == "LogisticRegression"
    assert bundle.model.named_steps["model"].class_weight is None


def test_03_runtime_schema_and_outcome_absence(bundle):
    assert len(bundle.inputs) == 2835
    assert bundle.inputs["nct_id"].is_unique
    assert list(bundle.inputs.columns) == EXPECTED_SCHEMA
    assert not (FORBIDDEN_COLUMNS & set(bundle.inputs.columns))


def test_04_exact_nct_lookup(bundle, stored_predictions):
    nct_id = stored_predictions.iloc[0]["nct_id"]
    row = get_trial_input(bundle, nct_id.lower())
    assert len(row) == 1
    assert row.iloc[0]["nct_id"] == nct_id


def test_05_reproduced_final_test_scores(bundle, stored_predictions):
    selected = stored_predictions[["nct_id"]].merge(
        bundle.inputs, on="nct_id", how="left", validate="one_to_one"
    )
    probability = bundle.model.predict_proba(
        selected[list(bundle.model.feature_names_in_)]
    )[:, 1]
    difference = np.abs(probability - stored_predictions["predicted_risk"].to_numpy())
    assert len(probability) == 462
    assert float(difference.max()) <= 1e-12
    assert float(difference.mean()) <= 1e-13


def test_06_threshold_is_frozen(bundle):
    assert THRESHOLD == 0.2129
    assert bundle.manifest["threshold"] == 0.2129
    assert "development temporal out-of-fold" in bundle.manifest["threshold_provenance"]


def test_07_local_contribution_additivity(bundle, stored_predictions):
    result = score_trial(bundle, stored_predictions.iloc[0]["nct_id"])
    assert result["additivity_error"] <= 1e-10
    assert result["reconstructed_log_odds"] == pytest.approx(
        result["decision_log_odds"], abs=1e-10
    )


def test_08_explanation_is_noncausal(bundle, stored_predictions):
    result = score_trial(bundle, stored_predictions.iloc[0]["nct_id"])
    explanation = generate_explanation(result)
    text = explanation["text"].casefold()
    assert "contributed" in text
    assert "do not establish causation" in text
    assert DISCLAIMER.casefold() in text
    assert all(claim not in text for claim in FORBIDDEN_CLAIMS)


def test_09_invalid_nct_handling(bundle):
    with pytest.raises(KeyError):
        get_trial_input(bundle, "NCT99999999")
    with pytest.raises(KeyError):
        get_trial_input(bundle, "")


def test_10_human_review_is_separate(bundle, stored_predictions):
    result = score_trial(bundle, stored_predictions.iloc[0]["nct_id"])
    original = generate_explanation(result)
    revised = generate_explanation(result, "Please make this concise.")
    assert revised["numeric_facts"] == original["numeric_facts"]
    record = make_review_record(result["nct_id"], "request_revision", "Be concise", revised)
    assert record["review_is_separate_from_prediction"] is True
    assert record["numeric_facts"] == original["numeric_facts"]
    with pytest.raises(ValueError):
        make_review_record(result["nct_id"], "reject", "", original)


def test_11_runtime_does_not_load_outcome_or_error_artifacts():
    runtime_source = (APP_DIR / "runtime.py").read_text(encoding="utf-8")
    app_source = (APP_DIR / "app.py").read_text(encoding="utf-8")
    for forbidden_filename in (
        "final_temporal_test_predictions.csv",
        "final_test_error_analysis.csv",
        "development_temporal_oof_predictions.csv",
    ):
        assert forbidden_filename not in runtime_source
        assert forbidden_filename not in app_source
    manifest = json.loads(
        (PROJECT_ROOT / "artifacts" / "runtime_model_manifest.json").read_text()
    )
    assert manifest["runtime_policy"]["outcomes_available_to_application"] is False
    assert manifest["runtime_policy"]["error_analysis_used_by_application"] is False
