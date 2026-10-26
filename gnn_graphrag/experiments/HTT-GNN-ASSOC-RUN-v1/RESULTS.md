# Steps 66D–66F — completed measured execution

Completed October 24, 2026. **Research experiment only: registered planned-outcome-to-trial association ranking within an observed graph.** Registered planned outcomes are not observed clinical results. No clinical prediction, treatment-effect or unseen-trial generalization claim is supported.

## Outcome

The feature, supervised training and frozen-test benchmark stages are complete. **Simple context pooling had the highest observed test query-micro MRR: 0.078413. Trained GraphSAGE reached 0.011239 and did not outperform any non-GNN baseline.** Training improved the GNN relative to its seeded untrained version, but it produced **zero top-1 successes among 2,219 test queries**. No overall GNN retrieval improvement or deployment readiness is established. No model, configuration or split was changed in response to these results, and no GraphRAG integration was performed.

## 1. Recovery and completed features

The previous validation-query bundle was recovered intact, verified and reused without regeneration. The incomplete original context matrix was preserved. A fresh pinned full-context pass matched every preserved float32 value and type slot with maximum absolute difference **0.0**, taking **306.818 seconds**. A subsequent relative-path bookkeeping exception was corrected without changing the encoder or numerical checks. The successful comparison was bound in [the recovery verification record](context_recovery_verification.json); its reuse avoided another completed context pass. Both incomplete context directories remain preserved. See [RECOVERY.md](RECOVERY.md) for the exception, evidence and commands.

| Feature payload | Shape | Max tokens including special tokens | Repeat maximum difference |
|---|---|---:|---:|
| Context | 9,036 × 390 | 87 | 0.0 |
| Training queries | 11,712 × 384 | 88 | 0.0 |
| Validation queries | 2,068 × 384 | 80 | 0.0 |
| Test queries | 2,219 × 384 | 71 | 0.0 |

All payloads are finite float32. Semantic vectors are L2-normalized; context appends the six declared type slots without renormalizing the concatenation. Only Trial, ConditionTerm, Intervention and Sponsor slots are active. PlannedOutcome and SourceDataset context slots remain zero. No truncation occurred under the effective **256-token** limit.

Encoder: `sentence-transformers/all-MiniLM-L6-v2`, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, verified snapshot SHA-256 `fa4e0ce8c98e7af6762dcc8d1930113fab9c487f5c59ba80c5e9d3e098b0f8b2`. CPU, one thread, batches of 16, no downloads. Recorded first-pass query encoding: training **134.536 s**, validation **48.090 s** from the reused bundle, test **25.500 s**. These exclude repeat-pass and model-loading costs. Original context first-pass timing was not retained in the partial artifact, so its feature audit leaves that field null rather than inventing a duration.

Detailed feature locations, payload hashes and validation are in [FEATURE_VALIDATION.md](FEATURE_VALIDATION.md). Each feature bundle has model/tokenizer file hashes, source mappings, audits, manifest and `SHA256SUMS`. Held-out queries were encoded only through the separate evaluation projection; test encoding occurred after checkpoint selection.

## 2. Supervised training and selection

- Frozen protocol: `HTT-GNN-ASSOC-PROTOCOL-v2`, manifest SHA-256 `b13d662390b687b62a08cc1fb81bd3413f2c9d1fbb3b6ec86438b1a6854cd95b`.
- 2,824 candidates; 1,976/424/424 train/validation/test trials. Source associations remain 13,819/2,962/2,959, total 19,740.
- 9,036 observed context nodes and 61,218 non-target computational edges. All planned-outcome target edges/reverses and provenance hubs are excluded from message passing.
- Genuine two-layer mean GraphSAGE 390→128→64 and trainable 384→64 query projection; 141,056 parameters. All six parameter tensors changed relative to the saved untrained state.
- Training-only optimization: 11,712 normalized queries, 13,277 distinct query–trial positive pairs, including 669 multi-owner queries. This differs from 13,819 source records because repeated registered measures within a trial collapse to the same query/owner association; original records are not deleted.
- Multi-positive probability-mass loss; equal query weighting; temperature 0.1; 64 uniform training-only sampled candidates per query without replacement. All known training positives, family exclusions and screened ambiguities are excluded. Eligible negative pools ranged from 1,910 to 1,975 trials. Unlinked trials are not confirmed clinically irrelevant negatives.
- One seed/configuration, no search: seed 20261023, Adam 0.001, weight decay 0.0001, gradient clip 1, one full-graph update per epoch, maximum 80 epochs. Exact settings were saved in [experiment_config.json](experiment_config.json) before any new model performance was inspected.
- Validation MRR every five epochs, initial checkpoint eligible, minimum improvement 0.0001, patience five evaluations, earlier-checkpoint tie break.

**80 epochs completed in 112.385 seconds of measured training/validation-loop time. Epoch 60 was selected using validation MRR 0.021802783.** The maximum-epoch bound ended training; four non-improving evaluation points followed epoch 60, fewer than the patience limit of five. This is checkpoint selection at epoch 60, not a claim that training stopped at epoch 60.

Training sampled loss: epoch 1 **4.115669**, selected epoch 60 **2.158746**, last epoch 80 **1.953782**. Negatives change deterministically by epoch, so these are sampled training objectives, not fixed-set held-out losses. Validation MRR peaked at epoch 60, then was 0.018410 at epoch 80. No extra optimization followed this observation.

Selected checkpoint: [selected_model.pt](training/selected_model.pt), SHA-256 `58bac20f20d15349063ef36079d204714052b48bb4332c6622e68c43d0d7b936`.

Artifacts: [full epoch history](training/history.json), [selection record](training/selection.json), [training curves](training/training_curves.svg), [training manifest](training/manifest.json), [last trained state](training/last_model.pt), [identical-initialization untrained state](training/untrained_model.pt). Checkpoints retain model/optimizer state where applicable, seeds, configuration, environment, feature and code hashes.

## 3. Validation results

2,068 eligible queries, representing 383 trials / 380 families, from 2,651 pre-embargo partition queries. All methods ranked the same 2,824 candidates. These baseline results were generated after checkpoint selection and were not used for a new model search.

| Method | MRR | Recall@1 | Recall@5 | Recall@10 | Hit@10 |
|---|---:|---:|---:|---:|---:|
| TF-IDF | 0.085190 | 0.058994 | 0.109284 | 0.125725 | 0.125725 |
| MiniLM | 0.081147 | 0.054642 | 0.102515 | 0.125725 | 0.125725 |
| Context pooling | 0.079348 | 0.053191 | 0.099130 | 0.126692 | 0.126692 |
| Untrained GraphSAGE | 0.003072 | 0.000967 | 0.001451 | 0.002660 | 0.002901 |
| Trained GraphSAGE | 0.021803 | 0.007253 | 0.021760 | 0.043037 | 0.043037 |

All metrics, including Hit@1/5, aggregates, strata, latency and citations to original association evidence are retained in [validation results](evaluation_validation/results.json) and per-method `*_rankings.jsonl`. [Validation comparison chart](evaluation_validation/ranking_comparison.svg).

## 4. Frozen test results — evaluated once after selection

2,219 eligible queries, representing 401 trials / 400 families, from 2,652 pre-embargo partition queries. No test result was used to choose the checkpoint, configuration, features, candidate universe or splits. One completed test bundle exists, with no partial failed test bundle. Subsequent audit recomputed metrics from stored ranks, **not another model inference/evaluation run**.

Values below are fractions, not percentages. Recall divides retrieved known owners by all known owners; Hit asks whether any owner was found. The distinction matters for the 19 multi-owner test queries (2,200 queries have one known owner).

| Method | MRR | Recall@1 | Recall@5 | Recall@10 | Hit@1 | Hit@5 | Hit@10 |
|---|---:|---:|---:|---:|---:|---:|---:|
| TF-IDF | 0.070741 | 0.047544 | 0.089905 | 0.114917 | 0.047769 | 0.090131 | 0.114917 |
| MiniLM | 0.076192 | 0.052050 | 0.092835 | 0.120775 | 0.052276 | 0.092835 | 0.120775 |
| Context pooling | **0.078413** | **0.053853** | **0.095539** | **0.121000** | **0.054078** | **0.095539** | **0.121226** |
| Untrained GraphSAGE | 0.002663 | 0.000000 | 0.001803 | 0.003605 | 0.000000 | 0.001803 | 0.003605 |
| Trained GraphSAGE | 0.011239 | 0.000000 | 0.012168 | 0.022082 | 0.000000 | 0.012168 | 0.022082 |

Context pooling is the descriptive winner on this test, not a statistically established improvement over MiniLM: the prespecified paired comparisons are trained GNN versus each baseline. No new test-guided choice or deployment follows this ranking.

| Method | Owner-trial macro MRR | Family-macro MRR | Family-macro MRR bootstrap 95% interval |
|---|---:|---:|---|
| TF-IDF | 0.082902 | 0.080609 | [0.062202, 0.099815] |
| MiniLM | 0.090249 | 0.087975 | [0.069101, 0.107116] |
| Context pooling | 0.093698 | 0.091432 | [0.071156, 0.112246] |
| Untrained GraphSAGE | 0.003045 | 0.003052 | [0.001905, 0.004708] |
| Trained GraphSAGE | 0.010684 | 0.010709 | [0.008509, 0.013364] |

Paired family-macro MRR differences (trained minus baseline), with the same 1,000 family-bootstrap draws:

- Versus untrained GraphSAGE: interval **[+0.005001, +0.010499]**.
- Versus TF-IDF: **[−0.089352, −0.051400]**.
- Versus MiniLM: **[−0.095256, −0.059399]**.
- Versus context pooling: **[−0.101424, −0.061169]**.

These intervals concern **family-macro**, not query-micro MRR. They support learning relative to the random initial model under this cluster analysis, but not an improvement over non-GNN retrieval. Unresolved families/shared-context dependence limit inferential strength.

Full precision, all supplementary metrics and source-bound ranks: [test results](evaluation_test/results.json), [test manifest](evaluation_test/manifest.json), and per-method `*_rankings.jsonl`. [Test comparison chart](evaluation_test/ranking_comparison.svg).

## 5. Coverage and measured latency

All eligible queries were scored by every method: coverage 100%. This is distinct from retaining 2,068/2,651 validation queries and 2,219/2,652 test queries after embargoes/quarantine. TF-IDF had seven zero-vector validation queries and four zero-vector test queries; these were retained with the declared NCT tie-break, not silently omitted. All other query vectors and all 2,824 candidate vectors were nonzero.

Test per-query scoring-plus-ranking timing on this local CPU run:

| Method | Median ms | p95 ms | One-time representation preparation seconds |
|---|---:|---:|---:|
| TF-IDF | 1.561 | 4.155 | 6.518 |
| MiniLM | 0.634 | 1.196 | 0.008 |
| Context pooling | 1.009 | 4.987 | 4.421 |
| Untrained GraphSAGE | 0.464 | 1.181 | 0.606 |
| Trained GraphSAGE | 0.339 | 0.545 | 0.352 |

These are **not end-to-end application latency**. One-time representation preparation includes method-specific fitting/transformation or graph/query projection as applicable. Shared MiniLM test encoding took 25.500 seconds for the first batch pass (11.492 ms amortized per row), plus a repeat check and model loading; individual encoding percentiles were not measured. No Neo4j retrieval or LLM answer time is included. Different local background loads/caches affect observed timing; no general speed superiority is established.

## 6. Integrity, isolation and tests

[final_integrity_audit.json](final_integrity_audit.json) verifies six complete output bundles, all checksums, unchanged Version 1/2 trees and protected prototype code, and the exact config/authorization pins. Source integrity rechecked all 35 source-hash and 23 protocol-output entries. Model/source mappings, finite/normalized arrays and type slots passed. Stored query ranks, trial owners, source evidence IDs, top-10 references and metric arithmetic reconciled for both splits and all five methods without rerunning test inference. TF-IDF fit provenance was identical between splits and used only training data.

**80 tests passed, zero failures/errors/skips**, in the final 47.188-second relevant offline suite: 28 execution/recovery tests, 21 original prototype tests and 31 saved-fixture protocol tests. Eight existing protocol regeneration/mutation methods were not selected and are not counted as passed/skipped. The old prototype test command requires the documented `PYTHONPATH`; an earlier package-style import error was resolved by the invocation, not a legacy code change.

Frozen `training_permitted=False` and the existing default loader refusal remain enforced. Authorized optimization used the separate independently validated external gate, not the audit-only loader. Target/reverse edges are absent; no validation/test association truth entered loss or negative sampling. Validation labels were used only in evaluation mode for checkpoint selection. Test features/truth were gated on the saved selected checkpoint.

The immutable `selection.json` still records `test_accessed:false` **as of selection**; completed test execution is recorded separately in `evaluation_test/manifest.json`. Likewise, original protocol `NOT_RUN`/provisional metadata is historical and preserved; the external run reports completion without rewriting the frozen protocol.

## 7. Reproduction and limitations

[README.md](README.md) provides exact feature, training, validation/test and offline-test commands, validation-only checks and a new-output-directory training reproduction command. Completed destinations refuse overwrite, and the test bundle must not be rerun for tuning. Recovery inputs/verification are documented separately. All implementation is localized to the new full-cohort modules; no Neo4j, GraphRAG, original prototype, frozen protocol, `week 5/`, model release or Git publication change was made.

Limitations: one seed/configuration and a bounded 80-update run do not establish the best achievable GNN; raw observed context includes held-out trials; family/near-query screening is incomplete; quarantine narrows evaluation rather than removing every uncertain context/candidate; registered exact owners are not clinical-equivalence labels; unlinked candidates can be semantically relevant; snapshot amendments and terminal-outcome-selected membership constrain population claims. Low held-out GNN retrieval is an observed result, not a reason to retune this completed test. Any future improvement needs a separately authorized development/evaluation plan that acknowledges this test exposure.

**No remaining runtime blocker. Training and evaluation are complete. No model integration, commits or pushes were performed.**
