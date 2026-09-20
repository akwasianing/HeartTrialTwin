# HeartTrialTwin — Challenge 2

Repository: <https://github.com/akwasianing/HeartTrialTwin>

## Working Human–AI task

**Model-release readiness review for a selected clinical trial.**

The implemented workflow is:

> Human selects an NCT ID → application retrieves exact-record provenance → checks model validation and release status → displays a grounded release-readiness result and uncertainty → human accepts, rejects, or requests revision.

This task is narrower than the planned HeartTrialTwin P1 capability. The application does not perform clinical risk prediction, trial-design analysis, runtime RAG, or LLM-generated explanation.

## What the application does

For an eligible NCT ID, the Streamlit application displays:

- frozen-cohort membership and exact registration-submission provenance;
- the model release status and actual validation metrics;
- bootstrap uncertainty intervals and historical-data limitations;
- a deterministic explanation of why the risk output is blocked; and
- accept, reject, and revision controls for human review.

The review log is session-only. A reviewer must download it before reloading or closing the browser.

## AI capability and release decision

A Logistic Regression baseline was trained on the 1999–2017 development group using only the verified `submission_year` predictor. It was evaluated on the 2018–2020 validation group. SHAP calculations were also checked for numerical additivity on the log-odds scale.

The model was **trained and evaluated but rejected for operational release**:

| Validation measure | Result |
|---|---:|
| AUPRC | 0.228136 |
| Validation prevalence / no-skill AUPRC | 0.232759 |
| AUROC | 0.484108 |
| Brier score | 0.178645 |

Because AUPRC was below prevalence and AUROC was below 0.5, the application blocks the selected-trial probability, SHAP attribution, and risk explanation. The visible output is a deterministic release-readiness explanation grounded in the stored validation metrics and selected trial's verified provenance. It is not an LLM-generated explanation or a clinically validated prediction.

The 2021–2024 final-test group remains locked and was not evaluated.

## Data

- Dataset version: `HTT-P1-AACT-20260905`
- Frozen AACT cohort: 2,824 trials
- Development: 1,904 trials, 1999–2017
- Validation: 464 trials, 2018–2020
- Final test: 456 trials, 2021–2024, labels masked in derived features
- Sole model predictor: `submission_year`

See [DATA.md](DATA.md) and [p1_app/feature_audit.md](p1_app/feature_audit.md) for provenance, leakage controls, and historical-data limitations.

## Fresh-clone setup

Python 3.12 is required for this reproducible setup because the committed model artifact was created and tested with Python 3.12 and the pinned packages in `requirements.txt`.

### macOS or Linux

```bash
git clone https://github.com/akwasianing/HeartTrialTwin.git
cd HeartTrialTwin
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run p1_app/app.py
```

### Windows PowerShell

```powershell
git clone https://github.com/akwasianing/HeartTrialTwin.git
cd HeartTrialTwin
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run p1_app/app.py
```

Keep the Streamlit server running and open `http://localhost:8501` in a browser. Streamlit will report a different URL if port 8501 is unavailable.

Run the tests after activating the environment:

```bash
python -m pytest p1_app/tests/test_p1.py -v
```

The application runs from the committed artifacts. Retraining is not required for the Challenge 2 demonstration.

## Agentic AI implementation and human oversight

Codex served as the agentic AI implementation partner. Its documented contributions included repository and data audits, scoped code implementation, debugging, automated test execution, provenance checks, Streamlit workflow verification, screenshot capture, presentation preparation, and Git publication preparation.

Human oversight controlled the work. The project owner reviewed and approved the task scope, methodological constraints, frozen cohort, validation evidence, blocked-output policy, test evidence, and GitHub publication. This statement does not claim that the project owner performed a line-by-line code review.

No autonomous agent, LLM, or RAG system runs inside the Streamlit application.

## Tests

Eight tests cover valid and invalid NCT lookup, split integrity, probability consistency, application blocking, SHAP additivity, provenance, explanation safety, missing evidence, and functional revision. Current result: **8 passed, 0 failed, 0 skipped**.

See [p1_app/TEST_RESULTS.md](p1_app/TEST_RESULTS.md).

## What remains to be developed

- Obtain scalable, verified registration-time predictors beyond submission year.
- Train and validate a useful multifeature discontinuation-risk model.
- Release probability and SHAP output only after defensible validation.
- Build a grounded risk explanation from verified trial evidence.
- Add durable review storage if the application moves beyond a local demonstration.

Submission year alone did not generalize to the later validation period and does not represent clinical, design, enrollment, sponsor, or operational factors.
