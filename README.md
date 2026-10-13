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

## Challenge 3: AI Design — Knowledge Graph with Neo4j

### Objective and data selection

Challenge 3 adds a Neo4j knowledge graph for exploring connections among
heart-failure trials, submitted and browse conditions, interventions, lead
sponsors, registered planned outcomes, and source provenance. It is a semantic
research layer and does not change the frozen predictive model or its results.

The graph is grounded in the pinned September 5, 2026 AACT/ClinicalTrials.gov
dataset, `HTT-P1-AACT-20260905`, whose authoritative cohort contains 2,824
trials. A deterministic, outcome-blind procedure retained trials with a
submitted condition, a named intervention, a named lead sponsor, and at least
two planned outcomes. It ranked shared condition/intervention pairs by support
and stable lexical tie-breaks, then selected the first five NCT IDs from the
highest-ranked eligible pair. Trial status, outcome labels, predictions, and
model performance were not used. The shared **Heart Failure** submitted
condition and **DRUG — Spironolactone** intervention emerged from this process.

### Verified graph schema

| Node label | Count |
|---|---:|
| `Trial` | 5 |
| `ConditionTerm` | 4 |
| `Intervention` | 1 |
| `Sponsor` | 5 |
| `PlannedOutcome` | 10 |
| `SourceDataset` | 1 |

The seven relationship types are `HAS_SUBMITTED_CONDITION`,
`HAS_BROWSE_CONDITION`, `HAS_INTERVENTION`, `LEAD_SPONSORED_BY`,
`HAS_PLANNED_OUTCOME`, `MEMBER_OF_DATASET`, and `SOURCED_FROM`. Submitted
conditions and browse-condition terms remain source-distinct. Prediction,
Evidence, HumanReview, and GraphRAG nodes were intentionally deferred.

### Preparation, import, and validation

The [CSV preparation script](artifacts/knowledge_graph/prepare_neo4j_import.py)
uses the pinned cohort and verified AACT archive members, applies conservative
normalization, preserves source identifiers and provenance, and writes separate
node and relationship CSVs. The
[Neo4j importer](artifacts/knowledge_graph/import_to_neo4j.py) uses the official
Python driver, uniqueness constraints, parameterized Cypher, and `MERGE`; it
imports all node types before relationships and performs post-import integrity
checks. File hashes, archive metadata, selection rules, and expected counts are
recorded in the
[graph import manifest](artifacts/knowledge_graph/graph_import_manifest.json).

The verified graph contains **26 nodes and 65 relationships**. All node IDs are
unique within type, every relationship endpoint exists, all five trials belong
to the pinned cohort, the graph is fully connected, and shared-condition and
shared-intervention traversal paths are present. See the complete
[validation report](artifacts/knowledge_graph/VALIDATION_REPORT.md).

### Research demonstrations

The Neo4j evidence captures the
[full graph visualization](artifacts/knowledge_graph/Neo4j_Evidence/screenshots/HeartTrialTwin_Full_Knowledge_Graph.png),
[shared condition/intervention comparison](artifacts/knowledge_graph/Neo4j_Evidence/screenshots/shared%20condition%20and%20intervention.png),
[sponsor analysis](artifacts/knowledge_graph/Neo4j_Evidence/screenshots/sponsor%20analysis.png),
[planned-outcome comparison](artifacts/knowledge_graph/Neo4j_Evidence/screenshots/planned%20outcome%20across%20trials%20.png),
[multi-hop trial comparison](artifacts/knowledge_graph/Neo4j_Evidence/screenshots/multti%20hop%20tial%20comparison.png),
and [dataset-provenance validation](artifacts/knowledge_graph/Neo4j_Evidence/screenshots/dataset%20provenance.png).
Together, these demonstrations show how shared clinical concepts support
cross-trial exploration while retaining exact links to the pinned source.

### Human–AI collaboration

Codex assisted with semantic-design critique, source reconciliation, schema
preparation, and reproducibility checks. Human review retained final authority
over the approved entities, relationships, provenance safeguards, and validation
criteria. The design record is preserved in the
[Challenge 3 semantic-design notebook](notebooks/HeartTrialTwin_Challenge3_Semantic_Design.ipynb).

### Reproduce the Neo4j import

Create an isolated environment, install the pinned dependencies, and copy the
credential template to a local `.env` file. Fill that file privately; never
commit connection credentials.

```bash
python3 -m venv /tmp/hearttrialtwin-neo4j
source /tmp/hearttrialtwin-neo4j/bin/activate
python -m pip install -r artifacts/knowledge_graph/requirements-neo4j.txt
cp artifacts/knowledge_graph/.env.example artifacts/knowledge_graph/.env
python artifacts/knowledge_graph/import_to_neo4j.py
python artifacts/knowledge_graph/import_to_neo4j.py \
  --execute --confirm-database <exact-database-name>
```

The first importer command performs local file and manifest validation without
connecting to Neo4j. The executing command requires the exact target database
name and reads connection settings from the ignored local `.env` file. See the
[dependency pins](artifacts/knowledge_graph/requirements-neo4j.txt) and
[environment template](artifacts/knowledge_graph/.env.example).

### Challenge 3 limitations

- The five-trial graph is illustrative and is not statistically representative
  of the full 2,824-trial cohort.
- `PlannedOutcome` nodes describe registered planned measures, not clinical
  results or evidence of a terminal trial status.
- GraphRAG was deferred; this challenge implements a verified knowledge graph,
  not a retrieval-augmented generation system.

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
