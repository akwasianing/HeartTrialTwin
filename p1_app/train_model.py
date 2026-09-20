#!/usr/bin/env python3
"""Train and validate the one-predictor Logistic Regression baseline."""

from __future__ import annotations

import hashlib
import json
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ARTEFACTS = Path(__file__).resolve().parent / "artefacts"
FEATURES = ["submission_year"]
LABEL = "discontinued"
MODEL_VERSION = "HTT-TEMPORAL-LR-v1"
DATASET_VERSION = "HTT-P1-AACT-20260905"
RANDOM_SEED = 5588


def sha256_ids(values: pd.Series) -> str:
    payload = "\n".join(sorted(values.astype(str))).encode()
    return hashlib.sha256(payload).hexdigest()


def bootstrap_intervals(
    y_true: np.ndarray, probabilities: np.ndarray, repetitions: int = 1000
) -> dict[str, list[float]]:
    rng = np.random.default_rng(RANDOM_SEED)
    values: dict[str, list[float]] = {"auprc": [], "auroc": [], "brier_score": []}
    for _ in range(repetitions):
        indices = rng.integers(0, len(y_true), len(y_true))
        y_sample = y_true[indices]
        p_sample = probabilities[indices]
        if np.unique(y_sample).size < 2:
            continue
        values["auprc"].append(average_precision_score(y_sample, p_sample))
        values["auroc"].append(roc_auc_score(y_sample, p_sample))
        values["brier_score"].append(brier_score_loss(y_sample, p_sample))
    return {
        key: [round(float(x), 6) for x in np.percentile(samples, [2.5, 97.5])]
        for key, samples in values.items()
    }


def year_metrics(validation: pd.DataFrame, probabilities: np.ndarray) -> dict[str, dict]:
    result: dict[str, dict] = {}
    working = validation.copy()
    working["probability"] = probabilities
    for year, group in working.groupby("submission_year"):
        y = group[LABEL].astype(int).to_numpy()
        p = group["probability"].to_numpy()
        metrics = {
            "rows": int(len(group)),
            "discontinued": int(y.sum()),
            "prevalence": round(float(y.mean()), 6),
            "auprc": round(float(average_precision_score(y, p)), 6),
            "brier_score": round(float(brier_score_loss(y, p)), 6),
        }
        metrics["auroc"] = (
            round(float(roc_auc_score(y, p)), 6) if np.unique(y).size == 2 else None
        )
        result[str(int(year))] = metrics
    return result


def train() -> None:
    feature_path = ARTEFACTS / "features.parquet"
    if not feature_path.exists():
        raise RuntimeError("features.parquet is missing; run feature_build.py first")
    data = pd.read_parquet(feature_path)

    if FEATURES != ["submission_year"]:
        raise RuntimeError("Temporal baseline must use exactly one predictor")
    if data.loc[data.temporal_group == "final_test", LABEL].notna().any():
        raise RuntimeError("Final-test labels are visible; training aborted")

    development = data[data.temporal_group == "development"].copy()
    validation = data[data.temporal_group == "validation"].copy()
    if development[LABEL].isna().any() or validation[LABEL].isna().any():
        raise RuntimeError("Development or validation labels are missing")

    X_dev = development[FEATURES]
    y_dev = development[LABEL].astype(int)
    X_val = validation[FEATURES]
    y_val = validation[LABEL].astype(int)

    # StandardScaler is fitted inside the pipeline using development data only.
    pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "logistic_regression",
                LogisticRegression(
                    penalty="l2",
                    solver="lbfgs",
                    class_weight=None,
                    random_state=RANDOM_SEED,
                    max_iter=1000,
                ),
            ),
        ]
    )
    pipeline.fit(X_dev, y_dev)
    probabilities = pipeline.predict_proba(X_val)[:, 1]

    auprc = float(average_precision_score(y_val, probabilities))
    auroc = float(roc_auc_score(y_val, probabilities))
    brier = float(brier_score_loss(y_val, probabilities))
    prevalence = float(y_val.mean())

    precision_values, recall_values, thresholds = precision_recall_curve(y_val, probabilities)
    f1 = 2 * precision_values[:-1] * recall_values[:-1] / np.maximum(
        precision_values[:-1] + recall_values[:-1], 1e-12
    )
    threshold_index = int(np.nanargmax(f1))
    selected_threshold = float(thresholds[threshold_index])
    predicted_class = (probabilities >= selected_threshold).astype(int)

    computational_checks = {
        "predictor_exactly_submission_year": FEATURES == ["submission_year"],
        "development_rows_1904": len(development) == 1904,
        "validation_rows_464": len(validation) == 464,
        "final_labels_masked": not data.loc[
            data.temporal_group == "final_test", LABEL
        ].notna().any(),
        "preprocessor_fit_on_development_only": True,
        "probabilities_finite": bool(np.isfinite(probabilities).all()),
        "probabilities_in_unit_interval": bool(
            ((probabilities >= 0.0) & (probabilities <= 1.0)).all()
        ),
        "validation_has_both_classes": y_val.nunique() == 2,
    }
    evaluation_checks = {
        "auroc_at_least_random_ranking": auroc >= 0.5,
        "auprc_at_least_validation_prevalence": auprc >= prevalence,
    }
    release_status = "PASS" if all(computational_checks.values()) and all(
        evaluation_checks.values()
    ) else "FAIL"

    bundle = {
        "pipeline": pipeline,
        "model_version": MODEL_VERSION,
        "dataset_version": DATASET_VERSION,
        "features": FEATURES,
        "training_split": "development",
        "training_ids_sha256": sha256_ids(development.nct_id),
        "validation_ids_sha256": sha256_ids(validation.nct_id),
        "release_status": release_status,
    }
    model_path = ARTEFACTS / "model.pkl"
    with model_path.open("wb") as handle:
        pickle.dump(bundle, handle)

    coefficient = float(
        pipeline.named_steps["logistic_regression"].coef_.reshape(-1)[0]
    )
    intercept = float(
        pipeline.named_steps["logistic_regression"].intercept_.reshape(-1)[0]
    )
    scaler = pipeline.named_steps["scaler"]
    metrics = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset_version": DATASET_VERSION,
        "model_version": MODEL_VERSION,
        "model_type": "StandardScaler + LogisticRegression",
        "predictors": FEATURES,
        "class_weight": None,
        "release_status": release_status,
        "computational_integrity_checks": computational_checks,
        "basic_evaluation_checks": evaluation_checks,
        "splits": {
            "development": {
                "rows": int(len(development)),
                "discontinued": int(y_dev.sum()),
            },
            "validation": {
                "rows": int(len(validation)),
                "discontinued": int(y_val.sum()),
            },
            "final_test": {
                "rows": int((data.temporal_group == "final_test").sum()),
                "labels_used": False,
                "evaluated": False,
            },
        },
        "validation_metrics": {
            "auprc": round(auprc, 6),
            "auroc": round(auroc, 6),
            "brier_score": round(brier, 6),
            "prevalence_no_skill_auprc": round(prevalence, 6),
            "validation_derived_f1_threshold": round(selected_threshold, 6),
            "precision_at_threshold": round(
                float(precision_score(y_val, predicted_class, zero_division=0)), 6
            ),
            "recall_at_threshold": round(
                float(recall_score(y_val, predicted_class, zero_division=0)), 6
            ),
            "f1_at_threshold": round(float(f1[threshold_index]), 6),
        },
        "bootstrap_95_percent_intervals": bootstrap_intervals(
            y_val.to_numpy(), probabilities
        ),
        "validation_metrics_by_submission_year": year_metrics(validation, probabilities),
        "fitted_parameters_on_standardized_year": {
            "coefficient": coefficient,
            "intercept": intercept,
            "development_year_mean": float(scaler.mean_[0]),
            "development_year_scale": float(scaler.scale_[0]),
        },
        "limitations": [
            "Submission year is the only predictor.",
            "The model cannot represent trial design, enrollment, sponsor, clinical, or operational factors.",
            "Association with calendar time is not causal.",
            "The final-test split has not been evaluated.",
            "This is a technical proof of concept, not a clinically validated prediction system.",
        ],
    }
    (ARTEFACTS / "validation_metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    (ARTEFACTS / "model_card.json").write_text(
        json.dumps(
            {
                "model_version": MODEL_VERSION,
                "dataset_version": DATASET_VERSION,
                "intended_use": "Temporal baseline / technical proof of concept",
                "not_intended_for": "Clinical decisions or multifeature risk assessment",
                "predictors": FEATURES,
                "training_split": "development (1999-2017)",
                "validation_split": "validation (2018-2020)",
                "final_test_status": "locked and not evaluated",
                "release_status": release_status,
                "training_ids_sha256": bundle["training_ids_sha256"],
                "validation_ids_sha256": bundle["validation_ids_sha256"],
                "limitations": metrics["limitations"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Model version: {MODEL_VERSION}")
    print(f"Validation AUPRC: {auprc:.6f} (prevalence {prevalence:.6f})")
    print(f"Validation AUROC: {auroc:.6f}")
    print(f"Validation Brier: {brier:.6f}")
    print(f"Release status: {release_status}")
    print("Final-test labels used: False")


if __name__ == "__main__":
    try:
        train()
    except Exception as exc:
        sys.exit(f"ABORT: {exc}")
