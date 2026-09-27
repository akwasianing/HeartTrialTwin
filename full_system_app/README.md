# HeartTrialTwin experimental full-system application

This is a separate course-project vertical slice. The published Challenge 2
application under `p1_app/` remains intact.

Workflow:

> NCT ID → exact frozen input → frozen Logistic Regression → experimental
> discontinuation score → additive model explanation → human review

Every score is labeled:

> **Experimental — not validated for clinical decision-making.**

The score and threshold comparison are research/educational outputs, not
clinical or trial-management recommendations.

## Frozen methodology

- Outcome: Completed = 0; Terminated/Withdrawn = 1.
- Development: submission year ≤ 2020.
- Locked temporal test: 2021–2024, evaluated once after model freeze.
- Model: unweighted Logistic Regression.
- Inputs: structured protocol/design fields plus eligibility-criteria TF-IDF.
- Current-record numeric enrollment was excluded after empirical leakage analysis.
- Class weighting was evaluated on development data only; unweighted LR was retained.
- Prospective Platt calibration was evaluated and not retained.
- Threshold `0.2129` was selected from development temporal OOF predictions only.

Locked temporal-test results: PR-AUC 0.3102 versus prevalence 0.1775,
ROC-AUC 0.6017, Brier 0.1433, precision 0.2283, recall 0.5122,
specificity 0.6263, and F1 0.3158.

The protocol/design and eligibility fields are frozen current-record inputs;
they are not claimed to be exact historical registration snapshots. Aggregate
SHAP and error-analysis artifacts are post-hoc evaluation artifacts and are not
used to generate application predictions.

Runtime files are stored under `artifacts/`. Outcome-bearing predictions and
post-hoc analyses are stored separately under `results/`; the application does
not load them.

## Setup and launch

The joblib was serialized with scikit-learn 1.6.1 and cannot be loaded by the
repository's Challenge 2 environment, which uses scikit-learn 1.9.1. Create a
separate environment:

```bash
cd HeartTrialTwin
python3.12 -m venv .venv-full-system
source .venv-full-system/bin/activate
python -m pip install -r requirements-full-system.txt
streamlit run full_system_app/app.py
```

Open `http://localhost:8501` unless Streamlit reports another port.

The training environment used Python 3.13.15. The local Python 3.12.14
compatibility environment reproduced all 462 stored probabilities to machine
precision before this application was enabled.

Run tests:

```bash
python -m pytest full_system_app/tests/test_full_system_app.py -v
```

Run the preserved Challenge 2 tests from its separate `.venv` environment as
documented in the root README.
