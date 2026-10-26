# HeartTrialTwin

> **Experimental — not validated for clinical decision-making.**

## Challenge 3: HeartTrialTwin — Human, AI, and Human–AI Co-Design of an Evidence-Grounded Clinical Trial Research System

The later Challenge 3 implementation is a **registered-information retrieval
system**, separate from the experimental classification applications documented
below. Human semantic modeling, AI-assisted design and critique, and human-led
corrections produced a provenance-preserving Neo4j graph, read-only GraphRAG,
MiniLM semantic discovery, and a local Streamlit research demonstration.
It does not infer observed treatment effects, patient outcomes, or validated
clinical predictions from registered planned outcomes.

### Assignment demonstration versus later extensions

The original five-trial assignment graph has **26 nodes and 65 relationships**;
its evidence and original GraphRAG remain intact. The later full-cohort extension
uses every member of the frozen `HTT-P1-AACT-20260905` cohort, without selecting
trials for outcome availability. Both use the **September 5, 2026** AACT snapshot;
snapshot values may include amendments and are not certified initial-registration
values. The cohort is terminal-outcome-selected, not all newly registered trials.

| Verified full-cohort component | Result |
|---|---:|
| Clinical trials | 2,824 |
| Neo4j nodes | 28,777 |
| Original relationships | 79,125 |
| Registered planned-outcome associations | 19,740 |
| Offline final-audit tests | 220 passed; 0 failures/errors/skips |

Counts and source identity are recorded in the
[full-cohort manifest](artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1/full_cohort_manifest.json)
and [coverage report](artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1/COVERAGE_REPORT.md).

The six labels remain `Trial`, `ConditionTerm`, `Intervention`, `Sponsor`,
`PlannedOutcome`, and `SourceDataset`. Submitted and browse conditions remain
distinct. Missing source records are explicit: 253 trials lack browse terms and
41 lack planned-outcome rows; a missing record is not evidence of absence.

### Architecture, evidence, and human review

```text
Exact NCT lookup ───────────────────────────┐
Question → pinned MiniLM → ranked trial IDs ┤
                                           ↓
                     bounded, read-only Neo4j retrieval
                                           ↓
                     validated trial-bound evidence and citations
                                           ↓
         deterministic facts / complete planned-outcome listings
              or optional constrained local Ollama explanation
                                           ↓
                     grounded answer or explicit abstention
                                           ↓
                              human evidence review
```

MiniLM ranks all 2,824 candidates using normalized 384-dimensional vectors from
`sentence-transformers/all-MiniLM-L6-v2`, revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41` (256-token effective limit).
Similarity is not factual or clinical evidence. Exact-NCT questions bypass
semantic ranking; bounded discovery retains original ranks and records candidates
skipped for insufficient evidence. Neo4j supplies the authoritative facts.

Simple factual answers are assembled deterministically with trial-bound citations.
Complete outcome listing returns all seven verified records for NCT00206232,
not a model-selected subset. Optional Ollama `qwen2.5:1.5b` selects authorized
catalog facts in one bounded attempt; invalid citations, incomplete evidence,
unsupported claims, and clinical-effectiveness questions fail closed.
Human review drove these corrections after slow or incomplete model responses;
it is not an independent clinical/scientific validation or a new durable review
database. Registered planned outcomes are **not observed clinical results**.

### Experimental GraphSAGE: negative comparison retained

The frozen Version 2 experiment ranks registered planned-outcome-to-trial
associations within an **observed graph**, not previously unseen-trial induction.
It uses 1,976 training, 424 validation, and 424 test trials; all 2,824 trials
remain ranking candidates. Target associations and computational reverses are
masked, leaving **61,218** permitted message edges. Conservative family controls,
query embargoes, and incomplete screening limitations remain documented.

| Frozen test comparison (descriptive, not new model selection) | MRR | Recall@10 |
|---|---:|---:|
| TF-IDF | 0.07074 | 0.11492 |
| MiniLM | 0.07619 | 0.12078 |
| Context pooling | 0.07841 | 0.12100 |
| Trained GraphSAGE | 0.01124 | 0.02208 |

GraphSAGE did **not** outperform semantic baselines and is not the application's
default ranker. Its frozen checkpoint remains a local research artifact.
Diagnostics found useful message flow under fixed weights but no confirmed graph
or loss implementation defect; weak generalization remains the leading
hypothesis. MiniLM is the practical integration choice, not a claim that it won
the inspected test comparison. No additional test-guided tuning is authorized.

### Code, evidence, and reproducibility

- [Graph preparation and import](cohort_scaling/FULL_COHORT_PREPARATION.md)
  and [isolated full-cohort importer](cohort_scaling/import_full_cohort.py).
- [Full-cohort retrieval](full_cohort_graphrag/README.md),
  [evidence preparation](full_cohort_graphrag/src/prepare_evidence.py), and
  [generation safeguards](full_cohort_graphrag/ANSWER_GENERATION.md).
- [MiniLM integration](full_cohort_graphrag/semantic_v1/README.md) and
  [final Streamlit demo](full_cohort_graphrag/semantic_v1/demo_v2/README.md).
- [GraphSAGE experiment](gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/README.md),
  [saved results](gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/RESULTS.md), and
  [diagnostic findings](gnn_graphrag/reviews/STEP_66G_1_DIAGNOSTIC_REPORT.md).
- [Final technical audit](reports/final_project/STEP_66G_5_v1/FINAL_PROJECT_AUDIT.md),
  [reproducibility guide](reports/final_project/STEP_66G_5_v1/REPRODUCIBILITY_GUIDE.md),
  and [Challenge 3 report](reports/final_project/CHALLENGE_3_FINAL/HeartTrialTwin_Challenge3_Final_Report.pdf).

This is **not a standalone, clone-and-run deployment**. Provision the external
local Neo4j database `hearttrialtwin-full2824`, a dedicated read-only account,
checksum-pinned graph/membership and MiniLM feature bundles, and the exact cached
model revision separately. Large/generated datasets, model weights, private
configuration, and caches are intentionally excluded from the new publication
set. Missing pinned assets must fail rather than be silently replaced or rebuilt.
Follow the guide for the three separate UI/backend/encoder environments; older
classification dependency pins must not be mixed with the encoder/GNN stack.

After those prerequisites are satisfied, from the repository root:

```bash
# Create the private file only if absent; do not overwrite existing credentials.
test -e full_cohort_graphrag/.env || cp full_cohort_graphrag/.env.example full_cohort_graphrag/.env
.venv-full-system/bin/python -B -m streamlit run full_cohort_graphrag/semantic_v1/demo_v2/app.py --server.address 127.0.0.1 --server.port 8502 --server.headless true --browser.gatherUsageStats false

# Offline backend and integration regressions; no Neo4j/Ollama calls.
.venv-graphrag/bin/python -B -m unittest discover -s full_cohort_graphrag/tests -p 'test_*.py' -q
.venv-graphrag/bin/python -B -m unittest full_cohort_graphrag.semantic_v1.test_pipeline full_cohort_graphrag.semantic_v1.demo_v2.test_demo -q
```

Open <http://127.0.0.1:8502/>. Exact factual lookup and complete outcome listings
do not require Ollama. The optional explanation path additionally requires the
existing local Ollama service/model. This new retrieval publication does not
bundle the Neo4j database, MiniLM/GNN weights, or credentials; existing tracked
classification artifacts remain preserved. The earlier-challenge documentation
below is retained for provenance and must not be confused with this retrieval-only application.

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

## Original Challenge 3 assignment: AI Design — Knowledge Graph with Neo4j

This section preserves the original five-trial assignment scope. The later
full-cohort implementation is described above; deferrals below refer only to
that original stage.

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
