# HeartTrialTwin — Temporal Baseline / Technical Proof of Concept

HeartTrialTwin is a CS 5588 Challenge 2 prototype exploring three P1 mechanics:

1. Estimate heart-failure trial discontinuation risk.
2. Attribute the model score with SHAP.
3. Ground an explanation in exact-NCT project evidence and collect human review.

## Current checkpoint: safe failure

The historically verified multifeature model was deferred because the approved retrieval pilot could not obtain initial ClinicalTrials.gov records programmatically at scale. A one-predictor Logistic Regression baseline was then trained using only verified `submission_year`.

That baseline **failed its predeclared validation release checks**:

| Validation measure | Result |
|---|---:|
| AUPRC | 0.228136 |
| Validation prevalence / no-skill AUPRC | 0.232759 |
| AUROC | 0.484108 |
| Brier score | 0.178645 |

Because AUPRC was below prevalence and AUROC was below 0.5, the Streamlit application blocks the selected-trial probability, SHAP attribution, and risk explanation. It instead demonstrates exact-NCT provenance, a grounded safety explanation, and functional accept/reject/revision review. This is not a clinically validated system.

The final-test split (2021–2024) remains locked and was not evaluated.

## Data and splits

- Dataset version: `HTT-P1-AACT-20260905`
- Frozen cohort: 2,824 trials
- Development: 1,904 trials, 1999–2017
- Validation: 464 trials, 2018–2020
- Final test: 456 trials, 2021–2024, labels masked in derived features
- Sole predictor: `submission_year`

See [DATA.md](DATA.md) and [p1_app/feature_audit.md](p1_app/feature_audit.md).

## Run locally

Use the existing project environment:

```bash
.venv/bin/python -m pytest p1_app/tests/test_p1.py -v
.venv/bin/streamlit run p1_app/app.py
```

To reproduce the already completed pipeline in order:

```bash
.venv/bin/python p1_app/feature_build.py
.venv/bin/python p1_app/train_model.py
.venv/bin/python p1_app/score_all.py
.venv/bin/python p1_app/evidence_fetch.py
```

`train_model.py` reads development and validation rows only. It checks that final-test labels are masked and does not evaluate them.

## SHAP integrity

`shap.LinearExplainer` was applied to the fitted Logistic Regression on the standardized submission year. The maximum observed error in

```text
base log-odds + submission-year SHAP = model decision log-odds
```

was `2.220446049250313e-16`, below the `1e-8` tolerance. Although the calculation is internally consistent, the app does not display trial-level SHAP because the model failed validation release checks.

## Tests

Eight tests cover valid and invalid NCT lookup, split integrity, probability consistency, application blocking, SHAP additivity, provenance, explanation safety, missing evidence, and human revision. Current result: **8 passed, 0 failed, 0 skipped**.

See [p1_app/TEST_RESULTS.md](p1_app/TEST_RESULTS.md).

## Limitations

- Submission year alone did not generalize adequately to the later validation period.
- Calendar year is not a causal or clinical risk factor.
- The prototype cannot assess design, enrollment, sponsor, operational, or clinical factors.
- Historical multifeature records were unavailable through an approved scalable retrieval method.
- No LLM, RAG, vector database, agent, PDF model, or multimodal model is used.
- No repository has been pushed to GitHub at this checkpoint.
