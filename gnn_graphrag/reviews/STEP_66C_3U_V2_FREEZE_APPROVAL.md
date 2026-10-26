# Step 66C-3U — Project-owner approval and Version 2 protocol freeze

Record ID: `HTT-GNN-ASSOC-v2-FREEZE-66C3U-1`  
Approval recorded: October 24, 2026.  
Authority: the project owner's explicit instruction in this conversation, headed **“Step 66C-3U — Record Human Approval and Freeze Version 2 Experimental Protocol.”**

**External decision: APPROVED — FROZEN BY REFERENCE for a limited observed-graph registered planned-outcome-to-trial association-ranking experiment.**

This record documents the owner's five decisions and the technical verification performed afterward. It is not a handwritten/electronic signature, independent scientific review, or individual adjudication of unresolved study pairs. No signature or unprovided reviewer identity is asserted.

## 1. Exact scope and artifact binding

| Item | Frozen identity |
|---|---|
| Protocol | `HTT-GNN-ASSOC-PROTOCOL-v2` |
| Bound manifest | [`split_manifest.json`](../protocols/HTT-GNN-ASSOC-PROTOCOL-v2/split_manifest.json) |
| Manifest SHA-256 | `b13d662390b687b62a08cc1fb81bd3413f2c9d1fbb3b6ec86438b1a6854cd95b` |
| Dataset | `HTT-P1-AACT-20260905` |
| Graph | `HTT-KG-AACT-20260905-FULL2824-v1` |
| Snapshot | September 5, 2026 |
| Extraction manifest SHA-256 | `3fe45287cc12f4d752545c90c9d63a375370b69d070be47cb04b79398da6b6a3` |
| Allocation seed | `20261023` |
| Preserved internal status | `PROVISIONAL_FAMILY_AUDIT_REVIEW_REQUIRED` |
| Preserved internal permission | `training_permitted=False` |
| Formal ranking evaluation | `NOT_RUN` |

The external freeze approval does **not** rewrite the protocol, its manifest, training manifest, checksum list, or guards. It binds the current partitions, family assignments, query exclusions/eligibility lists, candidate universe, feature restrictions and computational masks to the exact bytes identified above.

The earlier [Step 66C-3T review package](STEP_66C_3T_V2_PROTOCOL_REVIEW.md) is retained unchanged as a historical proposal. Its PENDING policy/Gate A entries are superseded by the five owner decisions recorded here. Its proposed individual W01–W21 review fields are **not** represented as completed individual scientific reviews: the owner accepted continued conservative quarantine at the policy level while leaving relatedness unresolved.

## 2. Five approved project-owner decisions

| Decision | Owner disposition recorded from this conversation | Preserved scientific limitation |
|---|---|---|
| D1 — Strong unresolved pairs | **APPROVED:** retain conservative co-grouping of all 25 strong unresolved pairs. | These are not newly confirmed related studies. All 25 remain UNRESOLVED; five previously confirmed pairs retain their existing classifications. |
| D2 — Weak candidates | **APPROVED:** retain held-out-query quarantine of the 69 weak-candidate endpoints, while keeping those trials in the candidate universe and observed context. | All 37 weak pairs, including 21 cross-partition pairs, remain scientifically unresolved. Quarantine does not remove all their training supervision, candidates or context, or establish equivalence. |
| D3 — Query contamination | **APPROVED:** retain exact/near-query embargoes and the restricted evaluation population. | Screening is bounded and non-exhaustive; unflagged similarity and residual dependence may remain. Lexical similarity is not clinical equivalence. |
| D4 — Research claims | **APPROVED:** limit claims to registered-association ranking within an observed graph. | No clinical outcome prediction, clinical-effectiveness claim, discontinuation prediction, or inductive unseen-trial generalization is authorized. |
| D5 — Freeze | **APPROVED:** freeze the existing Version 2 partitions, families, exclusions, candidates, feature restrictions and masks against the verified manifest. | Byte integrity is not proof that all leakage is eliminated. Any scientific change requires a separately versioned, reviewed successor, not edits to Version 2. |

The approval covers the documented conservative controls, not a declaration that every candidate pair has been clinically investigated. No pair was merged, reclassified, removed, or individually signed off during this step.

## 3. Frozen population and evaluation boundaries

| Partition | Trials | Source positive associations | Eligible held-out queries | Represented held-out owner trials |
|---|---:|---:|---:|---:|
| Train | 1,976 | 13,819 | Not applicable | Not applicable |
| Validation | 424 | 2,962 | 2,068 | 383 |
| Test | 424 | 2,959 | 2,219 | 401 |
| Total | 2,824 | 19,740 | 4,287 | 784 |

All 2,824 trials remain evaluation candidates in ascending NCT-ID order, including 41 trials without registered planned outcomes and the quarantined trials. Training-only negative candidates remain restricted to 1,976 training trials. Candidate linkage identifiers are metadata, not semantic inputs.

**Validation/test partitions and their eligibility lists are frozen before any model-performance evaluation for this Version 2 experiment.** No GraphSAGE model, embedding, ranking performance, or expected model result was inspected to approve this freeze. Later observed results must not be used to revise partitions, families, embargoes or evaluation membership. A necessary correction requires a documented successor protocol and disclosure of any prior evaluation exposure; it must not be silently presented as the same untouched test.

Held-out trial titles and non-target registered neighbors remain visible in the observed context. Trial-disjoint supervision is not graph-node-disjoint training. This benchmark therefore does not establish inductive generalization to previously unseen trials.

## 4. Independent integrity and isolation verification

Verification on October 24, 2026 used only local pinned artifacts and existing offline checks. No database, encoder, Ollama service, optimizer or training process was invoked.

| Control | Verified result |
|---|---|
| Manifest and provenance | Bound manifest SHA-256 matched exactly; all 35 source-hash entries and 23 output-hash entries passed; `SHA256SUMS` completeness and preparation/loader code hashes passed. |
| Membership and separation | 2,824 unique candidates; 1,976/424/424 trial partitions; grouped families do not cross partitions. Original membership and prior classifications preserved. |
| Family controls | 25 unresolved strong pairs co-grouped/co-partitioned; 69 weak endpoints quarantined; 21 weak cross-partition pairs retained as unresolved. |
| Positive associations | All 19,740 distinct original outcome associations retained across truth partitions; source owners, registered measures, outcome types, time frames, evidence IDs and source-record IDs matched the extraction in existing regression checks. |
| Target and reverse masking | All 19,740 forward `HAS_PLANNED_OUTCOME` edges and their 19,740 computational reverses removed from context. Exactly 61,218 allowed message edges remain; no target or provenance-hub message edges survive. Original graph evidence remains preserved. |
| Training label isolation | Existing loader-access tests passed: only the training manifest and five allowlisted training files are read. Training positive/ambiguous owners are training candidates only; default loading still rejects training. |
| Feature projection | Context contains 9,036 approved Trial/ConditionTerm/Intervention/Sponsor nodes. Context semantic text excludes NCT linkage tokens; queries use normalized measure text only. Owner, source, description, type and time-frame metadata are not query features. Pattern/allowlist checks do not prove absence of every indirect semantic proxy. |
| Candidate ordering | Exactly 2,824 unique candidates, ascending NCT IDs, indices 0–2,823; quarantined and missing-outcome trials retained. |
| Query embargo | All 624 exact cross-partition groups and the 333 query IDs affected by 188 cross-partition near-query pairs excluded from primary held-out evaluation. No quarantined owner remains in eligible query sets. |
| Published evaluation inputs | Validation/test query lists match eligible truth records exactly, with unique IDs and measure-only projections; counts 2,068 and 2,219. |
| Permissions and saved state | Protocol, split manifest and training manifest remain provisional with permission false; `load_training_data()` still raises the existing blocked-training error by default. `audit_only=True` was used solely for verification. |

The source-level audit necessarily checks association truth to verify partition integrity; it is not training access or model-performance evaluation. Future training code must not access global or held-out truth. The loader remains an API boundary, not an operating-system sandbox.

### Existing regression checks actually executed

- **31 passed, 0 failures, 0 errors, 0 skips**, in **26.504 seconds** of unittest execution.
- Version 1: 15 existing read-only regression methods; Version 2: 16.
- The unchanged test methods were supplied with the saved protocol fixtures instead of their normal split-generating setup. No test assertion or production implementation was edited.
- Four regeneration/mutation tests per version were deliberately **not selected**, to honor the instruction not to regenerate splits or modify datasets. They were not counted as passed or skipped. This is not a claim of a new full 39-test run.

Tests not selected in either version:

1. `test_byte_deterministic_regeneration_and_overwrite_rejection`
2. `test_source_integrity_failure_rejected_before_any_output`
3. `test_saved_truth_tampering_detected`
4. `test_training_input_path_injection_is_rejected`

The independent read-only checker embedded in Step 66C-3T was also executed successfully against the actual saved Version 2 files, including code-hash binding, quarantine, candidate ordering and published-query reconciliation.

### Reproduce the selected regression checks without regenerating splits

From the project root, in the existing environment:

```bash
.venv-vector-rag/bin/python -B - <<'PY'
import importlib
import unittest

excluded = {
    'test_byte_deterministic_regeneration_and_overwrite_rejection',
    'test_source_integrity_failure_rejected_before_any_output',
    'test_saved_truth_tampering_detected',
    'test_training_input_path_injection_is_rejected',
}
suite = unittest.TestSuite()
for name in ('test_association_protocol', 'test_association_protocol_v2'):
    module = importlib.import_module('gnn_graphrag.tests.' + name)
    def saved_setup(cls, module=module):
        cls.output = module.protocol.DEFAULT_OUTPUT
        cls.audit = module.protocol.validate_saved_protocol(cls.output)['actual_counts']
        cls.splits = module.protocol.read_csv(cls.output / 'trial_splits.csv')
        cls.partition = {r['nct_id']: r['split'] for r in cls.splits}
        cls.positives = module.protocol.read_csv(cls.output / 'positive_associations.csv')
        cls.catalog = module.protocol.read_jsonl(cls.output / 'query_catalog.jsonl')
        cls.overlaps = {r['query_id']: r for r in module.protocol.read_csv(cls.output / 'query_overlap_audit.csv')}
        cls.inputs = module.training.load_training_data(cls.output, audit_only=True)
    case = module.AssociationProtocolTests
    case.setUpClass = classmethod(saved_setup)
    case.tearDownClass = classmethod(lambda cls: None)
    names = unittest.defaultTestLoader.getTestCaseNames(case)
    assert excluded <= set(names)
    suite.addTests(case(n) for n in names if n not in excluded)
result = unittest.TextTestRunner(verbosity=2).run(suite)
assert result.testsRun == 31 and result.wasSuccessful() and not result.skipped
PY
```

### Protected-artifact preservation

All 25 files in each protocol directory were hashed before and after this operation. Both path sets and contents remain identical. Tree fingerprints below are SHA-256 of UTF-8 JSON serialized with `separators=(',', ':')`, containing sorted `(relative POSIX path, file SHA-256)` pairs. They supplement, not replace, the bound manifest and individual checksums.

| Protected material | Verified unchanged fingerprint |
|---|---|
| Version 1 directory, 25 files | `e6ac09b346e48ed82c03cb86d51b505e03f1adf723a120345f91d0b22c39d077` |
| Version 2 directory, 25 files | `b566d47014dd7023006777f8d6fe72494a2be8b4bd1974680434bd69524a46d6` |
| Earlier Step 66C-3T review document, file SHA-256 | `0e3bdd3ccfa25ec140b9ef7b99c8f5a3f03a28d3daa5e5750aea3e09334af76a` |

## 5. Accepted limitations, not eliminated risks

- Family and near-query screens are non-exhaustive. All 62 unresolved pairs remain unresolved: 25 strong and 37 weak. This approval is acceptance of conservative controls, not new evidence of study identity or clinical equivalence.
- Quarantined endpoints remain context/candidates, and the observed graph contains held-out trial covariates. Shared neighbors can create residual dependence; family-cluster uncertainty estimates cannot certify independence.
- Embargoes restrict evaluation toward non-embargoed measures. Future reports must disclose coverage and cannot extrapolate performance to all 19,740 registered outcomes or all clinical trials.
- Exact-normalized multiple owners are registered positives, not clinical-equivalence labels. Unlinked trials are not proven clinically irrelevant negatives; negative sampling still requires separate approval.
- The September 2026 snapshot can contain amendments, and membership originates in a terminal-outcome-selected cohort. These are not verified initial-registration features or a representative prospective clinical population.
- Registered planned outcomes are registered measures, **not observed clinical results**. This is neither treatment-effect prediction nor discontinuation-risk modeling.
- Hash verification establishes artifact identity, not complete scientific validity or exhaustive absence of leakage. The operational training boundary must remain enforced.

## 6. Separate authorization gates

| Gate | Current disposition | Remaining requirements |
|---|---|---|
| A — Research protocol freeze | **APPROVED externally by project owner through this conversation**, bound to the exact manifest above. | Preserve the approved bytes and document any future successor separately. Internal provisional metadata/guards remain unchanged. |
| B — Deterministic pinned MiniLM features | **NOT AUTHORIZED.** Step 66D requires separate instruction. | Approve local model/revision/file hashes, CPU encoder/package settings, approved context and measure-only input views, stable ordering, isolated query caches, resource bounds, normalization/reproducibility checks and feature-manifest provenance. No owner/source IDs embedded; no target-linked message passing. |
| C — GraphSAGE optimization/training | **NOT AUTHORIZED.** Gate A or B is not training permission. | Approve multi-positive objective, training-only negative policy/exclusions and sampling seeds, baseline fairness, architecture/optimizer/hyperparameters/compute bounds, validation-only early stopping and model selection, locked final-test evaluation, checkpoint/config/data/code hashes, and a reviewed executable authorization mechanism that preserves the pinned artifacts and guards. |

The existing candidate MiniLM revision remains `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` for `sentence-transformers/all-MiniLM-L6-v2`; naming it here does not authorize loading it or generating features. No negative-sampling mixture, optimizer, learning rate, stopping tolerance or training configuration is selected by this approval record.

Future comparisons must retain identical eligible queries, the 2,824-candidate universe, masked context policy, deterministic tie-breaking and declared metrics across methods. Fit TF-IDF on training data only. Any permitted validation-based model selection must not become partition tuning. Freeze the chosen model/checkpoint before formal test evaluation; no test-guided retuning or retrospective split optimization.

## 7. Completion boundary

Only this separate approval record was created. No pinned artifact, earlier review, partition, family classification, source dataset, graph, feature, model or application was changed. No split was regenerated. No MiniLM embeddings, GraphSAGE training, live service calls, commits or pushes occurred.

**Protocol freeze recording and integrity review are complete. Stop here. Feature generation and GraphSAGE training await separate explicit authorization.**
