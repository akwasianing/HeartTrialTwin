# Step 66G-1 — Frozen GraphSAGE ranking diagnosis

## Decision

No ranking-code defect was demonstrated in neighbor aggregation, candidate/query
ordering, the declared multi-positive loss, or negative-pool exclusions. Do not
patch those components speculatively or replace the selected checkpoint.

The clearest measured problem is weak generalization in the learned ranking
space, with additional overfitting after epoch 60. Learning works on training
examples; the model is neither completely collapsed nor unable to optimize.
Loss of useful pretrained semantic alignment is a plausible architectural cause,
not an experimentally isolated causal finding.

This is an observed-graph registered planned-outcome association-ranking task,
not clinical prediction or unseen-trial induction. Registered measures are not
observed clinical results.

## Scope, authorization and preserved artifacts

- Frozen run: `HTT-GNN-ASSOC-RUN-v1`.
- Frozen protocol: `HTT-GNN-ASSOC-PROTOCOL-v2`.
- Protocol manifest SHA-256:
  `b13d662390b687b62a08cc1fb81bd3413f2c9d1fbb3b6ec86438b1a6854cd95b`.
- Selected checkpoint SHA-256:
  `58bac20f20d15349063ef36079d204714052b48bb4332c6622e68c43d0d7b936`.
- The project owner's Step 66G-1 request authorized one tiny training-only overfit
  check and a training/validation no-message diagnostic, not a new full run.
- No test truth, test query features, or saved test results were opened by the
  diagnostic. Runtime read guards rejected those paths and global truth catalogs.
  All 2,824 observed candidate contexts remain available as prescribed by the
  original protocol; this is not test-association supervision.
- Before/after SHA-256 maps matched for 51 protected files: core and validation
  feature bundles, training and validation outputs, training input view,
  validation input/truth, candidate/split metadata, configuration, authorization,
  shared model and frozen execution code, and Version 1/2 protocol manifests.
  Aggregate map SHA-256:
  `64c12e79c5fcadbd2c258387c255ea651defa6bd7b8c94fd2eb45cace418b9ae`.
  This is a scoped preservation check, not a fresh audit of test-file contents.
- No frozen artifacts, production modules, protocol flags, Neo4j data, GraphRAG
  application, or existing benchmark results were changed. No commit or push.

## 1. Aggregation and ordering — checks passed

`src/model.py:mean_aggregate()` sums incoming source features and divides by
incoming degree; isolates receive zeros. Both GraphSAGE layers concatenate
self features with this mean, then apply their learned linear map and ReLU.

Eight fixed context-node probes matched independently computed neighbor means
with maximum absolute difference **0.0**. There are **61,218** computational
edges and **61,218** distinct source/target pairs, so no hidden multitype duplicate
pair reweighting was detected. The existing context validator checked allowed
relationships, endpoint labels, unique typed edges and reverse symmetry; no
planned-outcome target or provenance edges were allowed.

Feature-index rows match context-node rows; the first 2,824 nodes are sorted,
unique Trial IDs. Training scores explicitly map the sorted 1,976 training
candidates back into that full order. Validation feature rows match the frozen
eligible query IDs and truth order. The checkpoint's validation MRR reproduces
the saved value exactly: **0.021802783247318835**.

## 2. Query/graph alignment — mechanically correct; semantic bottleneck plausible

Queries use a learned `Linear(384,64)` and the graph uses
`390 -> 128 -> 64`; both outputs are L2-normalized before the same-space dot
product. All six parameter tensors changed from initialization. All six had
finite, nonzero gradient norms in a selected-checkpoint training-loss backward
check. There is no evidence of a detached query projection or swapped rows.

The projections do **not** preserve MiniLM's original cosine geometry by
construction. They begin independently initialized, and trial outputs have a
final ReLU whereas query outputs do not. Mean training-positive cosine rises
from **0.06046** at initialization to **0.27275** at selection; sampled unlinked
candidate cosine falls from **0.05969** to **-0.05318**. Thus alignment is learned
for training associations, but that does not establish semantic transfer to
embargoed held-out queries or held-out owners.

The saved tokenization audit reports **zero truncated context or training-query
texts** (maximum 87 and 88 tokens respectively); the 256-token input cap is not
a demonstrated cause of this failure. Input semantic vectors and output ranking
vectors pass normalization and finite-value checks. The 390-dimensional input
intentionally combines a unit semantic vector with a one-hot type vector and
therefore has norm sqrt(2), not 1; this follows the frozen feature policy.

## 3. Multi-positive objective — correct for the declared objective

`src/full_cohort_ranking.py:multi_positive_loss()` computes

`logsumexp(positive scores + sampled unlinked scores) - logsumexp(positive scores)`

after temperature scaling; padded positive indices are masked to negative
infinity. It optimizes total probability mass assigned to all known positive
training owners. The existing analytic test gives `log(33)` for two equally
scored positives and 64 sampled candidates, with the expected gradient signs.
There are **669** multi-positive training queries.

Important limitation: probability-mass loss can emphasize an easy positive
without making every positive rank well. That is an objective trade-off,
particularly for multi-owner Recall@K, not a demonstrated implementation error.
Unlinked associations are not confirmed clinical negatives.

## 4. Negative sampling — declared exclusions passed

All **11,712** training-query pools exclude known training positives, explicitly
ambiguous training associations, and training members of their positive owners'
known families. Pool sizes are **1,910–1,975**. All **749,568** sampled indices in
the fixed selected-epoch audit belong to their allowed pools, with 64 distinct
samples per query. No validation/test truth was consulted for this check.

Uniform sampling covers only about 3.2–3.4% of a pool per update. It might not
teach the distinctions needed among the strongest semantic competitors in a
2,824-candidate ranking. This is a hypothesis: no hard-negative experiment or
new tuning was performed. Family/ambiguity exclusions remain limited by the
frozen scientific audit and do not certify that all unlinked associations are
false or that every family has been identified.

## 5. Updates, normalization and embedding geometry

The original run made **80 optimizer updates**, one full-batch update per epoch.
Training loss decreased from **4.11567** to **1.95378**. No nonfinite recorded
gradient norms occurred; **76/80** updates exceeded the declared clipping norm 1.
The maximum pre-clipping norm was **13.35165**. Clipping was active, not a
verified failure. The selected graph's mean pre-normalization output norm was
**0.04021**, versus **0.23760** at initialization; this can affect normalization
derivatives and gradient balance but does not by itself prove instability.

Training-trial geometry (fixed seeded pair sample; descriptive, not a release
threshold):

| Representation | Mean pair cosine | Centered participation rank | Zero vectors | Unique vectors |
| --- | ---: | ---: | ---: | ---: |
| MiniLM semantic input, 384-D | 0.49777 | 52.04 | 0 | 1,972/1,976 |
| Untrained GraphSAGE, 64-D | 0.98762 | 14.23 | 0 | 1,976/1,976 |
| Selected GraphSAGE, 64-D | 0.39326 | 21.13 | 0 | 1,976/1,976 |
| Last GraphSAGE, 64-D | 0.32653 | 24.19 | 0 | 1,976/1,976 |

Initialization is highly anisotropic, but training substantially separates
vectors. **Complete embedding collapse is not supported.** Selected outputs
are sparse (68.59% zero coordinates), and dimensional compression/nonlinear
geometry may discard useful distinctions; the statistics alone do not isolate
that as the cause of weak validation. Effective ranks are within-space
statistics, not cross-dimensional cosine comparisons.

## 6. Underfitting versus overfitting

| Checkpoint | Training MRR, all 2,824 candidates | Training MRR, 1,976 training candidates | Validation MRR |
| --- | ---: | ---: | ---: |
| Initialization | 0.005109 | 0.006746 | 0.003072 |
| Selected, epoch 60 | 0.203863 | 0.224755 | 0.021803 |
| Last, epoch 80 | 0.233540 | 0.258706 | 0.018410 |

Training performance increases while validation falls after selection: this is
evidence of late overfitting and a substantial generalization gap. Training is
not perfect, so limited optimization or task capacity may coexist; simply adding
epochs is not justified by these observations. Frozen early selection correctly
kept epoch 60 rather than epoch 80. The run hit the 80-epoch cap before exhausting
its five-evaluation patience after the last improvement.

Previously saved validation baselines remain: TF-IDF **0.085190**, MiniLM
**0.081147**, context pooling **0.079348**. The selected GNN does not match these.
The query embargo/quarantine makes validation different from memorized training
associations; the gap is not a controlled causal decomposition of all factors.

## 7. Tiny training-only overfit sanity — passed

One fresh seeded model used the first sorted training-query IDs having one
known positive and distinct owners: **16 queries / 16 training owners**. The
architecture, Adam settings, temperature, clipping, seed, and negative policy
were unchanged. It retained the permitted observed context graph, but optimized
only these 16 training queries. It ranked against all **1,976 training
candidates**, with no validation/test evaluation or checkpoint selection.

| Updates | MRR | Hit@1 |
| --- | ---: | ---: |
| 0 | 0.000904 | 0.0000 |
| 25 | 0.968750 | 0.9375 |
| 50 | 1.000000 | 1.0000 |
| 200, prespecified stopping point | 1.000000 | 1.0000 |

Elapsed fitting/check time: **128.929 seconds**. No tiny-model checkpoint was
saved and it was not evaluated on validation. This supports basic learnability,
not generalization or correctness of every possible setting. No second attempt
or parameter search was performed.

Trace interpretation note: MRR/Hit@1 progress rows have their stated step
numbers. The runner stores its final pre-update sampled-loss/gradient snapshot
(step 199, before update 200) on the preceding progress row (175), overwriting
that row's earlier loss snapshot; do not interpret that scalar as a step-175
loss. This diagnostic logging limitation does not affect ranks, training,
frozen run history, or any benchmark result.

## 8. Fixed-weight no-message ablation

The selected checkpoint and query projection were held fixed; only computational
edges were replaced with an empty `[2,0]` tensor at both graph layers.

| Selected weights | Training MRR, all 2,824 candidates | Validation MRR |
| --- | ---: | ---: |
| Permitted messages | 0.203863 | 0.021803 |
| No messages | 0.067524 | 0.013195 |

The same training trial's full/no-message vectors have mean cosine **0.52995**.
Messages affect representations and improve ranking in this particular frozen
network. Removing them causes inference distribution shift: this is **not** a
separately trained MLP comparison, a causal scientific explanation, or evidence
that GraphSAGE outperforms semantic retrieval. No ablated model was fitted.

## Most likely causes and smallest justified next action

1. **Measured:** a large training/validation gap and deterioration after epoch 60.
   A broken optimizer, complete collapse and an indexing failure are not supported.
2. **Plausible:** replacing useful pretrained semantic cosine geometry with
   independently initialized, compressed nonlinear graph/query projections makes
   the learned association space generalize poorly. Final graph ReLU, type
   offsets and output scale are possible contributors, not isolated bugs.
3. **Plausible:** uniform 64-candidate probability-mass training does not match the
   hardest fine distinctions required by full-universe, multi-owner ranking.
   Weak semantic relevance of some context neighbors and unresolved associations
   are additional task limitations; neither was newly adjudicated.

**Do not apply a speculative bug fix or run longer training now.** Keep the
frozen comparison and working evidence retrieval intact. The smallest proposed
model correction for a separately approved experiment is an **identity-preserving
semantic residual score**: retain the fixed MiniLM/context-pooling cosine path
and learn only a graph residual, instead of replacing semantic similarity with
the random 64-D bottleneck. Prespecify the residual rule, initialization and
selection budget before fitting; change no sampling/epoch/activation settings
simultaneously. This is a hypothesis to test, not a measured improvement or an
implementation authorized by this diagnosis.

Any revised model needs a new versioned experiment. This validation set has now
informed diagnosis; further use is exploratory. The already reported test set
must not be reused to choose or certify a revision. An unbiased final claim
requires separately approved independent confirmation data and family/query
overlap controls; do not resplit the frozen protocol based on model results.

## New files and checks

- `gnn_graphrag/src/diagnose_full_cohort.py`: bounded standalone diagnostic.
- `gnn_graphrag/tests/test_full_cohort_diagnosis.py`: four lightweight helper tests.
- `gnn_graphrag/diagnostics/HTT-GNN-DIAG-66G1-v1/`:
  `diagnostic_plan.json`, `diagnostic_results.json`, `manifest.json`, `SHA256SUMS`.
- This report; no existing implementation file was edited.

Command executed:

```bash
.venv-vector-rag/bin/python -B -m unittest \
  gnn_graphrag.tests.test_full_cohort_diagnosis \
  gnn_graphrag.tests.test_full_cohort_execution -v
```

**32 tests passed, 0 failures** (4 new + 28 existing execution checks). These
are targeted tests, not a rerun of the whole repository or test-truth audit.

The single bounded diagnostic was executed with:

```bash
.venv-vector-rag/bin/python -B -m gnn_graphrag.src.diagnose_full_cohort
```

It refuses to overwrite its output directory. Repeating the tiny fitting check
or running a revised experiment is not authorized automatically by this report.

**Stopped after diagnosis. No model integration, full retraining, commit or push.**

## Resumed checkpoint — verification, model disposition and integration readiness

### Diagnostic completion

The diagnostic script, its tests, this report, the saved diagnostic manifest,
and the underlying training/ranking/model code were inspected on resumption.
All nine original diagnostic questions were already addressed. No fitting,
full ranking experiment, or tiny overfit experiment needed repeating.

The same focused command was run again: **32 passed, 0 failures**, in **6.612
seconds** of unittest execution (4 diagnostic tests and 28 existing execution
tests). These exercise ordering guards, the probability-mass loss and gradient
signs, positive/ambiguous/family negative exclusions, normalization, both model
heads receiving gradients, reproducible initialization, and input isolation.

The existing diagnostic/training/validation bundles passed checksum validation.
The selected checkpoint was loaded read-only for forward-only representation
verification. All recorded selected-model geometry fields recomputed with
**maximum absolute difference 0.0**, including query/trial geometry, first-layer
geometry and raw second-layer geometry. The same-trial full/no-message cosine
also reproduced exactly: **0.5299497246742249**. Saved validation ranking rows
average to **0.021802783247318835**, matching selection and diagnostic records.

The no-message MRR **0.013194558356761652** was verified against the hash-bound
saved diagnostic and inspected execution code; its ranking experiment was not
repeated. All six saved parameter deltas and gradient norms are nonzero and all
six saved gradient checks report finite values. The original 51 protected-file
hashes still match. Neither the test set nor its saved result files were opened.

New verification record:
`gnn_graphrag/diagnostics/HTT-GNN-DIAG-66G1-RESUME-v1/verification.json`.
No production or diagnostic Python source needed correction. The previously
documented tiny-check loss-snapshot labeling caveat remains; its rank measurements
and completed diagnosis are unaffected. The original executed diagnostic source
and its hash binding were deliberately preserved.

**Status: Step 66G-1 complete.** Weak held-out generalization and late overfitting
are measured findings; semantic-space disruption, final ReLU/scale effects and
uniform-negative difficulty remain hypotheses, not proven implementation bugs.
The proposed semantic-residual training experiment above is deferred, not the
next required capstone action.

### Model decision — experimental GraphSAGE, opt-in MiniLM candidate

Retain the trained GraphSAGE checkpoint and all comparisons as reproducible
research artifacts. Do **not** make GraphSAGE the default retrieval model or
describe graph-message contribution as superiority over non-GNN baselines.

For the next **separate, versioned integration candidate**, prefer the existing
fixed **MiniLM cosine baseline**, not a revised trained model. Reasons are its
slightly higher saved validation MRR than context pooling (**0.081147 versus
0.079348**), direct reuse of the pinned semantic space, and fewer graph/masking
dependencies. The difference is small: no MiniLM-versus-pooling significance or
general superiority is established. TF-IDF's saved validation MRR is actually
highest (**0.085190**); preserve it as a serious comparator rather than ignoring
that result. Neither MiniLM nor pooling has yet been demonstrated here as a
general-purpose natural-language GraphRAG retriever.

Context pooling remains a useful fixed alternative if graph-aware retrieval is
later justified; its use would require a reproducible permitted-edge/pooling
contract. Do not choose its mixture or edge policy using test scores.

The project owner supplied the following already-reported, rounded **test**
comparison. It is recorded descriptively only; it was not recomputed, used to
choose settings, or treated as fresh confirmation of this integration decision:

| Frozen method | Reported test MRR | Reported test Recall@10 |
| --- | ---: | ---: |
| Context pooling | 0.07841 | 0.12100 |
| MiniLM | 0.07619 | 0.12078 |
| TF-IDF | 0.07074 | 0.11492 |
| Trained GraphSAGE | 0.01124 | 0.02208 |

This engineering recommendation is made after results were known and must not
be represented as a retrospectively prespecified benchmark selection. No
default application was switched. New retrieval settings or model revisions
require their own experiment record and independent confirmation for an unbiased
final performance claim; the existing frozen test set cannot certify a revision.

### Inspected application interfaces and remaining gaps

- `full_cohort_graphrag/src/retrieve.py`: `FullCohortRetriever.trial_profile()`,
  `search_trials()` and `compare_planned_outcomes()` already implement bounded,
  read-only evidence retrieval with database identity checks. Search is exact
  normalized condition/intervention matching, not semantic ranking. Profiles
  page at 200 evidence records maximum; comparisons require 1–20 explicit IDs.
- `src/prepare_evidence.py:prepare_evidence()` validates **one response**, keeps
  trial-bound source paths/citations and coverage, and never fetches or merges
  pages. A ranked candidate ID is not a substitute for this evidence contract.
- `src/generate_answer.py:OllamaAnswerGenerator.generate()` consumes prepared
  evidence, permits a single model attempt and only 1–3 authorized fact IDs,
  and fails closed on scope, relevance, source gaps, pagination or selection
  completeness. Its anchored single-field question grammar is deliberately
  narrow. It is not an unrestricted cross-trial explanation engine.
- `src/list_planned_outcomes.py:list_registered_planned_outcomes()` provides
  explicit complete, deterministic single-trial listings without a model call.
  The saved live trace
  `full_cohort_graphrag/results/live_deterministic_listing_NCT00206232_20261024T002220600467Z.json`
  confirms `COMPLETE_LISTING`, seven outcomes, validation passed, zero attempts.
  The separate Ollama path still correctly blocks an incomplete one-fact outcome
  selection. Do not silently replace one path with the other after a failure.
- Root `test_live_graphrag.py` is an executable, single-case live script, not a
  reusable UI or an offline test: importing/executing it connects and generates.
  It was inspected as text only. Existing `full_system_app/app.py` is the frozen
  discontinuation-model/human-review app, not a full-cohort semantic GraphRAG UI.
  Preserve it rather than presenting these separate components as integrated.
- Documentation has drift: the full-cohort README still describes retrieval
  only; parts of `ANSWER_GENERATION.md` describe older generation/relevance
  versions and an example question outside today's supported grammar. A later
  documentation pass must reconcile these with actual code and saved trace
  statuses. Historical `GROUNDED` traces alone do not prove current relevance.
- Environment inspection: `.venv-vector-rag` has torch 2.2.2, NumPy 1.26.4 and
  sentence-transformers 5.1.2, but **no Neo4j driver or Streamlit**. A combined
  serving environment is not yet demonstrated. Do not change the frozen app's
  dependency pins or install packages as part of this diagnosis.

### Numbered remaining implementation plan — not executed

1. **First step: offline MiniLM ranker/export adapter.** After approval, add an
   isolated `full_cohort_graphrag/semantic_v1/` path. Export only the existing
   2,824 approved trial semantic rows (384-D, no type slots) and stable NCT
   ordering to a separately versioned serving bundle with feature/source hashes,
   pinned encoder revision, text policy, scope and deterministic tie rules.
   Implement read-only loading and cosine-ranking tests for a supplied query
   vector. Do not import training truth or training entry points into serving,
   generate new corpus embeddings, tune top-k, or alter existing modules.
2. Add bounded query encoding using `sentence-transformers/all-MiniLM-L6-v2`
   revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` and a
   documented input limit. Keep existing exact-NCT and entity workflows intact.
   Ranking proposes candidate trials only; scores are not clinical probabilities
   or proof that an unlinked trial truly owns a registered measure. Restrict the
   first use to the registered-association retrieval scope actually evaluated.
3. Bridge selected IDs to existing read-only Neo4j profiles/comparisons and the
   evidence adapter. Preserve associations, source versions and page coverage.
   Request a sufficient bounded page or explicitly abstain when incomplete;
   do not silently merge pages or change strict evidence contracts. Keep
   complete single-trial outcome listing separate from 1–3-fact LLM selection.
   Ranked search questions outside today's generator grammar need an explicit
   future scope/validation decision, not a hidden question rewrite.
4. Add offline end-to-end tests for ID-to-evidence mapping, sponsor/outcome
   attribution, irrelevant and unknown queries, missing records, high-volume
   pagination, citation bindings, unsupported clinical premises and abstention.
   Resolve the isolated serving environment, then separately authorize bounded
   read-only/live Neo4j and Ollama integration checks with immutable traces.
   These are functional checks, not another ranking benchmark on the old test.
5. Add a separate minimal demonstration interface with human accept/reject/revise
   records, clearly separating proposed ranks, verified evidence, deterministic
   listings and model-selected facts. Preserve the existing deployed application.
   Revision must not overwrite source evidence or bypass validation.
6. Update architecture/setup/limitations and assemble final Challenge 3 evidence:
   frozen ranking comparisons, diagnostic results, reproducibility commands,
   actual validated traces, failure cases, human–AI decisions and real demo
   captures. Clearly separate association ranking from answer correctness and
   clinical prediction. **Do not draft the final Challenge 3 report yet.**

Only this diagnostic report and a new verification JSON were added/updated on
resumption. No new retrieval implementation, Neo4j/Ollama calls, training,
test-set evaluation, commit or push was performed.
