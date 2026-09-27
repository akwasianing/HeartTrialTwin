# HeartTrialTwin

> **Experimental — not validated for clinical decision-making.**

HeartTrialTwin is a graduate data-science course project that studies whether a
heart-failure clinical trial with an observed terminal outcome was completed
(`0`) or terminated/withdrawn (`1`). Its full-system prototype connects a frozen
machine-learning score to transparent model contributions, exact-record evidence,
and human review. The output is a research result—not a clinical recommendation,
a trial-management directive, or an estimate of absolute prospective risk for
all newly registered trials.

## Research questions

1. Can protocol/design fields plus eligibility-criteria text distinguish later
   terminated/withdrawn trials from completed trials in a held-out time period?
2. Can a selected trial's frozen score be explained without changing the model's
   numerical output or making causal claims?
3. Can provenance and human accept/reject/revise controls make the limitations of
   an experimental prediction visible in the interface?

## Final experimental model

The frozen model is an **unweighted Logistic Regression** using structured
protocol/design fields and eligibility-criteria TF-IDF. Current-record numeric
enrollment was excluded after empirical leakage analysis. Balanced and moderate
class weighting were assessed with development data only; the unweighted model
was retained. Prospective Platt calibration was also assessed and not retained.

The development cohort contains 2,373 terminal-outcome trials submitted through
2020. The locked temporal test contains 462 trials submitted in 2021–2024: 380
completed and 82 terminated/withdrawn (prevalence 0.1775). The test was evaluated
once after model and threshold freeze.

| Locked temporal-test measure | Result |
|---|---:|
| PR-AUC | 0.3102 |
| Prevalence / no-skill PR-AUC | 0.1775 |
| PR-AUC gain over prevalence | 0.1327 |
| ROC-AUC | 0.6017 |
| Brier score | 0.1433 |
| Mean predicted score | 0.2001 |

The research threshold, **0.2129**, was selected from development temporal
out-of-fold predictions only. At that threshold, the frozen test results were
precision 0.2283, recall 0.5122, specificity 0.6263, and F1 0.3158 (TN 238,
FP 142, FN 40, TP 42). It is not an operational or clinical decision threshold.

## Full-system vertical slice

> NCT ID → frozen input record → frozen model → experimental discontinuation
> score → additive contributions and evidence → human review

The Streamlit interface:

- retrieves one exact NCT ID from an outcome-free runtime input artifact;
- verifies model, input, summary, and environment hashes before loading;
- reproduces the frozen Logistic Regression score;
- shows exact additive log-odds contributions for structured fields and TF-IDF
  terms, with non-causal wording;
- shows model/data version, source values, missing-evidence flags, and the required
  experimental-use disclaimer; and
- records an accept, reject, or request-revision review separately from the
  immutable score and numerical explanation facts.

Aggregate SHAP and error-analysis outputs are included as post-hoc research
results. They are not loaded by the application and were not used to retune the
frozen model.

## Important data limitation

The final prototype uses frozen **current-record** protocol/design fields and
eligibility text. These values are not claimed to be exact historical
initial-registration snapshots. The project therefore reports conditional,
experimental classification performance on terminal-outcome trials and does not
claim validated prospective deployment performance. See [DATA.md](DATA.md) for
the data boundary and artifact provenance.

## Repository structure

```text
artifacts/          Frozen model, outcome-free runtime inputs, and manifests
results/            Offline evaluation predictions, SHAP, and error analyses
full_system_app/    Final experimental Streamlit application and 11 tests
p1_app/             Preserved Challenge 2 release-readiness vertical slice
notebooks/          Final modeling notebook
step3_manifest/     Frozen Challenge 2 cohort manifest and validation code
deliverables/       Course deliverables retained for reference
```

## Run the full-system prototype

The model was serialized with scikit-learn 1.6.1 under Python 3.13.15. It has
also been verified locally with Python 3.12.14 and the pinned full-system
dependencies.

```bash
git clone https://github.com/akwasianing/HeartTrialTwin.git
cd HeartTrialTwin
python3.12 -m venv .venv-full-system
source .venv-full-system/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-full-system.txt
streamlit run full_system_app/app.py
```

Open `http://localhost:8501` unless Streamlit reports another port.

Run the full-system integrity and reproducibility tests:

```bash
python -m pytest full_system_app/tests/test_full_system_app.py -v
```

The application loads the frozen artifacts; it does not retrain the model.

## Preserved Challenge 2 vertical slice

`p1_app/` is the separately preserved Challenge 2 submission. Its submission-year
baseline failed validation (AUPRC 0.228136 versus prevalence 0.232759; AUROC
0.484108), so that application correctly blocks trial-level probability, SHAP,
and risk explanation. It remains reproducible and unchanged; it must not be
confused with the later experimental full-system model.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run p1_app/app.py
python -m pytest p1_app/tests/test_p1.py -v
```

The preserved Challenge 2 workflow and its blocked-release rationale are
documented in [p1_app/TEST_RESULTS.md](p1_app/TEST_RESULTS.md) and
[p1_app/feature_audit.md](p1_app/feature_audit.md).

## Reproducibility and integrity

- Frozen model SHA-256:
  `a47ef63f5d7408d2525946df57a28e4b781e36c3355bf9ab1840f64c58db8083`
- Runtime-input SHA-256:
  `e8a00748cadd9aa01526e3cec5bb85b6048204abae0269d594b849da5f8a418e`
- The full-system suite checks all 462 stored temporal-test probabilities against
  newly generated scores to machine precision.
- Outcome-bearing evaluation tables remain offline research results and are never
  loaded by the Streamlit scoring path.

## Limitations and intended use

- The cohort includes trials with observed terminal outcomes only.
- Current-record fields may reflect amendments after initial registration.
- Discrimination is modest, and thresholded precision is low.
- Model contributions are associations on the Logistic Regression log-odds scale,
  not causes of discontinuation.
- The prototype is for research and education only and must not guide clinical,
  regulatory, or trial-management decisions.

Repository: <https://github.com/akwasianing/HeartTrialTwin>
