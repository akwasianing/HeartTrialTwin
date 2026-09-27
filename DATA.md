# HeartTrialTwin data and artifact instructions

> **Experimental — not validated for clinical decision-making.**

This repository preserves two distinct course-project systems. Their cohorts,
models, and release decisions must not be conflated.

## Final experimental full-system dataset

The final modeling objective is binary classification among heart-failure trials
with observed terminal outcomes:

- Completed = `0`
- Terminated or Withdrawn = `1`

Development uses trials first submitted through 2020 (`n = 2,373`). The frozen
temporal test uses 2021–2024 (`n = 462`: 380 completed and 82 discontinued;
prevalence 0.1775). The temporal test was evaluated once after the model and
research threshold were frozen. Outcome-immature 2025–2026 records are not part
of that evaluation.

The runtime input artifact contains 2,835 unique NCT IDs and exactly 18 columns:
an identifier, submission year, approved structured protocol/design fields, and
eligibility criteria. It contains no outcome, status, error-analysis, or
why-stopped field. The application validates this schema and record count before
scoring.

### Frozen runtime artifacts

| Path | Role |
|---|---|
| `artifacts/hearttrialtwin_final_model.joblib` | Frozen unweighted Logistic Regression pipeline |
| `artifacts/runtime_inputs.parquet` | Exact-NCT, outcome-free runtime inputs |
| `artifacts/runtime_model_manifest.json` | Hashes, versions, threshold, metrics, and runtime policy |
| `artifacts/final_model_summary.json` | Frozen development/test summary |
| `artifacts/training_environment.json` | Serialization environment versions |

Key integrity values:

- Model SHA-256: `a47ef63f5d7408d2525946df57a28e4b781e36c3355bf9ab1840f64c58db8083`
- Runtime-input SHA-256: `e8a00748cadd9aa01526e3cec5bb85b6048204abae0269d594b849da5f8a418e`
- Model version: `hearttrialtwin-final-lr-a47ef63f5d74`
- Frozen research threshold: `0.2129`, selected from development temporal
  out-of-fold predictions only

Current-record numeric enrollment is excluded because its apparent predictive
value was affected by leakage. The retained structured fields and eligibility
text are frozen current-record values and are **not** claimed to reproduce exact
initial-registration versions.

### Offline research results

The following files support audit and reproducibility but are not application
runtime inputs:

- `results/final_temporal_test_predictions.csv`
- `results/development_temporal_oof_predictions.csv`
- `results/final_test_error_analysis.csv`
- `results/shap_global_importance.csv`
- `results/shap_temporal_stability.csv`

The prediction and error-analysis tables contain outcomes. The Streamlit
application does not load them. The test suite reads only `nct_id` and
`predicted_risk` from the frozen temporal-test predictions to verify all 462
scores; it does not refit, tune, or select the model. SHAP and error-analysis
tables are post-hoc interpretation outputs and must not be used for retuning.

The source analysis is preserved as
`notebooks/HeartTrialTwin_Final_Modeling.ipynb`.

## Preserved Challenge 2 dataset

The authoritative Challenge 2 manifest is:

`step3_manifest/HeartTrialTwin_first_p1_cohort_manifest_HTT-P1-AACT-20260905.csv`

- Dataset version: `HTT-P1-AACT-20260905`
- Manifest SHA-256: `5a2d6bbb0973a45988275efb4e9caff8400438edf4e3c560b1b7c0b1688fe7ab`
- AACT snapshot date: 2026-09-05
- Rows and unique NCT IDs: 2,824
- Development: 1,904 (1999–2017)
- Validation: 464 (2018–2020)
- Final test: 456 (2021–2024), labels masked in derived features

`p1_app/feature_build.py` derives the preserved Challenge 2 feature table from
that manifest. Its only model predictor is `submission_year`, and the application
correctly blocks its failed baseline from release. `p1_app/evidence_fetch.py`
performs local exact-NCT provenance lookup; despite its historical filename, it
does not retrieve network data.

Do not alter the manifest, the preserved Challenge 2 artifacts, or the final-test
masking behavior.

## Data-use boundary

- Do not describe either system as estimating absolute prospective risk for all
  newly registered trials.
- Do not substitute current 2026 values for unavailable historical predictor
  versions while claiming registration-time validity.
- Do not use stored outcomes, error types, termination reasons, or post-hoc SHAP
  artifacts in application scoring.
- Do not use the locked temporal-test results to retune features, preprocessing,
  calibration, model settings, or the threshold.
