# Registered planned-outcome association protocol — Step 66C-2

Version: `HTT-GNN-ASSOC-PROTOCOL-v1`.
Dataset: `HTT-P1-AACT-20260905`; graph: `HTT-KG-AACT-20260905-FULL2824-v1`.
Snapshot: September 5, 2026. Source extraction:
`HTT-GNN-FULL2824-EXTRACT-v1`, manifest SHA-256
`3fe45287cc12f4d752545c90c9d63a375370b69d070be47cb04b79398da6b6a3`.

**Status: PROVISIONAL_FAMILY_AUDIT_REVIEW_REQUIRED. Training is blocked.**
This is a reproducible dataset proposal for human review, not a certification
that all clinical-study families or near-duplicate queries have been discovered.
There are no embeddings, fitted models, ranking results, or new clinical facts.
Original graph artifacts, the five-trial prototype, and GraphRAG remain intact.

## Commands

From the project root in the existing Python 3.12 Intel Mac environment:

```bash
.venv-vector-rag/bin/python -B gnn_graphrag/src/prepare_association_protocol.py
.venv-vector-rag/bin/python -B gnn_graphrag/src/prepare_association_protocol.py --validate-only
.venv-vector-rag/bin/python -B -m unittest discover \
  -s gnn_graphrag/tests -p 'test_association_protocol.py' -v
.venv-vector-rag/bin/python -B -m unittest discover \
  -s gnn_graphrag/tests -p 'test_*.py' -v
```

Preparation never overwrites an existing directory. Use `--output-dir` with a
new destination for regeneration. All operations are local and standard-library
only. Source hashes include all 26 pinned full-cohort files, original membership,
extraction outputs, and prior family-review artifacts. All 14 existing metadata
records are checked against their embedded content hashes and source NCT IDs.

Default outputs: `gnn_graphrag/protocols/HTT-GNN-ASSOC-PROTOCOL-v1/`.

## Families and partitions

Every one of the 2,824 trials is screened, with no status, prediction, or model
performance used. Prior CONFIRMED_RELATED, UNRESOLVED and explicit REJECTED
classifications are preserved. No new pair is automatically confirmed or
rejected. Zero rejected pairs means no such adjudication exists, not that all
other pairs were proven related or unrelated.

Candidate rules are recorded in `protocol.json`: exact sufficiently long
normalized titles; or title similarity after bounded informative-token blocking.
Strong unresolved candidates are grouped conservatively. Weaker unresolved
candidate endpoints and their grouped families are quarantined from held-out
evaluation. Shared condition, sponsor or outcome strings alone do not establish
family identity. Full protocol/secondary identifiers are not present for every
trial, and the blocked title screen is not exhaustive.

Family groups receive one split using seed **20261023** and initial **70/15/15**
targets. Greedy allocation balances total trials, outcome-eligible trials and
positive-association counts, with declared deterministic tie-breaking. Actual
counts are saved; targets are not forced. All outcomes of a trial stay in its
supervision partition. The 41 trials without outcomes remain members and ranking
candidates. This is independent of the existing classification-model partitions.

## Queries and truth

All 19,740 original associations retain exact outcome/evidence/source IDs, NCT
owner, measure, type and time frame. The query key uses only Unicode NFKC,
case-folding and whitespace normalization of the registered **measure**.
Punctuation, numerical ranges, units and clinical wording are not silently
changed to merge labels. Multiple exact-normalized owners remain positives,
without claiming clinical endpoint equivalence.

Novel-query evaluation excludes a query from both held-out sets if its owner
trials span partitions, a screened near query spans partitions, or a relevant
family is quarantined. Exact truth records are retained with explicit reasons;
exclusion never deletes original evidence or a trial. Near candidates are
unreviewed and conservatively excluded, not relabeled as equivalent endpoints.

Description duplication is separately audited, including cross-partition
overlaps. Descriptions are not semantic inputs, so boilerplate overlap alone
does not create family identity, positive labels, or an automatic embargo.
The audit can inform later human review. Lexical screens are bounded and cannot
establish exhaustive absence of near duplicates or clinical equivalence.

## Computational graph and training boundary

The observed context graph excludes **all** HAS_PLANNED_OUTCOME message edges
and their reverses: 39,480 edges removed, 61,218 retained. Provenance-only edges
are also forbidden in message passing; all original 79,125 evidence relationships
remain unchanged. The 9,036 context nodes are Trial, ConditionTerm, Intervention
and Sponsor nodes. Held-out trials' non-target registered context is visible.

This is **trial-disjoint supervision within an observed graph**, not fully
inductive unseen-trial generalization. Query nodes are detached: only normalized
measure text is a future query input. Owner NCT IDs, outcome type, time frame,
source identifiers and descriptions are audit/label metadata, not query features.
Existing approved context text is copied into an allowlisted projection; no
new semantic feature engineering, embedding encoding or message passing occurs.

`association_training_data.load_training_data()` reads only five fixed inputs
and a manifest under `training/`. It does not open global catalogs or validation/
test truth. It rejects unknown paths, symlinks, hashes, unexpected fields, target
edges and non-training owner labels. Training is blocked by default; explicit
`audit_only=True` permits inspection but returns `training_permitted=False`.
This is an API boundary, not an OS permissions sandbox. Future training must use
the reviewed entry point rather than bypass it to read raw evidence or truth.

Training negatives are drawn only from training trials. All known training
positives, grouped owner-family members and conservatively identified training
ambiguities are excluded. `negative_candidates()` exposes this exclusion set;
no negatives are actually sampled in this stage. No held-out truth lookup is
needed. Unlinked trials are not established clinical negatives.

## Files and evaluation

- `protocol.json`, `source_audit.json`: policies, limitations and actual coverage.
- `family_pairs.csv`, `family_groups.csv`, `trial_splits.csv`: candidate evidence,
  classifications, grouping, quarantine and assignment.
- `positive_associations.csv`, `query_catalog.jsonl`: complete source-bound audit.
- `query_overlap_audit.csv`, `near_query_candidates.csv`,
  `duplicate_description_audit.csv`: exact/near overlap and review limitations.
- `candidate_trials.csv`: fixed, lexical 2,824-trial universe for every method.
- `truth/train.jsonl`, `truth/validation.jsonl`, `truth/test.jsonl`: separate
  source-bound truth, including embargoed examples and exclusion reasons.
- `evaluation/validation_queries.jsonl`, `evaluation/test_queries.jsonl`:
  measure-only eligible held-out inputs; truth remains separate.
- `message_edge_mask.csv`: every original semantic message edge and its decision.
- `training/`: allowlisted training queries/labels, candidate IDs, families,
  copied safe context text, masked context edges and an independent manifest.
- `split_manifest.json`, `SHA256SUMS`: source/code/output checksums and counts.

Intended metrics are Recall@1/5/10, Hit@1/5/10, MRR, coverage and median/p95
latency, with query-, owner-trial- and family-macro summaries. Recall measures
the fraction of known registered owners, unlike Hit@k. Use paired family-cluster
bootstrap uncertainty and disclose dependence remaining across shared text and
graph neighbors. Rank all 2,824 candidates, breaking score ties by NCT ID.
Keep query encoding, scoring and one-time preparation latency separate.

Compare training-fitted TF-IDF, pinned MiniLM, deterministic non-target neighbor
pooling, untrained GraphSAGE and trained GraphSAGE only after protocol review.
All formal evaluation results remain **NOT_RUN**. Do not alter the five-trial
benchmark or infer prospective/clinical validity from this retrospective cohort.

## Required review before any training

Review the new family candidates and uncertain near-query exclusions; assess
held-out coverage and whether grouping needs revision. Any changes require a
new protocol version rather than tuning this split against model performance.
Planned outcomes are registered measures, not observed clinical results. The
September 2026 snapshot may include amendments and is not an initial-registration
dataset. No clinical effectiveness or termination prediction is being developed
in this protocol stage.
