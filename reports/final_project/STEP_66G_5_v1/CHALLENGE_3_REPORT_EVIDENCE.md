# Challenge 3 — verified material for later report/presentation authoring

Evidence package only. This is **not** the final report, a newly evaluated
benchmark, or an updated slide deck. Keep the distinctions below when writing.

## Claim-to-source inventory

| Material to discuss | Authoritative evidence | Permitted claim / caution |
| --- | --- | --- |
| Problem and motivation | [Current summary](FINAL_PROJECT_SUMMARY.md) and [original graph manifest](../../../artifacts/knowledge_graph/graph_import_manifest.json) | Explore registered facts and association retrieval with provenance; not clinical benefit prediction |
| Full dataset | [Full graph manifest](../../../artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1/full_cohort_manifest.json), [coverage](../../../artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1/COVERAGE_REPORT.md) | 2,824 frozen trials; 28,777 nodes; 79,125 relationships; 19,740 outcomes; snapshot may include amendments |
| Initial graph design | [Semantic design notebook](../../../notebooks/HeartTrialTwin_Challenge3_Semantic_Design.ipynb), [six-label graph validation](../../../artifacts/knowledge_graph/VALIDATION_REPORT.md) | Five-trial illustrative origin, not the full cohort or representative population |
| Read-only retrieval | [Full retrieval source](../../../full_cohort_graphrag/src/retrieve.py), [fixed Cypher](../../../full_cohort_graphrag/src/queries.py) | Actual registered evidence and trial-bound relationship provenance |
| Feature methodology | [Feature specification](../../../gnn_graphrag/reviews/STEP_66D_1_MINILM_FEATURE_SPECIFICATION.md), [feature validation](../../../gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/FEATURE_VALIDATION.md) | Pinned MiniLM; 384 semantic dimensions plus six context-type slots; separate held-out query features |
| Protocol and human approvals | [V2 manifest](../../../gnn_graphrag/protocols/HTT-GNN-ASSOC-PROTOCOL-v2/split_manifest.json), [freeze approval](../../../gnn_graphrag/reviews/STEP_66C_3U_V2_FREEZE_APPROVAL.md), [execution authorization](../../../gnn_graphrag/reviews/STEPS_66D_66F_EXECUTION_AUTHORIZATION.md) | Frozen family-aware targets, masks and embargoes; external approvals preserve internal fail-closed metadata |
| Trained model | [Prespecified config](../../../gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/experiment_config.json), [selection](../../../gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/training/selection.json) | Genuine supervised GraphSAGE; epoch 60 selected after an 80-update run |
| Benchmark comparison | [Results](../../../gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/RESULTS.md), [validation JSON](../../../gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/evaluation_validation/results.json), [test JSON](../../../gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/evaluation_test/results.json) | Trained GNN worse than all three non-GNN baselines; observed test comparison is descriptive |
| Diagnostic findings | [Diagnostic report](../../../gnn_graphrag/reviews/STEP_66G_1_DIAGNOSTIC_REPORT.md) | No demonstrated implementation defect; weak generalization/late overfitting; hypotheses not isolated causes |
| Final demo | [Demo README](../../../full_cohort_graphrag/semantic_v1/demo_v2/README.md), [G-4 actual live validation](../../../full_cohort_graphrag/semantic_v1/demo_v2/VALIDATION.md), [current audit](FINAL_PROJECT_AUDIT.md) | MiniLM proposes candidates; Neo4j facts and citations substantiate answers |
| Future three-system RAG comparison | [Shared Q1–Q10 specification](../../../evaluation/questions_v1.json), [protocol](../../../evaluation/README.md) | Formal Vector/Static/Agentic RAG benchmark remains NOT RUN; do not substitute the association-ranking experiment |

## Architecture diagram specifications

**Figure A — implemented serving path.** Draw a solid lane:

```text
Streamlit question
  ├─ exact NCT + supported field ─────────────────────────┐
  └─ semantic outcome topic → pinned MiniLM cosine        │
       → original ranked prefix (all 2,824 candidates)    │
       → bounded evidence-backed candidate examination ──┤
                                                        ▼
      fixed read-only Neo4j profile → prepared evidence validation
        → deterministic cited facts / COMPLETE planned-outcome listing
        → grounded answer or explicit abstention → source evidence + trace
```

Show optional constrained Ollama catalog selection as a separate, labeled
branch **after** evidence validation: one attempt, 60-second request timeout,
strict original citation/relevance validation, unsupported output withheld.
It does not execute Cypher or synthesize unrestricted medical conclusions.
Label the UI, Neo4j and MiniLM subprocess environments separately.

**Figure B — offline research lane.** Use a dashed box, not an app component:

```text
Pinned graph → frozen V2 partition/mask/embargo protocol
 → permitted context + pinned MiniLM features
 → training-only GraphSAGE + query projection → validation checkpoint selection
 → one frozen-test comparison against TF-IDF / MiniLM / pooling / untrained GNN
```

Put **“observed graph; target edges/reverses removed; held-out trial context
visible; not unseen-trial induction”** beside the diagram. No arrow should imply
that trained GraphSAGE is the deployed ranking model. Provenance relationships
stay in authoritative Neo4j even when excluded from computational message passing.

**Figure C — schema/count inset.** Six labels with counts from the summary.
Solid original semantic relationships: HAS_SUBMITTED_CONDITION,
HAS_BROWSE_CONDITION, HAS_INTERVENTION, LEAD_SPONSORED_BY,
HAS_PLANNED_OUTCOME. Dashed provenance: MEMBER_OF_DATASET and SOURCED_FROM.
Distinguish original directions from added computational reverses. Explain
100,698 pre-mask semantic message edges → 61,218 permitted edges, not a change
to the 79,125 authoritative Neo4j relationships.

## Existing figures that can be reused without inventing values

- [Actual training loss/validation-MRR curves](../../../gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/training/training_curves.svg).
- [Saved validation comparison](../../../gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/evaluation_validation/ranking_comparison.svg).
- [Saved test comparison](../../../gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/evaluation_test/ranking_comparison.svg).

Use the five-method numerical table in [the summary](FINAL_PROJECT_SUMMARY.md).
Show MRR/Recall as fractions or clearly converted percentages. Label test data
as already exposed; no new selection follows it. Do not attach family-macro
confidence intervals to query-micro MRR. Do not reuse the five-trial untrained
prototype's Hit@1 0.20/0.30/0.10 as this trained full-cohort evaluation.

## Actual screenshots versus instructions

Two **real, unedited** browser captures were saved in this audit:

1. [01_live_title.jpg](screenshots/01_live_title.jpg): actual GROUNDED status,
   6.36-second UI timing and zero-model-request metric area.
2. [02_live_title_answer.jpg](screenshots/02_live_title_answer.jpg): actual title,
   NCT citation, dataset/graph/snapshot provenance and safeguards.

They were captured from the available narrow in-app browser; they are not wide
presentation mockups. A full-page capture API was unavailable, so two viewport
captures preserve the actual view. Screenshot pixels do not prove every internal
validation assertion; source JSON and automated tests provide that audit trail.

For wider slide images, use the exact launch command in the reproducibility
guide, enlarge the browser window and follow the [demo screenshot instructions](../../../full_cohort_graphrag/semantic_v1/demo_v2/README.md).
The **discovery-table, full seven-outcome, and abstention screenshots remain
capture instructions**, not claimed images in this package. No classroom-specific
or final-presentation screenshot was fabricated.

## Representative source-grounded answers

All examples below belong to `HTT-P1-AACT-20260905`, graph
`HTT-KG-AACT-20260905-FULL2824-v1`, snapshot 2026-09-05.

- **Title:** For NCT00206232, the registered title is
  “Novel Treatment for Diastolic Heart Failure in Women”
  `[cite:85602b5dbe212bf4ce959041]`; studies.txt record NCT00206232.
- **Lead sponsor:** Baylor College of Medicine,
  `[cite:3db774038cf4618ff9294543]`; sponsors.txt record **381715287**;
  path `NCT00206232|LEAD_SPONSORED_BY|sponsor:64f999d92d1b73893f9b`.
- **Intervention:** Spironolactone,
  `[cite:21f56031bbf8289fe76bfdcb]`; interventions.txt record **392379839**;
  path `NCT00206232|HAS_INTERVENTION|intervention:eb4e562ee31fac7ede8a`.

The complete seven-record answer is preserved in the
[live outcome trace](../../../full_cohort_graphrag/semantic_v1/demo_v2/validation/HTT-DEMO-v2-SMOKE-v1/03_outcomes.json):

| design_outcomes.txt ID | Exact registered measure | Type |
| --- | --- | --- |
| 1426532164 | Procollagen peptides, troponin I, tumor necrosis factor alpha, Brain Natriuretic Peptide | other |
| 1426532165 | Electrolytes, blood urea nitrogen, creatinine | other |
| 1426532166 | Quality of Life Questionaire | other |
| 1426532167 | New York Heart Association Classification | other |
| 1426532168 | Number of participants with adverse events | other |
| 1426533443 | Echocardiography parameters of diastolic function | secondary |
| 1426534673 | Six minute walk distance | primary |

The trace retains every exact time frame, evidence ID and citation binding.
“Questionaire” preserves source spelling. A planned measurement window referring
to completion at six months is a registered schedule, not an observed completion
date or measured result. Registered planned outcomes are not observed clinical
results; snapshot values may contain amendments.

Unsupported example: **“Did spironolactone improve survival in NCT00206232?”**
must abstain. Registered measures cannot establish a treatment effect. Unknown
NCT99999999 must not be replaced by a semantic candidate. Missing outcomes for
NCT00000475 must not be reported as a nonexistent trial or clinical absence.

## Engineering and Human–AI Co-Design evidence

| Actual human decision / observed issue | Implemented response and verified consequence |
| --- | --- |
| Preserve source provenance while excluding provenance hubs from GNN computation | Original relationships retained; masked computational context excludes targets and provenance edges |
| Require explicit scientific review before training | External freeze and execution approvals bind exact hashes while preserving internal `training_permitted=False` |
| Do not present random message passing as trained superiority | Initial five-trial forward-pass/ranking diagnostics remain separate from the supervised full-cohort experiment |
| Investigate weak GNN results rather than retune exposed test | Fixed-checkpoint diagnosis and tiny training-only sanity check; checkpoint/results retained; GNN stays experimental |
| Citations and complete outcome listings take priority over fluent partial answers | Catalog-ID validation and separate deterministic complete-listing path; seven outcomes preserved and independently checked |
| Address slow model calls without weakening grounding | Default source-exact facts need zero LLM requests; optional bounded model path retains validators |
| Missing second-ranked outcome evidence should not rewrite ranking | New bounded examination records skips and selects complete evidence without changing original scores/ranks |
| Final audit must include credential safety | Exposed example-template password sanitized; rotation explicitly remains an owner action before publication |

Codex assisted with code inspection, implementation, mocked regression tests,
hash/provenance checks, debugging and preparation of this evidence package.
Project-owner instructions supplied scope, approvals and scientific decisions.
Do not imply an independent clinical review, external peer validation, fabricated
human signatures, or individual adjudication of all unresolved family pairs.

## Lessons, limitations and future work to carry forward

- A genuine trained GNN is not necessarily better than semantic retrieval.
- Passing code tests and learning training associations do not imply held-out
  retrieval quality, clinical validity or inductive generalization.
- Metadata/citations should be deterministic; supported-source membership alone
  does not prove question relevance or completeness.
- Preserve negative findings, timeout failures and the distinction between
  benchmark scoring latency and end-to-end interactive latency.
- Future model changes need a new development protocol and independent
  confirmation data; the existing test cannot be repeatedly optimized against.
- Improve portability, question coverage, field-specific missingness policy,
  evidence paging and carefully tested synthesis through separately reviewed
  work. Do not silently relax the current safeguards.
- Finish credential rotation/selective publication before calling the package
  publicly reproducible. Author the final report/slides only after human review.
