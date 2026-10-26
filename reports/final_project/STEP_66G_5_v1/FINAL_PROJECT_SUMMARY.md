# HeartTrialTwin — final-project technical summary

Step 66G-5 · audited October 25, 2026 (America/Chicago). This is a technical
handoff and evidence index, **not the actual Challenge 3 report**.

## Objective and implemented scope

Explore registered heart-failure trial information using a provenance-preserving
Neo4j graph, compare semantic and graph-based association ranking, and demonstrate
verified retrieval through a local application. The trained task is **registered
planned-outcome-measure-to-trial association ranking within an observed graph**.
It is not clinical outcome, effectiveness, termination-risk or unseen-trial
prediction. Earlier discontinuation-model/Challenge 2 work remains separate and
unchanged; its metrics must not be mixed with this experiment.

Implemented application: **question → exact NCT or pinned MiniLM ranking →
bounded read-only Neo4j evidence → validated, cited registered facts → answer or
abstention**. GraphSAGE remains a reproducible research comparison, not the
default retrieval model. Optional Ollama provides constrained catalog selection,
not unrestricted scientific synthesis.

## Data and identity

| Component | Verified identity / size |
| --- | --- |
| Snapshot / membership | `HTT-P1-AACT-20260905`; September 5, 2026; 2,824 trials |
| Source archive | `20260905_export_ctgov.zip`; recorded size 2,526,451,724 bytes; MD5 `99e62b3f8ae5838b36bc0c2277ad2714` |
| Full graph | `HTT-KG-AACT-20260905-FULL2824-v1`; 28,777 nodes, 79,125 original relationships |
| Registered outcomes | 19,740 source-record associations; 2,783 trials have outcome records; 41 do not |
| Protocol | `HTT-GNN-ASSOC-PROTOCOL-v2`; 1,976 / 424 / 424 train/validation/test trials |
| Partition source associations | 13,819 / 2,962 / 2,959 respectively |
| Training inputs | 9,036 observed context nodes; 61,218 computational message edges |
| Training query representation | 11,712 distinct normalized queries; 13,277 unique query-owner pairs |
| Eligible evaluation queries | Validation 2,068 of 2,651; test 2,219 of 2,652 pre-embargo queries |
| Feature shapes | Context 9,036×390; train 11,712×384; validation 2,068×384; test 2,219×384 |

Node counts: Trial 2,824; ConditionTerm 1,743; Intervention 3,417; Sponsor 1,052;
PlannedOutcome 19,740; SourceDataset 1. Submitted and browse conditions remain
source-distinct. Planned outcomes describe **registered measures**, not observed
clinical findings. Snapshot fields may include amendments; initial-registration
availability is not established. Membership originates in a terminal-outcome-
selected research cohort, not every registered HF trial.

Canonical sources: [graph manifest](../../../artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1/full_cohort_manifest.json),
[protocol manifest](../../../gnn_graphrag/protocols/HTT-GNN-ASSOC-PROTOCOL-v2/split_manifest.json),
[feature manifest](../../../gnn_graphrag/feature_artifacts/HTT-GNN-ASSOC-FEATURES-v1/manifest.json).

## MiniLM and GraphSAGE methodologies

- Encoder: `sentence-transformers/all-MiniLM-L6-v2`, revision
  `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`; normalized 384-D, CPU, effective
  256-token limit. Context adds six type slots; only Trial, ConditionTerm,
  Intervention and Sponsor slots are active. Identifiers are linkage metadata,
  not semantic features. Held-out measure-only query embeddings were generated
  separately after the appropriate gates.
- All planned-outcome target edges and computational reverses are removed before
  graph computation. Provenance remains in the authoritative source graph but
  not in the message graph. The 100,698 pre-mask semantic message edges lose
  39,480 target-direction/reverse edges, leaving 61,218.
- Supervised model: mean GraphSAGE 390→128→64 plus learned 384→64 query projection;
  normalized cosine ranking. One seed/configuration; multi-positive probability-
  mass loss, training-only exclusions and 64 sampled unlinked candidates/query.
  Unlinked is not synonymous with clinically irrelevant.
- Adam 0.001, weight decay 0.0001, temperature 0.1, clipping norm 1; 80 updates
  completed. Validation MRR every five epochs selected **epoch 60**, not epoch 80.
  The maximum epoch bound stopped training before patience was exhausted.

Family-aware, trial-disjoint target partitions were frozen before performance
evaluation. All 2,824 trials remain observed candidates/context, including
held-out trial covariates. This is **not inductive generalization**. Twenty-five
strong unresolved pairs remain conservatively co-grouped; 69 weak-candidate
endpoints are quarantined from held-out queries, not removed from context or
candidates. Family and exact/near-query screening remains incomplete.

## Saved benchmark comparison — not rerun for this audit

All methods ranked the same ordered 2,824 candidates. Values are fractions.

| Method | Validation MRR | Test MRR | Test Recall@1 | Test Recall@5 | Test Recall@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| TF-IDF | 0.085190 | 0.070741 | 0.047544 | 0.089905 | 0.114917 |
| MiniLM | 0.081147 | 0.076192 | 0.052050 | 0.092835 | 0.120775 |
| Context pooling | 0.079348 | 0.078413 | 0.053853 | 0.095539 | 0.121000 |
| Untrained GraphSAGE | 0.003072 | 0.002663 | 0.000000 | 0.001803 | 0.003605 |
| Trained GraphSAGE | 0.021803 | 0.011239 | 0.000000 | 0.012168 | 0.022082 |

Trained GraphSAGE did **not** outperform any non-GNN baseline. Context pooling's
highest observed test MRR is descriptive, not permission for test-guided model
selection or a statistically established advantage over MiniLM. MiniLM was
approved for the opt-in integration as a simple, pinned semantic candidate path;
it is not claimed to be the overall benchmark winner. The existing test is
exposed and cannot serve as fresh unbiased confirmation for a revised model.

Metrics/source details: [validation JSON](../../../gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/evaluation_validation/results.json),
[test JSON](../../../gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/evaluation_test/results.json),
[original results and uncertainty definitions](../../../gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/RESULTS.md).
Family-bootstrap intervals apply to **family-macro MRR**, not the query-micro MRR
above. Eligible-query scoring coverage was 100%; this is not full-population
retention or answer-generation accuracy.

## Diagnosis and application observations

No indexing, aggregation, loss or negative-exclusion defect was demonstrated.
Training MRR increased, while held-out performance was weak and validation
deteriorated after epoch 60. No complete embedding collapse was observed. Removing
messages from the selected weights reduced validation MRR 0.021803→0.013195;
this is not a separately trained no-graph baseline. A tiny training-only sanity
check memorized 16 associations; it did not demonstrate generalization.

[Diagnostic findings](../../../gnn_graphrag/reviews/STEP_66G_1_DIAGNOSTIC_REPORT.md)
separate measured behavior from hypotheses about semantic compression/alignment,
negative difficulty and task limitations. No new optimization was performed.

The final UI provides exact lookup, bounded semantic discovery, source evidence,
citations, complete outcome listings, timeout messages and abstention. G-4 live
sponsor/intervention responses took **0.634/0.758 s**, versus prior sponsor
137.600 s and an intervention timeout. They are deterministic verified facts,
not evidence of faster LLM inference. Discovery took **25.093 s**, preserved ranks
and logged the skipped missing-outcome candidate. See [G-4 validation](../../../full_cohort_graphrag/semantic_v1/demo_v2/VALIDATION.md).

## Readiness and next actions

**Ready to author the scoped report and presentation; not cleared for public
publication yet.** This audit reran 220 offline tests successfully and confirmed
current read-only database access plus one browser title lookup. A password in
the full-cohort example template was sanitized. Its exposure still requires
owner-controlled credential rotation and private `.env` update before sharing.

The current full-cohort code/artifacts are local untracked work; this audit did
not publish them to [GitHub](https://github.com/akwasianing/HeartTrialTwin).
External reproduction needs the pinned graph/feature assets, cached encoder and
documented environments. No clinical deployment readiness is claimed.

Use [FINAL_PROJECT_AUDIT.md](FINAL_PROJECT_AUDIT.md),
[REPRODUCIBILITY_GUIDE.md](REPRODUCIBILITY_GUIDE.md), and
[CHALLENGE_3_REPORT_EVIDENCE.md](CHALLENGE_3_REPORT_EVIDENCE.md) for the checks,
commands, figure inputs, quotations, screenshots and remaining submission tasks.
