# Results index — saved poster claims and application evidence

The requested `HeartTrialTwin_Poster_V20_CONTENT_CORRECTED_EDITABLE_48x36.pptx`
has not been located. This indexes **supporting artifacts**, not verification of
the unavailable poster's actual wording or layout. No earlier poster substitutes
for Version 20. No demonstration-video link is invented.

## Scientific evidence map

| Claim / scope | Verified saved result | Primary artifact | Verification in this phase |
| --- | --- | --- | --- |
| Frozen terminal-outcome-selected cohort | 2,824: 2,237 Completed, 393 Terminated, 194 Withdrawn | [Original cohort results](../../final_project/HEARTTRIALTWIN_FINAL_20261102/analysis/results.json); [review copy](evidence/cohort_results.json) | Check saved counts and source hashes; not a new extraction |
| Full knowledge graph | 28,777 nodes, 79,125 original directed relationships, 19,740 registered planned outcomes | [Pinned full manifest](../../../artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1/full_cohort_manifest.json) | Manifest/payload verification and row recount, not a new live Neo4j audit |
| Missing source evidence | 253 trials lack browse rows; 41 lack planned outcomes; 528 outcome time frames missing | [Coverage](../../../artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1/COVERAGE_REPORT.md) | Read saved source coverage; missingness is not clinical absence |
| B1 saved Louvain partition | Mean three-seed ARI 0.648; seed 42: 823 communities / 747 singletons | [Stability](../../challenge4_community_graphrag/full_cohort_results/community_stability_v1.json), [memberships](../../challenge4_community_graphrag/full_cohort_results/louvain_full_cohort_v1.json) | Aggregate saved ARIs/count saved memberships; no community algorithm rerun |
| B3 exact-normalization partition | Mean ARI 0.867; seed 42: 904 communities / 820 singletons | [Sensitivity](../../challenge4_community_graphrag/full_cohort_results/community_sensitivity_v2.json) | Verify pinned input identity and saved membership counts; stability is not clinical validity |
| Descriptive phase/intervention analysis | 1,319 phase-applicable / 1,505 NA; 115 NA drug-including trials; 88 dashboard cells, 13 unadjusted comparisons | [Cohort results](evidence/cohort_results.json); [dashboard manifest](../../final_project/HEARTTRIALTWIN_INTEGRATED_20261102_v1/results/dashboard_manifest.json) | Inspect frozen artifacts and UI behavior; do not rerun adjusted models |
| Frozen association-ranking protocol | 1,976 / 424 / 424 trial partitions; 61,218 permitted message edges; 2,219 eligible test queries | [Version 2 manifest](../../../gnn_graphrag/protocols/HTT-GNN-ASSOC-PROTOCOL-v2/split_manifest.json) | Verify identity/recorded counts; no partition regeneration or test-based tuning |
| Later V1 status-snapshot predictive evaluation | 358 scored; 329 binary evaluable (289 Completed / 40 Terminated); 29 Withdrawn excluded | [Review copy](evidence/independent_evaluation_v1.json), [original narrative](../../../V1_INDEPENDENT_EVALUATION_REPORT.md) | Inspect checksum-bound aggregate results only; no evaluation or bootstrap rerun |
| V1 predictive metrics | ROC-AUC 0.486592 (CI 0.384907–0.588509); AP 0.157487; Brier 0.110039; release BLOCKED | [Aggregate evaluation](evidence/independent_evaluation_v1.json) | Saved measured results, not clinically validated forecasting |
| Longitudinal feasibility | 24 trials, 72 observations; 9 changing trials, 10 changed adjacent comparisons, 38 unchanged | [Review summary](evidence/longitudinal_summary.json); original pilot source paths/hashes in [evidence provenance](EVIDENCE_SOURCES.json) | Inspect existing reconstructed pilot; no new history downloads or event-date inference; raw panel remains external |

The graph/source archive is `HTT-P1-AACT-20260905`, September 5, 2026. Snapshot
fields can include amendments and are not certified original registrations.
Historical descriptive discontinuation combines Terminated + Withdrawn; later
V1's binary endpoint excludes Withdrawn. These denominators must not be mixed.

## Frozen ranking comparison — descriptive, not new model selection

All methods ranked the same 2,824-trial observed-graph universe on **2,219**
embargo-eligible test queries. Query-micro values from the
[original results JSON](../../../gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/evaluation_test/results.json):

| Method | MRR | Recall@10 |
| --- | ---: | ---: |
| TF-IDF | 0.07074 | 0.11492 |
| MiniLM | 0.07619 | 0.12078 |
| Context pooling | 0.07841 | 0.12100 |
| Trained GraphSAGE | 0.01124 | 0.02208 |

GraphSAGE did not outperform semantic baselines and is not deployed as the
default ranker. The [diagnostic](../../../gnn_graphrag/reviews/STEP_66G_1_DIAGNOSTIC_REPORT.md)
supports message contribution under fixed trained weights and weak learned-space
generalization as the leading explanation; it did not confirm a graph/loss bug.
The experiment is registered-association ranking in an observed graph, not
clinical outcome prediction or unseen-trial induction. The inspected test set
must not drive revised models or split selection.

## Functional evidence versus research performance

- [Phase 2 validation](../../challenge4_community_graphrag/hearttrialtwin_community_app_v6/VALIDATION_PHASE2.md):
  169 distinct tests on the provisioned development setup, no scientific rerun.
- [Earlier bounded live GraphRAG validation](../../../full_cohort_graphrag/semantic_v1/demo_v2/VALIDATION.md):
  source-grounded sponsor/intervention/outcome behavior and measured functional
  latency, **not** an end-to-end relevance benchmark.
- [Phase 3 report](PHASE3_REPORT.md): new isolated-environment execution is
  reported separately from retained Phase 2 test results and from public-clone
  availability. No Neo4j/Ollama call is made in this phase.

[EVIDENCE_SOURCES.json](EVIDENCE_SOURCES.json) records exact original paths and
hashes for the lightweight copied summaries. [RUNTIME_ASSETS.json](RUNTIME_ASSETS.json)
distinguishes public source from external runtime material. Unavailable external
payloads are never represented as downloadable public files or reconstructed
by invented values.
