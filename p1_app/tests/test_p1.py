"""Eight non-skipped tests for the temporal-baseline safe failure state."""

from __future__ import annotations

import hashlib
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = PROJECT_ROOT / "p1_app"
ARTEFACTS = APP_DIR / "artefacts"
sys.path.insert(0, str(APP_DIR))

from core import get_exact_evidence, get_trial_result, load_runtime, make_review_record
from explain import FORBIDDEN_CLAIMS, generate_failure_explanation


@pytest.fixture(scope="session")
def runtime():
    return load_runtime()


@pytest.fixture(scope="session")
def features():
    return pd.read_parquet(ARTEFACTS / "features.parquet")


@pytest.fixture(scope="session")
def model_bundle():
    with (ARTEFACTS / "model.pkl").open("rb") as handle:
        return pickle.load(handle)


def test_1_valid_nct_selection(runtime):
    predictions, shap_values, evidence_cache, _, _ = runtime
    result, evidence = get_trial_result(
        "nct03414632", predictions, shap_values, evidence_cache
    )
    assert result["nct_id"] == "NCT03414632"
    assert evidence["nct_id"] == "NCT03414632"
    assert int(result["submission_year"]) == evidence["submission_year"] == 2018


def test_2_invalid_nct_id(runtime):
    predictions, shap_values, evidence_cache, _, _ = runtime
    with pytest.raises(KeyError):
        get_trial_result("NCT99999999", predictions, shap_values, evidence_cache)
    with pytest.raises(KeyError):
        get_exact_evidence("NCT99999999", evidence_cache)


def test_3_development_only_training_and_split_integrity(features, model_bundle):
    assert len(features[features.temporal_group == "development"]) == 1904
    assert len(features[features.temporal_group == "validation"]) == 464
    assert len(features[features.temporal_group == "final_test"]) == 456
    assert features.loc[
        features.temporal_group == "final_test", "discontinued"
    ].isna().all()
    assert model_bundle["features"] == ["submission_year"]
    assert model_bundle["training_split"] == "development"
    dev = features[features.temporal_group == "development"]
    expected_hash = hashlib.sha256(
        "\n".join(sorted(dev.nct_id.astype(str))).encode()
    ).hexdigest()
    assert model_bundle["training_ids_sha256"] == expected_hash
    fitted_mean = model_bundle["pipeline"].named_steps["scaler"].mean_[0]
    assert fitted_mean == pytest.approx(dev.submission_year.mean())


def test_4_probability_consistency_and_application_block(runtime, model_bundle):
    predictions, _, _, metrics, _ = runtime
    row = predictions[predictions.nct_id == "NCT03414632"].iloc[0]
    expected = model_bundle["pipeline"].predict_proba(
        pd.DataFrame({"submission_year": [int(row.submission_year)]})
    )[0, 1]
    assert float(row.predicted_probability) == pytest.approx(float(expected), abs=1e-12)
    assert metrics["release_status"] == "FAIL"
    assert not metrics["basic_evaluation_checks"]["auroc_at_least_random_ranking"]
    assert not metrics["basic_evaluation_checks"]["auprc_at_least_validation_prevalence"]

    app = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=20).run()
    assert not app.exception
    error_text = " ".join(element.value for element in app.error)
    assert "risk output is blocked" in error_text.lower()
    metric_labels = [element.label for element in app.metric]
    assert "Predicted discontinuation probability" not in metric_labels
    assert "Submission-year SHAP" not in metric_labels


def test_5_shap_additivity(runtime):
    _, shap_values, _, _, shap_audit = runtime
    reconstructed = (
        shap_values.shap_base_log_odds
        + shap_values.submission_year_shap_log_odds
    )
    error = np.abs(reconstructed - shap_values.model_decision_log_odds)
    assert bool(shap_audit["shap_enabled"])
    assert error.max() <= shap_audit["additivity_tolerance"]
    assert shap_audit["maximum_absolute_additivity_error"] == pytest.approx(
        float(error.max()), abs=1e-18
    )


def test_6_exact_nct_provenance(runtime):
    _, _, evidence_cache, _, _ = runtime
    assert len(evidence_cache) == 2824
    evidence = get_exact_evidence("NCT03414632", evidence_cache)
    assert evidence["study_first_submitted_date"] == "2018-01-23"
    assert evidence["source_field"] == "ctgov.studies.study_first_submitted_date"
    assert evidence["dataset_version"] == "HTT-P1-AACT-20260905"
    assert evidence["source_file_sha256"] == (
        "5a2d6bbb0973a45988275efb4e9caff8400438edf4e3c560b1b7c0b1688fe7ab"
    )
    forbidden = {"discontinued", "overall_status", "why_stopped", "completion_date"}
    assert not (forbidden & set(evidence))


def test_7_failure_explanation_fidelity_and_claim_safety(runtime):
    _, _, evidence_cache, metrics, _ = runtime
    evidence = get_exact_evidence("NCT03414632", evidence_cache)
    explanation = generate_failure_explanation(metrics, evidence)
    text = explanation["text"]
    facts = explanation["numeric_facts"]
    assert facts["validation_auprc"] in text
    assert facts["validation_prevalence"] in text
    assert facts["validation_auroc"] in text
    assert "No trial-level discontinuation probability is presented" in text
    assert "blocks the probability" in text
    assert all(claim not in text.lower() for claim in FORBIDDEN_CLAIMS)


def test_8_missing_evidence_and_functional_revision(runtime):
    _, _, evidence_cache, metrics, _ = runtime
    with pytest.raises(KeyError):
        get_exact_evidence("", evidence_cache)

    evidence = get_exact_evidence("NCT03414632", evidence_cache)
    original = generate_failure_explanation(metrics, evidence)
    revised = generate_failure_explanation(
        metrics, evidence, feedback="Please lead with the performance metrics."
    )
    assert revised["revision_mode"] == "metrics_first_failure_notice"
    assert revised["text"] != original["text"]
    assert revised["numeric_facts"] == original["numeric_facts"]
    record = make_review_record(
        "NCT03414632", "request_revision", "Please lead with the performance metrics.", revised
    )
    assert record["reviewer_comment_is_separate_from_system_text"] is True
    assert record["numeric_facts"] == original["numeric_facts"]
    with pytest.raises(ValueError):
        make_review_record("NCT03414632", "reject", "", original)
