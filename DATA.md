# HeartTrialTwin data instructions

## Frozen cohort

The authoritative manifest is:

`step3_manifest/HeartTrialTwin_first_p1_cohort_manifest_HTT-P1-AACT-20260905.csv`

- Dataset version: `HTT-P1-AACT-20260905`
- Manifest SHA-256: `5a2d6bbb0973a45988275efb4e9caff8400438edf4e3c560b1b7c0b1688fe7ab`
- AACT snapshot date: 2026-09-05
- Rows and unique NCT IDs: 2,824

Do not alter this manifest, the original cohort notebook, or Step-2 reconciliation artifacts.

## Safe predictor

The temporal baseline uses only:

`submission_year = year(study_first_submitted_date)`

The exact submission date, NCT ID, dataset version, source file, and source field are retained for provenance. They are not additional predictors.

## Derived artifacts

`p1_app/feature_build.py` creates `p1_app/artefacts/features.parquet` and masks every final-test outcome. Development and validation labels remain available for fitting and assessment. Current snapshot values for phase, enrollment, sponsor, title, eligibility, dates, results, and outcome information are excluded.

`p1_app/evidence_fetch.py` is local-only despite its historical filename. It performs no network retrieval and creates exact-NCT provenance from the frozen manifest without outcome fields.

## Historical-data limitation

The outcome-blind 18-record pilot is preserved under `historical_retrieval_pilot/`. It retrieved zero historical record payloads programmatically. Current AACT values must not be substituted for missing initial-registration values.

## Final-test lock

The 2021–2024 final-test group contains 456 trials. Its labels are masked in the derived feature table. Training, validation metrics, thresholds, SHAP verification, tests, and the Streamlit application do not evaluate final-test outcomes.
