# Step 66C-3T — Version 2 human review and protocol-freeze package

Review package: `HTT-GNN-ASSOC-REVIEW-v2-66C3T-1`  
Prepared: October 24, 2026. Preparation and technical verification are AI-assisted; scientific approval remains human-controlled.

**All human decisions are PENDING. This document does not freeze the protocol, authorize feature generation, or authorize training.**

## 1. Artifact identity and current boundary

This review lives outside both checksum-pinned protocol directories. Version 1 and Version 2 must remain byte-for-byte unchanged.

| Item | Bound identity |
|---|---|
| Protocol | `HTT-GNN-ASSOC-PROTOCOL-v2` |
| Manifest | [`split_manifest.json`](../protocols/HTT-GNN-ASSOC-PROTOCOL-v2/split_manifest.json) |
| Manifest SHA-256 | `b13d662390b687b62a08cc1fb81bd3413f2c9d1fbb3b6ec86438b1a6854cd95b` |
| Dataset | `HTT-P1-AACT-20260905` |
| Graph | `HTT-KG-AACT-20260905-FULL2824-v1` |
| Snapshot | September 5, 2026 |
| Extraction manifest SHA-256 | `3fe45287cc12f4d752545c90c9d63a375370b69d070be47cb04b79398da6b6a3` |
| Allocation seed | `20261023` |
| Saved status | `PROVISIONAL_FAMILY_AUDIT_REVIEW_REQUIRED` |
| Saved training permission | `False` |
| Formal ranking evaluation | `NOT_RUN` |

| Partition | Trials | Source associations | Eligible held-out queries |
|---|---:|---:|---:|
| Train | 1,976 | 13,819 | Not applicable |
| Validation | 424 | 2,962 | 2,068 |
| Test | 424 | 2,959 | 2,219 |
| Total | 2,824 | 19,740 | 4,287 |

There are 2,783 trials with registered planned outcomes and 41 without. All 2,824 remain candidates. Validation eligibility retains 383 owner trials; test eligibility retains 401. These counts describe the selected evaluation population, not model performance.

Read-only preparation checks verified the bound manifest, 35 source-hash entries, 23 output-hash entries, and the allowlisted training view. The independent checklist command below was also executed successfully against the saved Version 2 files. The previously reported 39 regression-test passes are historical results, **not a new test run for this document**.

## 2. Five decisions requiring explicit human approval

Recommendations below are proposals, not completed adjudications. For every decision, record a rationale and evidence references. Permitted human dispositions are APPROVE AS DOCUMENTED, REQUEST REVISION, or DEFER. A revised scientific policy requires a new version; do not edit pinned Version 2 files or reroll partitions based on anticipated performance.

### D1 — Retain conservative grouping of strong unresolved candidates

- **Supporting evidence:** [`family_pairs.csv`](../protocols/HTT-GNN-ASSOC-PROTOCOL-v2/family_pairs.csv) contains 25 STRONG/UNRESOLVED pairs, separate from five previously confirmed pairs. [`family_groups.csv`](../protocols/HTT-GNN-ASSOC-PROTOCOL-v2/family_groups.csv) and [`trial_splits.csv`](../protocols/HTT-GNN-ASSOC-PROTOCOL-v2/trial_splits.csv) place every strong unresolved pair in the same family and partition. The 25 pairs represent 23 unresolved groups.
- **Remaining limitations:** Title similarity and shared registered entities are not proof of shared participants, protocols, or clinical equivalence. Full-cohort protocol/secondary identifiers are unavailable. Screening is not exhaustive.
- **Scientific implications:** Grouping reduces identified family-related cross-partition exposure but may group independent studies and reduce effective sample size. The family labels remain UNRESOLVED.
- **Recommended disposition:** Approve conservative co-grouping for this limited experiment without confirming relatedness. Review all 25 rows; prioritize held-out groups, including CHARM Added/Preserved, empagliflozin HFpEF/HFrEF, and the mIBG pair. Preserve prior unresolved prednisone and furosemide decisions.
- **Human review:** **PENDING**. Disposition: ______. Rationale/evidence: ______. Reviewer/date: ______.

### D2 — Accept weak-endpoint query quarantine, with retained context/candidates

- **Supporting evidence:** There are 37 WEAK/UNRESOLVED pairs, 69 distinct quarantined endpoints (43 train, 17 validation, nine test), and 21 cross-partition pairs listed in Section 3. No quarantined owner appears in the primary held-out query sets.
- **Remaining limitations:** Quarantine is an evaluation-query exclusion, not node deletion. These trials remain candidates and observed context; eligible training supervision is not globally removed. Weak candidates are not merged into families.
- **Scientific implications:** Direct held-out query ownership from these candidates is excluded, but residual dependence can remain through candidates, context, other family members not discovered by screening, and training. This is not complete isolation of uncertain study programs.
- **Recommended disposition:** Approve only if the human reviewer explicitly accepts this narrower quarantine for an observed-graph experiment. Complete the 21-row review below. If stronger isolation is required, request a newly versioned protocol rather than changing Version 2.
- **Human review:** **PENDING**. Disposition: ______. Rationale/evidence: ______. Reviewer/date: ______.

### D3 — Accept query embargo, incomplete screening, and evaluation population

- **Supporting evidence:** [`query_overlap_audit.csv`](../protocols/HTT-GNN-ASSOC-PROTOCOL-v2/query_overlap_audit.csv) records 624 exact cross-partition query groups. [`near_query_candidates.csv`](../protocols/HTT-GNN-ASSOC-PROTOCOL-v2/near_query_candidates.csv) contains 188 cross-partition pairs involving 333 query IDs. No flagged ID remains in primary held-out evaluation. Eligibility falls from 2,651 to 2,068 validation queries and from 2,652 to 2,219 test queries; overlapping exclusion reasons must not be added as independent counts.
- **Remaining limitations:** Near-query screening is bounded and non-exhaustive. Lexical adjacency, punctuation similarity, and number/time-point differences do not establish clinical equivalence. Description overlap is audit-only, not a model input or automatic truth merge.
- **Scientific implications:** Primary evaluation emphasizes non-embargoed registered measures, disproportionately excluding generic or repeated measures. Results cannot be generalized to every outcome record. Exact-normalized multiple registered owners remain positives; an unlinked trial is not a proven clinically irrelevant negative.
- **Recommended disposition:** Approve the recorded embargo and coverage with explicit residual-contamination and selection-bias limitations. Retain week-12/week-24 distinctions and the RLX030 c20h/c24h source discrepancy; do not silently correct or merge them.
- **Human review:** **PENDING**. Disposition: ______. Rationale/evidence: ______. Reviewer/date: ______.

### D4 — Restrict experimental claims

- **Supporting evidence:** [`protocol.json`](../protocols/HTT-GNN-ASSOC-PROTOCOL-v2/protocol.json) declares trial-disjoint supervision in an observed non-target graph. All outcome target edges and reverses are masked; held-out trial titles and condition/intervention/sponsor context remain visible.
- **Remaining limitations:** The graph is not an unseen-trial inductive setting. September 2026 records may contain amendments. Membership originates in a terminal-outcome-selected cohort. Residual dependencies may remain despite family-cluster uncertainty estimates.
- **Scientific implications:** The task is registered planned-outcome-measure-to-trial association ranking, not clinical outcome prediction, treatment effectiveness, discontinuation prediction, or prospective risk estimation. Registered planned outcomes are not observed clinical results.
- **Recommended disposition:** Approve only the limited observed-graph claim. Do not describe higher ranking metrics, if later obtained, as clinical validity or unseen-trial generalization.
- **Human review:** **PENDING**. Disposition: ______. Rationale/evidence: ______. Reviewer/date: ______.

### D5 — Freeze the existing Version 2 research artifacts by reference

- **Supporting evidence:** The recorded manifest hash binds the saved files; `SHA256SUMS` includes the manifest. The source/output hashes, family assignments, 19,740 associations, masks, 2,824 candidates, and eligibility lists are independently checkable using Section 4.
- **Remaining limitations:** Byte integrity does not certify scientific validity. A frozen snapshot remains provisional in its original internal metadata, and the current loader refuses training by default. Approval documentation does not bypass this block.
- **Scientific implications:** Freeze means accepting the existing artifact bytes as the research reference, not changing their permission fields. Later changes require a successor version and documented reasons independent of model results.
- **Recommended disposition:** Approve freeze-by-reference only after D1–D4, pair-review dispositions, and checklist sign-off are complete. Preserve the manifest, partitions, masks, candidate universe, and embargo lists exactly.
- **Human review:** **PENDING**. Disposition: ______. Rationale/evidence: ______. Reviewer/date: ______.

## 3. Prioritized cross-partition weak-family review

All 21 pairs remain WEAK/UNRESOLVED and both endpoints are quarantined. Every row requires a human disposition. **No row below declares actual study or clinical equivalence.** Registered-title signals are abbreviated from the pinned [`nodes_trial.csv`](../../artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1/nodes_trial.csv); pair-screen evidence and exact similarities remain in `family_pairs.csv`.

Priority is for review order, not an estimated leakage probability: **P1** indicates explicit study-series, geography, model, phase, or population distinctions that warrant targeted protocol review; **P2** indicates other similar-title candidates. Both priorities must be addressed before approval. No new external evidence was retrieved.

| Case | Trial pair | Partitions, in pair order | Registered-title signal and review question | Priority | Human decision |
|---|---|---|---|---|---|
| W01 | NCT00454818 / NCT01643330 | validation / test | Genetically targeted enzyme replacement, advanced HF; independent protocols or shared study program? | P2 | PENDING |
| W02 | NCT00711360 / NCT01221649 | train / validation | HomeCARE II / J-HomeCARE II in Japan; geographic or participant overlap? | P1 | PENDING |
| W03 | NCT00784095 / NCT01044290 | train / validation | Outlook quality-of-life intervention; companion registration or independent study? | P2 | PENDING |
| W04 | NCT00845286 / NCT00933218 | test / train | MAGIC / Be-MaGIC marathon titles; overlapping program or participants? | P1 | PENDING |
| W05 | NCT00853593 / NCT01365234 | validation / train | LV lead model 4396 / model 20066; device-study family or independent protocols? | P1 | PENDING |
| W06 | NCT00927251 / NCT01365234 | validation / train | LV lead model 4296 / model 20066; review jointly with W05. | P1 | PENDING |
| W07 | NCT01434134 / NCT03760588 | train / validation | Cardiac dysfunction during breast-cancer therapy; continuation or independent protocol? | P2 | PENDING |
| W08 | NCT01480401 / NCT02012179 | train / test | Dietary intervention under 100 mmol / SODIUM-HF; pilot/extension relationship? | P1 | PENDING |
| W09 | NCT01484288 / NCT02627196 | train / validation | Baroreflex activation therapy; shared protocol or merely shared intervention? | P2 | PENDING |
| W10 | NCT01502501 / NCT01502514 | test / validation | Adipose-derived stem cells, non-ischemic versus broader HF wording; population overlap? | P1 | PENDING |
| W11 | NCT01584700 / NCT02146794 | test / validation | Renal artery denervation / renal denervation; duplicate, companion, or independent protocol? | P2 | PENDING |
| W12 | NCT01807221 / NCT01955694 | validation / train | BAY94-8862 phase IIb titles with dose/renal-population differences; shared trial program? | P1 | PENDING |
| W13 | NCT01951625 / NCT01951638 | test / train | SOCRATES-REDUCED / SOCRATES-PRESERVED; shared program versus distinct populations. | P1 | PENDING |
| W14 | NCT02861534 / NCT05093933 | validation / train | Vericiguat MK-1242-001 / MK-1242-035; explicit different protocol numbers need interpretation. | P1 | PENDING |
| W15 | NCT02938052 / NCT03220204 | train / validation | REACH phase II / phase III; sequential study dependence or independent samples? | P1 | PENDING |
| W16 | NCT03203759 / NCT05256303 | validation / train | Hospital-level care at home / rural version; extension, shared program, or independent cohort? | P1 | PENDING |
| W17 | NCT03877224 / NCT03877237 | test / validation | DETERMINE-preserved / DETERMINE-reduced; do not collapse HF populations. | P1 | PENDING |
| W18 | NCT04583527 / NCT05501652 | validation / test | ALLEVIATE-HF-1 / ALLEVIATE-HF-HD; program/cohort linkage? | P1 | PENDING |
| W19 | NCT04838353 / NCT05501652 | validation / test | ALLEVIATE-HF-2 / ALLEVIATE-HF-HD; review with W18 and existing strong grouping. | P1 | PENDING |
| W20 | NCT05042973 / NCT05084235 | train / test | Empagliflozin metabolic / cardiac effects; companion endpoint registrations or independent studies? | P1 | PENDING |
| W21 | NCT05205265 / NCT05332873 | train / validation | Rivet PVS PH-HFpEF / Canada; geographic extension or independent protocol? | P1 | PENDING |

For each W-case, record one of: **retain unresolved + existing quarantine accepted**, **defer pending identified evidence**, or **request successor protocol**. Record supporting protocol/registry references if actually inspected; do not infer confirmation from title similarity, a shared sponsor, or an intervention name. Keeping an unresolved case conservatively excluded can be a valid explicit decision without resolving its identity. PENDING is not acceptance.

The remaining 16 weak pairs are within training, not cross-partition; they and all strong pairs still require D1/D2 policy review. They are not declared safe, unrelated, or removed. Existing stronger grouping links can connect a weak endpoint to other trials; do not assess W-cases as isolated pairs only. Quarantine does not establish that registered measures are clinically equivalent or that source records should be merged.

## 4. Independently verifiable freeze checklist

Technical checks and human approval are different. Tick a box only after recording the verifier, date, command/evidence, and actual result. All approval boxes are intentionally unchecked.

| Check | Required pass condition | Verification evidence |
|---|---|---|
| [ ] Source/manifest integrity | Exact bound manifest; all 35 source and 23 output hashes; checksum-list completeness; preparation/loader code hashes match | Commands below; `split_manifest.json`, `SHA256SUMS` |
| [ ] Membership/partitions | 2,824 unique pinned IDs; counts 1,976/424/424; no overlap or reassignment; 41 missing-outcome trials retained | `trial_splits.csv`, original membership, source hashes, regression tests |
| [ ] Family controls | Five confirmed pairs preserved; 25 unresolved strong pairs co-grouped/co-partitioned; 69 weak endpoints quarantined; all 21 W-cases reviewed | `family_pairs.csv`, `family_groups.csv`, D1/D2 and W-case records |
| [ ] Association integrity | 19,740 distinct source outcomes, partitioned 13,819/2,962/2,959; source owner, evidence ID, measure, type, time frame and source ID unchanged | `positive_associations.csv`, source extraction, `truth/`, metadata-preservation regression test |
| [ ] Target/reverse masking | Remove 19,740 forward and 19,740 reverse target edges; retain 61,218 allowed edges; no provenance messages; original graph preserved | `message_edge_mask.csv`, source message edges, `training/message_edges.csv` |
| [ ] Label isolation | Training loader reads only its manifest and five allowlisted files; 1,976 training candidates; no held-out owners or global truth reads | Loader inspection, loader-access regression test, default training block |
| [ ] Query embargo | All 624 exact groups and both endpoints of 188 flagged cross-partition near pairs excluded; no quarantined owner in held-out evaluation | Query audits and truth/evaluation reconciliation; D3 |
| [ ] Candidate integrity | Identical 2,824 sorted candidates for every evaluation method, including missing-outcome and quarantine trials | `candidate_trials.csv`, exact membership comparison, candidate indices |
| [ ] Feature restrictions | Only approved context `feature_text` and normalized measure queries; no owner/source IDs, outcome labels, status, completion dates, results, enrollment, descriptions or withheld-association-derived fields embedded | Training projection, extraction feature policy, semantic-field regression tests; Gate B plan |
| [ ] Scope/coverage | Observed-graph association ranking only; 2,068 validation and 2,219 test queries; limitations and embargo selection bias accepted | D3/D4, protocol policy, coverage counts |
| [ ] Final decisions | D1–D5 and all W-cases explicitly disposed; reviewer identity/date/rationale recorded; hash-bound approval | Human-authored review record; Gate A below |

### Read-only checks against the actual saved artifacts

Run from the project root. These commands do not regenerate protocols or authorize training.

```bash
shasum -a 256 gnn_graphrag/protocols/HTT-GNN-ASSOC-PROTOCOL-v2/split_manifest.json
.venv-vector-rag/bin/python -B gnn_graphrag/src/prepare_association_protocol_v2.py --validate-only
```

Expected manifest hash is the full value in Section 1. The following independent checks supplement the saved validator (notably code-hash binding, family quarantine and the actual published evaluation inputs):

```bash
.venv-vector-rag/bin/python -B - <<'PY'
import csv, hashlib, json
from collections import Counter
from pathlib import Path
from gnn_graphrag.src import prepare_association_protocol_v2 as p
from gnn_graphrag.src.association_training_data_v2 import load_training_data

b = p.DEFAULT_OUTPUT
assert p.extraction.sha256(b / 'split_manifest.json') == 'b13d662390b687b62a08cc1fb81bd3413f2c9d1fbb3b6ec86438b1a6854cd95b'
m = p.validate_saved_protocol(b)
assert len(m['source_sha256']) == 35 and len(m['files_sha256']) == 23
for name, digest in m['code_sha256'].items():
    assert p.extraction.sha256(Path(p.__file__).with_name(name)) == digest
policy = json.loads((b / 'protocol.json').read_text())
assert m['status'] == policy['status'] == 'PROVISIONAL_FAMILY_AUDIT_REVIEW_REQUIRED'
assert m['training_permitted'] is policy['training_permitted'] is False
splits = {r['nct_id']: r for r in p.read_csv(b / 'trial_splits.csv')}
assert Counter(r['split'] for r in splits.values()) == {'train': 1976, 'validation': 424, 'test': 424}
pairs = p.read_csv(b / 'family_pairs.csv')
strong = [r for r in pairs if r['classification'] == 'UNRESOLVED' and r['strength'] == 'STRONG']
weak = [r for r in pairs if r['classification'] == 'UNRESOLVED' and r['strength'] == 'WEAK']
assert len(strong) == 25 and len(weak) == 37
assert all(splits[r['left_nct_id']]['family_id'] == splits[r['right_nct_id']]['family_id']
           and splits[r['left_nct_id']]['split'] == splits[r['right_nct_id']]['split'] for r in strong)
weak_ids = {r[k] for r in weak for k in ('left_nct_id', 'right_nct_id')}
quarantine = {n for n, r in splits.items() if r['heldout_review_quarantine'] == 'True'}
assert len(weak_ids) == 69 and weak_ids == quarantine
assert sum(splits[r['left_nct_id']]['split'] != splits[r['right_nct_id']]['split'] for r in weak) == 21
flagged = {r[k] for r in p.read_csv(b / 'near_query_candidates.csv')
           if r['cross_partition'] == 'True' for k in ('left_query_id', 'right_query_id')}
assert len(flagged) == 333
catalog = {r['query_id']: r for r in p.read_jsonl(b / 'query_catalog.jsonl')}
exact = {qid for qid, r in catalog.items() if len({splits[n]['split'] for n in r['owner_trial_ids']}) > 1}
assert len(exact) == 624
for split, expected in [('validation', 2068), ('test', 2219)]:
    truth = {r['query_id']: r for r in p.read_jsonl(b / 'truth' / (split + '.jsonl'))}
    published = p.read_jsonl(b / 'evaluation' / (split + '_queries.jsonl'))
    ids = {r['query_id'] for r in published}
    assert len(published) == len(ids) == expected
    assert ids == {qid for qid, r in truth.items() if r['eligible_for_novel_evaluation']}
    assert not ids & (exact | flagged)
    for row in published:
        qid = row['query_id']
        assert set(row) == {'query_id', 'query_text'}
        assert row['query_text'] == truth[qid]['query_text'] == catalog[qid]['query_text']
        assert not truth[qid]['exclusion_reasons']
        assert not set(catalog[qid]['owner_trial_ids']) & quarantine
candidate_rows = p.read_csv(b / 'candidate_trials.csv')
assert [r['nct_id'] for r in candidate_rows] == sorted(splits)
assert [int(r['candidate_index']) for r in candidate_rows] == list(range(2824))
mask = p.read_csv(b / 'message_edge_mask.csv')
removed = [r for r in mask if r['retained'] == 'False']
assert Counter(r['message_direction'] for r in removed) == {'forward': 19740, 'reverse': 19740}
inputs = load_training_data(b, audit_only=True)
assert inputs.training_permitted is False and len(inputs.candidate_ids) == 1976
assert len(inputs.context_nodes) == 9036 and len(inputs.message_edges) == 61218
try:
    load_training_data(b)
except p.ProtocolError:
    pass
else:
    raise AssertionError('Default training block missing')
print('PASS: saved hash, policies, family controls, embargoes, candidates, masking and blocked training view')
PY
```

For independent regression verification, the following command runs the existing Version 1 and Version 2 tests (39 previously reported). These tests regenerate temporary copies and remove them; they do not overwrite pinned directories. Record the new actual count/result if run. They were not rerun when preparing this document.

```bash
.venv-vector-rag/bin/python -B -m unittest discover \
  -s gnn_graphrag/tests -p 'test_association_protocol*.py' -v
```

In particular, inspect the Version 2 tests named `test_every_original_association_and_metadata_are_preserved`, `test_truth_partition_is_complete_unique_and_trial_disjoint`, `test_training_loader_never_reads_heldout_truth_or_global_catalog`, and `test_semantic_training_inputs_exclude_linkage_and_heldout_query_metadata`. The checksum-bound source text still requires scientific inspection: absence of known identifier patterns cannot establish absence of every indirect semantic proxy. Human checklist sign-off is not replaced by a successful command.

## 5. Three separate authorization gates

### Gate A — Approve a frozen research protocol

**State: PENDING.** Requires D1–D5, W01–W21 dispositions, checklist evidence, reviewer identity/date, accepted residual risks, and the exact manifest hash. Approval may accept retaining unresolved classifications with conservative controls; it must not claim they were scientifically resolved.

Freeze by external decision record; retain the original provisional status and `training_permitted=False` in pinned files. Any need to change families, partitions, masks, or embargoes requires a successor version and renewed checks. No embeddings or optimization are authorized by Gate A. No model performance has been consulted for this decision.

### Gate B — Authorize deterministic pinned MiniLM feature generation

**State: PENDING; separate explicit permission required after Gate A.** Before execution, approve a feature-generation specification covering:

- Local/offline `sentence-transformers/all-MiniLM-L6-v2`, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, CPU, normalized 384-dimensional semantic vectors. Verify local model-file hashes and actual package versions; do not download or silently substitute a model. The revision is already recorded in [`vector_rag/data/index_manifest.json`](../../vector_rag/data/index_manifest.json), but existing five-trial vector storage is not a full-cohort feature cache.
- Exactly the approved context `feature_text` and measure-only query text; metadata IDs remain linkage only. Do not embed outcome-owner, evidence/source-record IDs, descriptions, clinical results, status, enrollment, completion dates, or withheld target associations. No trainable ID embeddings.
- Stable node/query ordering and separate cache namespaces for context and queries. Hash the feature policy, text inputs, model files/revision, encoder settings, ordering, protocol manifest, edge mask, and output bytes. Record dtype, dimensions, normalization tolerance, batch size, threads, finite-value and repeatability checks; investigate rather than silently accept differing hashes.
- Test-query feature caches isolated from training consumers; no query-owner labels or held-out truth provided to the encoder/trainer. Visible held-out trial context is allowed only under the Gate A observed-graph scope. No global target-linked message passing.
- Resource/storage estimate and feature integrity tests; no optimizer, fitted calibration, new labels, or GraphSAGE training. Proposed future code must preserve the default training block and never use `audit_only=True` as a training authorization bypass.

Gate B does not authorize GraphSAGE optimization or formal ranking evaluation. Stop after approved feature generation and validation for review.

### Gate C — Authorize GraphSAGE optimization and training

**State: PENDING; separate explicit permission required after Gate B.** Approve an experiment specification before any optimization:

| Requirement | Decision/evidence required before training |
|---|---|
| Positive/multi-positive objective | Use all known exact-normalized registered training owners; specify loss, per-query/per-trial weighting, query encoder and trial scorer. Never force a multi-owner query into an arbitrary single-positive label. No clinical-equivalence merges. |
| Negative sampling | Fix training-only pool, seed, negatives per query, uniform/hard mixture and hard-mining source/schedule. Exclude known training positives, grouped owner families and screened training ambiguities via the approved inputs. Do not consult held-out truth to mine/filter training negatives. Unlinked means unregistered association, not a clinical negative; document residual false-negative risk. |
| Baseline fairness | Freeze the same eligible queries, all 2,824 candidates, tie-breaks, approved evidence/text and ranking metrics. Fit TF-IDF vocabulary/IDF on training data only. Pin MiniLM. Neighbor pooling, untrained GraphSAGE and trained GraphSAGE must use the same masked non-target context; declare architecture-specific differences and no target-edge access. |
| Optimization | Prespecify architecture, initialization seeds, trainable/frozen components, optimizer, learning rate, weight decay, dropout, batch/sampling scheme, epochs and compute budget. No values are selected by this document. |
| Early stopping/model selection | Prespecify validation metric, direction, patience, minimum improvement rule, maximum epochs and checkpoint tie-break. Bound the configuration search. Training optimization consumes training supervision only; a separate evaluator may use validation truth for declared selection, never test truth. |
| Test lock/evaluation | Freeze selected configuration/checkpoint before one formal test evaluation. Specify Recall/Hit@1/5/10, MRR, query/trial/family summaries, coverage, encoding/scoring latency and paired family-cluster bootstrap (protocol: 1,000 replicates, fixed seed). Document residual dependence; do not optimize splits or exclusions from results. |
| Checkpoint provenance | Bind model and optimizer state, epoch/selection reason, seeds, code/config/environment hashes, training-view/feature/protocol/mask hashes and logs. Record CPU determinism controls and reproducibility tolerances. No credentials or held-out truth in training checkpoints. |
| Executable authorization | Implement and review an explicit training-authorized entry point only after approval, bound to the frozen protocol and approved experiment. Preserve original pinned manifests and default blocked loader; do not bypass its permission checks. Add tests preventing held-out-label or target-edge access. |

Trial-disjoint labels do not make the graph inductive. Clinical effectiveness, prospective discontinuation, and unseen-trial claims remain outside all three gates.

## 6. Human completion record and recommendation

| Approval item | Current decision | Reviewer/date | Rationale/evidence record |
|---|---|---|---|
| D1 strong grouping | PENDING | ______ | ______ |
| D2 quarantine/context boundary | PENDING | ______ | ______ |
| D3 embargo/population | PENDING | ______ | ______ |
| D4 experimental claims | PENDING | ______ | ______ |
| D5 freeze-by-reference | PENDING | ______ | ______ |
| W01–W21 individual dispositions | PENDING | ______ | ______ |
| Integrity/review checklist sign-off | PENDING | ______ | ______ |
| Gate A protocol approval | PENDING | ______ | ______ |
| Gate B feature-generation authorization | PENDING | ______ | ______ |
| Gate C optimization/training authorization | PENDING | ______ | ______ |

**Recommendation: CONDITIONAL GO for freeze-by-reference after explicit Gate A human approval.** The observed controls support a reproducible, limited registered-association benchmark, not a certification that all leakage is eliminated. The smallest next step is human completion of this record, particularly the weak cross-partition cases and accepted quarantine meaning. If those controls are unacceptable or new evidence requires scientific changes, do not freeze Version 2; prepare a separately reviewed successor protocol instead.

No approval, feature generation, training, database change, commit, or push is performed by preparing this package.
