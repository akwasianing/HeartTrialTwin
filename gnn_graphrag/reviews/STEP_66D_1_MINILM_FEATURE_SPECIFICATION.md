# Step 66D-1 — Pinned full-cohort MiniLM feature specification and audit

Prepared October 24, 2026. **DESIGN ONLY — proposed feature policy, not authorization to encode or train.**

Protocol approval is recorded in [Step 66C-3U](STEP_66C_3U_V2_FREEZE_APPROVAL.md). That approval freezes the research protocol by reference; it does not authorize feature generation. The original internal status remains `PROVISIONAL_FAMILY_AUDIT_REVIEW_REQUIRED`, with `training_permitted=False`.

## 1. Bound protocol and audit scope

| Identity | Required value |
|---|---|
| Protocol | `HTT-GNN-ASSOC-PROTOCOL-v2` |
| Protocol manifest SHA-256 | `b13d662390b687b62a08cc1fb81bd3413f2c9d1fbb3b6ec86438b1a6854cd95b` |
| Dataset | `HTT-P1-AACT-20260905` |
| Graph | `HTT-KG-AACT-20260905-FULL2824-v1` |
| Snapshot | September 5, 2026 |
| Proposed feature-policy/artifact version | `HTT-GNN-ASSOC-FEATURES-v1` |

This audit verified the saved protocol manifest, 35 source-hash entries and 23 output-hash entries, and inspected the training loader, original feature/model implementation, saved prototype report, installed package metadata, installed tokenization/encoding source, and local encoder configuration/files. The protocol audit validator reads audit truth to verify integrity; it must **not** be called inside the future feature-generation data path.

No SentenceTransformer encoder was instantiated, no embedding or model forward pass was computed, and no model-performance results were used to select this policy. A local tokenizer-only audit counted input tokens; it produced no saved token arrays or embeddings. No dependency was installed, network source contacted, or protocol/prototype file edited. Existing regression suites were not rerun for this design-only step.

## 2. Actual existing prototype and reusable assets

| Asset | Verified behavior / reuse boundary |
|---|---|
| [`src/features.py`](../src/features.py) | Exact pinned MiniLM, CPU and local-files-only loading; snapshot-content verification; batch size 16; normalized 384-dimensional semantics; six one-hot type dimensions; float32; repeat-generation hash equality. Reuse concepts/helpers after review, not its five-trial graph loader. |
| [`src/graph_data.py`](../src/graph_data.py) | Hardcoded five-trial graph identity, 26 nodes, 65 original relationships and 80 semantic message edges. Not a full-cohort loader. |
| [`src/extract_graph.py`](../src/extract_graph.py) | Original approved formatting and type order. Original Trial feature text includes NCT ID, which must **not** be copied into the full-cohort feature policy. |
| [`src/extract_full_cohort.py`](../src/extract_full_cohort.py) | Full-cohort Trial allowlist removes NCT ID; all feature text redacts NCT tokens. Existing approved text is the authoritative input, not a new serialization of raw node properties. |
| [`src/model.py`](../src/model.py) | Genuine PyTorch mean aggregation; two seeded layers 390 → 128 → 64, ReLU, evaluation mode; seed 20261022, one PyTorch thread and deterministic algorithms. No PyTorch Geometric dependency. Do not run it in this step. |
| [`src/message_passing_demo.py`](../src/message_passing_demo.py), [`results/message_passing_demo_v1.json`](../results/message_passing_demo_v1.json) | Seeded **untrained** prototype. Saved features were 26 × 390, with repeat semantic maximum difference 0.0. That historical repeat result is not a new full-cohort reproducibility measurement. |
| [`src/association_training_data_v2.py`](../src/association_training_data_v2.py) | Allowlisted training reader; default refuses training, `audit_only=True` returns permission false. Preserve unchanged. A new feature-only reader needs its own reviewed authorization boundary; do not use audit mode to bypass the training block. |

### Existing local environment, inspected without loading the encoder

Interpreter: `.venv-vector-rag/bin/python`, Python **3.12.14**, Intel `x86_64`, macOS **14.8.3**.

| Installed package | Actual distribution version |
|---|---|
| sentence-transformers | 5.1.2 |
| torch | 2.2.2 |
| numpy | 1.26.4 |
| transformers | 4.57.1 |
| huggingface-hub | 0.36.2 |
| tokenizers | 0.22.2 |
| safetensors | 0.8.0 |
| networkx | 3.7 |
| torch-geometric | Not installed; unnecessary for this feature stage |

These are installed-package metadata findings, not a fresh end-to-end encoder runtime test. Use this existing environment rather than installing a new stack. The model's historical `config_sentence_transformers.json` records older creation-library versions; those are not the actual current runtime versions above.

### Verified model/tokenizer identity

- Model: `sentence-transformers/all-MiniLM-L6-v2`.
- Immutable revision: `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.
- Existing snapshot hash: `fa4e0ce8c98e7af6762dcc8d1930113fab9c487f5c59ba80c5e9d3e098b0f8b2`; independently recomputed and matched.
- Local snapshot found at `/Users/lovelaceashong/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. This machine-specific path is an audit finding, not a path to hardcode into implementation.
- Eleven cached files were present: `model.safetensors`, `modules.json`, `config.json`, `sentence_bert_config.json`, `config_sentence_transformers.json`, `1_Pooling/config.json`, `tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json`, `vocab.txt`, `README.md`.
- Hugging Face cache entries are normal symlinks to blobs. Hash their actual bytes and relative snapshot paths using the existing algorithm; do not reject this legitimate cache layout. Fail on broken links or changed content. Repository input/output-path symlink rules remain separately strict.
- BERT configuration: six layers, hidden size 384. Modules: Transformer → attention-masked mean Pooling → Normalize. No CLS/max pooling.
- Effective sentence-transformer maximum length: **256 tokens**, from `sentence_bert_config.json`. BERT positional capacity and tokenizer metadata report 512, but **512 is not the effective sentence-embedding limit**.
- Tokenizer: cached BERT tokenizer configuration, vocabulary and special tokens at the same revision; tokenizer lowercasing enabled. Outer transformer `do_lower_case=False` does not disable the tokenizer's own lowercasing.

The pin agrees with [`vector_rag/data/index_manifest.json`](../../vector_rag/data/index_manifest.json). Do not read or change Chroma storage or reuse five-trial document vectors as full-cohort features.

## 3. Approved inputs and exact projection boundary

The future generator may read only the bound `split_manifest.json`, its `protocol.json` policy metadata, `training/manifest.json`, the approved external freeze/feature-authorization records, and the following checksum-bound payloads. Reading hashes of held-out files from a manifest is not permission to open their contents.

| Input | Fields consumed | Permitted purpose |
|---|---|---|
| `training/context_nodes.jsonl` | `node_index`, `node_id`, `node_label`, `feature_text` | Embed **only** the `feature_text` string; index/ID for linkage and label for one-hot. Reject unexpected fields/labels. |
| `training/queries.jsonl` | Exact source schema: `query_id`, `query_text`, `positive_trial_ids`, `ambiguous_trial_ids` | Embed **only** `query_text`. ID is an ordering key. The two training-label columns may be parsed solely to validate the source schema, then discarded from encoder inputs and feature outputs. Do not construct target edges from them. |
| `training/message_edges.csv` | Existing edge schema | Read-only verification of the 61,218 allowed typed directions and endpoints; never concatenate edge/relationship metadata into text. No edge construction or message passing during feature generation. |
| `candidate_trials.csv` | `candidate_index`, `nct_id` | Verify all 2,824 candidate linkages and ordering against Trial rows; no labels or semantic inputs. |

The existing training loader also opens `training/candidates.csv` and `training/families.csv` to check supervised training boundaries. These are not required inputs to the narrower feature-only reader. Do not import and invoke `validate_saved_protocol()` in that reader, because it opens global/held-out truth. Run broad integrity audits separately from feature generation.

Forbidden in the feature-generation process: `truth/*`, `query_catalog.jsonl`, `positive_associations.csv`, raw full extraction/source CSVs, and any validation/test association-label file. No opening these files to enrich or repair text, choose samples, or backfill missing values. Future evaluation-query encoding must be a separate explicitly authorized entry point reading only its checksum-bound `evaluation/{validation,test}_queries.jsonl` measure-only projection, never held-out truth.

### Actual safe context and training queries

| Label | Count | Preserved original indices | Permitted source attributes already represented in text |
|---|---:|---|---|
| Trial | 2,824 | 0–2,823 | `brief_title`, `study_type`, `phase` |
| ConditionTerm | 1,743 | 2,824–4,566 | `name`, `source_kind` (submitted/browse distinction) |
| Intervention | 3,417 | 4,567–7,983 | `name`, `intervention_type` |
| Sponsor | 1,052 | 7,984–9,035 | `name`, `agency_class` |
| PlannedOutcome | **0** in context | Not applicable | No outcome nodes in computational context |
| SourceDataset | **0** in context | Not applicable | Provenance retained externally, never as a hub feature |

There are **11,712 training query rows**, ordered by stable query ID. Query text is the already-normalized registered measure: Unicode NFKC, casefold and whitespace collapse, as fixed by the protocol. It excludes owner, outcome type, time frame, description and source IDs. Counts of 19,740 source associations and 16,290 global normalized queries are **not** the training-feature row count.

Do not interpret a measure such as mortality as a measured clinical result. It is a registered association query. Context titles may have indirect semantic overlap with outcome measures; the approved protocol does not certify absence of every semantic proxy.

## 4. Proposed Feature Policy Version 1

### Ordering, dimensions and type slots

Preserve context file order and original node indices exactly. Assert unique contiguous indices 0–9,035 and the declared label blocks, with ascending stable import identifiers within label. Do not re-sort arbitrarily, derive trial order from labels, or silently renumber. Training query rows retain their existing strictly increasing query-ID ordering. Keep row-to-ID mappings separate from vectors.

| Type | One-hot offset | Combined matrix column | Full-cohort context use |
|---|---:|---:|---|
| Trial | 0 | 384 | Active |
| ConditionTerm | 1 | 385 | Active |
| Intervention | 2 | 386 | Active |
| Sponsor | 3 | 387 | Active |
| PlannedOutcome | 4 | 388 | Reserved; zero for every context row |
| SourceDataset | 5 | 389 | Reserved; zero for every context row |

Each context row has one active bit among the first four type slots. Retaining six slots preserves prototype compatibility, not permission to reintroduce the excluded classes. `context_features.npy` is **(9,036, 390)**: normalized semantic columns 0–383 followed by exact float32 one-hot columns 384–389. **Do not normalize the concatenated 390-vector:** its norm is approximately sqrt(2), matching the prototype's concatenation semantics.

`train_query_semantic.npy` is **(11,712, 384)**, semantic only. Queries are detached text inputs, not inserted PlannedOutcome graph nodes. No query one-hot or query–trial edge is generated by this policy.

### Text, tokenizer and encoder

1. Pass the already-approved `feature_text`/`query_text` as strings, not dictionaries, IDs, JSON or templates. Verify source hashes first. Preserve source text; no new summaries, prefixes, stemming, numeric stripping, punctuation harmonization or clinical equivalence mapping.
2. The installed sentence-transformer implementation strips outer whitespace before tokenization. Current texts are already canonical. Preserve this behavior; do not add new context casefolding. Use the pinned tokenizer's own normalization/casing and special tokens.
3. Pin fast-tokenizer use, `max_seq_length=256`, single-string inputs, `truncation='longest_first'` with verified right truncation, and batch padding to longest input, as the existing pipeline does. Record token lengths and affected rows. No chunking or mean over invented subdocuments.
4. Current local tokenizer-only audit, including special tokens: context maximum **87**, training-query maximum **88**; **zero** inputs exceed 256. No held-out queries were tokenized in this audit. Default to failing publication if new truncation is detected in this frozen training/context view rather than silently changing what is embedded. Future evaluation views must report/check truncation separately.
5. Use the exact cached model and tokenizer revision above, CPU, float32 weights/computation/output, evaluation mode, inference/no-gradient mode and normalized sentence embeddings. Verify pooling configuration and 384 output dimensions. Do not fine-tune, quantize, use mixed precision, use a prompt prefix, or substitute model variants.
6. Load the verified local snapshot path after hashing its files. Set `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `local_files_only=True`, and no remote custom code. Fail if missing/incompatible; do not resolve a floating revision or download a replacement.

### Missingness and input rejection

Current permitted context has no empty or label-only text, and training queries have no empty text. Approved extraction omits blank attribute values and preserves originals in source metadata; do not impute missing attributes. Reject unknown labels, empty/whitespace-only text, label-only context, invalid types, noncanonical query text, known NCT tokens, source/evidence-linkage markers or unexpected input fields before encoder invocation. Never silently drop a node or query or change counts to accommodate failures.

Missing planned-outcome time frames in the original extraction (528 records) do not authorize adding time frames to measure-only query features. Missingness in source metadata remains evidence, not a generated clinical value.

Generic numeric strings or scientific words are not automatically identifiers or leakage. Use field allowlists plus narrowly tested identifier/linkage checks; avoid deleting legitimate units, drug names or registered measures. A suspicious source text must fail with a reviewable error, not be automatically rewritten in this stage. Screening remains imperfect and must not be described as complete leakage elimination.

### Determinism and numerical limits

- Proposed fixed encoding seed `20261023` (protocol seed; not performance-tuned). Set Python/NumPy/PyTorch seeds, one PyTorch intra-op/inter-op thread, deterministic algorithms and fixed CPU math/thread settings before runtime initialization. Disable tokenizer parallelism. Record actual settings and CPU/runtime versions.
- Batch size **16**, matching the prototype. Fix input order, encode-call boundaries and sentence-transformers length sorting. Record the library behavior, because padding/batch composition can affect floating-point output. Preserve restored original row order after internal sorting. No automatic batch-size fallback on resource failure.
- Use little-endian float32, C-contiguous arrays; finite values required. Verify semantic L2 norms with the prototype's `rtol=1e-5`, `atol=1e-5`. Type dimensions must be exactly 0/1 and sum to one per context row.
- On the same pinned environment and batch schedule, require repeated generation of both payloads to match canonical float32 byte hashes and maximum absolute difference 0.0 before publication. This repeat is a future authorized encoding check, **not performed now**. If it fails, stop rather than choose a relaxed tolerance after seeing results.
- Do not promise bit identity across processors, BLAS libraries, package versions or batching changes. Such a change invalidates cache compatibility; comparison needs separately declared numerical tolerances and review. File hashes prove a specific artifact identity, not scientific validity.

## 5. Leakage and authorization checks

**Allowed observed context:** all 2,824 trial profiles and their non-target condition/intervention/sponsor neighbors, including held-out trial covariates, as approved by the owner. This is not unseen-trial induction.

**Prohibited supervision:** validation/test association owners, labels, target/reverse edges, owner/source IDs embedded in semantic inputs, or any feature derived from withheld associations.

The future generator must:

1. Validate the externally approved protocol-manifest hash and an additional feature-generation authorization record. The current document and freeze approval alone do not satisfy that authorization.
2. Validate only its declared input subset against manifest hashes, strict schemas and non-symlink repository paths. Hash the policy/authorization itself; fail on unknown files or attempts to escape approved roots.
3. Use a small projection type such as `ContextText(row, original_index, linkage_id, label, text)` / `QueryText(row, query_id, text)`. Encoder methods receive `list[str]` only; linkage IDs are written solely to mapping files. Never call `str(row)` or `json.dumps(row)` for an encoder input.
4. Validate the existing 61,218 context edges against four permitted relationship types: `HAS_SUBMITTED_CONDITION`, `HAS_BROWSE_CONDITION`, `HAS_INTERVENTION`, `LEAD_SPONSORED_BY`. Reject any `HAS_PLANNED_OUTCOME`, provenance edge, invalid endpoint, or duplicate typed direction. Preserve source edges unchanged; this stage does not create edge outputs.
5. Keep training query features separate from any later validation/test query cache. Evaluation-query reader and its tests require distinct authorization and must not expose labels. The future trainer may use shared context and training-query vectors only; its validation evaluator is a separate boundary.
6. Never set `training_permitted=True`, modify manifests, call GraphSAGE, fit an optimizer or invoke the original full-graph five-trial demo as a feature-generation shortcut. Feature-only authorization is independent of the currently blocked training reader.

Model caches and API allowlists are not OS-level isolation. Future trainer/evaluator entry points must be reviewed for access controls; no claim of perfect isolation is made here.

## 6. Proposed artifact layout and storage contract

No directories/files in this layout have been created by this design step:

```text
gnn_graphrag/feature_artifacts/HTT-GNN-ASSOC-FEATURES-v1/
  feature_policy.json
  feature_manifest.json
  context_features.npy
  context_index.csv
  train_query_semantic.npy
  train_query_index.csv
  tokenization_audit.json
  VALIDATION_REPORT.md
  SHA256SUMS
```

`context_index.csv`: `row_index,original_node_index,node_id,node_label,feature_text_sha256`. `train_query_index.csv`: `row_index,query_id,query_text_sha256`. Metadata IDs remain outside numeric semantic vectors. Do not copy positive/ambiguous owner lists into feature artifacts. Baselines can view the first 384 context columns without storing a duplicate semantic matrix. Existing training/evaluation truth stays in its approved location.

### Manifest, policy and invalidation

The future `feature_policy.json` must machine-encode Sections 3–5, with schema/version, model/tokenizer identities, input roles, type mapping, ordering, text/tokenization/numerical/batching settings and failure rules. Its canonical JSON hash (UTF-8, sorted keys, compact separators, no NaN) is a new policy checksum. **No machine-readable policy or policy checksum has been generated in this design step.**

`feature_manifest.json` must bind:

- Exact protocol, graph, dataset, snapshot, freeze-approval hash and separately approved feature-authorization hash; do not infer approval from a path or filename.
- SHA-256 of the protocol manifest, policy bytes/canonical policy, training manifest, each actually consumed input, masked edge file, implementation and relevant dependency lock/configuration.
- Immutable encoder/tokenizer revision; snapshot tree hash and per-file relative-name/size/content hashes, including safetensors, tokenizer/vocabulary/special tokens, module/pooling/normalization configs. No floating branch resolution.
- Python/package/OS/CPU/thread/dtype/runtime details, seed, encode batch size/call schedule, tokenizer choice and max length, normalization/pooling, and actual input counts.
- Output filenames, shapes, dtype/endianness/order, row-mapping hashes, `.npy` file hashes and canonical C-order little-endian float32 payload hashes; repeat hashes/differences, finite/norm/one-hot/truncation checks, missingness and failures.
- Generation start/end UTC timestamps and measured runtime, distinguished from deterministic payload identity. Timestamp variation must not redefine feature equivalence; exact manifests remain separately hashed records.

No self-referential manifest hash: put payload/index/report hashes in the manifest, and put the completed manifest's hash plus those files in `SHA256SUMS`. Cache compatibility requires protocol/policy/input/model/runtime/settings identities to match, not merely array dimensions. Any mismatch fails closed; do not overwrite, append to, silently reuse, mix evaluation features or modify the old cache. A changed scientific policy needs a new version.

### Atomic, bounded publication

After separate execution authorization, preflight model availability, RAM/disk and destination absence. Use a unique staging directory on the same filesystem, exclusive file creation and an exclusive writer lock. Write/flush/close arrays (non-object NumPy format; validation with `allow_pickle=False`), write manifests/checksums last, validate the complete staging bundle, then publish with no-clobber atomic directory semantics under the lock. Plain `os.replace` on an existing destination is not acceptable. Readers reject staging/incomplete bundles. If portable atomic no-overwrite directory publication cannot be guaranteed, stop and implement/test the guard before generation.

An existing finalized destination is validation-only, never overwritten, even if compatible. Failures leave an explicitly incomplete staging bundle for review; do not auto-delete arbitrary outputs or promote partial results. Identical reruns need a separately named destination and compare payload identities; they do not overwrite Version 1.

Raw matrix sizes: context 9,036 × 390 × 4 = **14,096,160 bytes**; training queries 11,712 × 384 × 4 = **17,989,632 bytes**; combined approximately **30.6 MiB**, excluding `.npy` headers and metadata. The context semantic portion alone is 13,879,296 bytes. The existing 2 × 61,218 int64 edge representation would be 979,488 bytes if a future trainer materializes it; it is not a new feature artifact here. Cached safetensors occupy 90,868,376 bytes on disk. These are storage calculations, not peak-RAM/runtime measurements.

Encoder/framework/tokenizer allocations can substantially exceed matrix storage. Batch 16 and sequential writes are reasonable starting constraints on this Intel Mac, but CPU inference time and peak RAM remain unmeasured for the full cohort. Do not claim a completion-time estimate. Budget space for staging, output and repeat checks; stream verification and avoid retaining a second complete feature bundle when a bounded rowwise comparison suffices.

## 7. Future offline test plan

Implement these tests before authorizing encoding. Use injected fake encoders and temporary synthetic fixtures: no real encoder downloads, inference, GraphSAGE training, Neo4j or Ollama calls in deterministic unit tests.

1. Protocol/approval/policy binding: wrong version/hash, changed code/input bytes, missing approval, or unexpected filename fails before an encoder call. Freeze approval alone is insufficient.
2. File-access spy: feature-generation path opens only approved input/model files; assert it never opens truth, global catalogs, source nodes or evaluation files. Separate evaluation reader must never open truth/training labels.
3. Exact context row count, original indices, label blocks, all 2,824 candidate mappings, unique IDs and strict query-ID ordering; reject reordered/duplicate/missing rows.
4. Projection/identifier safety: change linkage metadata in a synthetic fixture and verify it cannot change the text sent to a fake encoder; reject NCT/linkage tokens in text and extra fields. Do not alter checksum-pinned fixtures to perform negative tests.
5. Shape/dtype/finite values and six-slot type mapping; last two slots zero, exactly one active permitted slot, first 384 columns normalized, combined features not unit-renormalized.
6. Training query encoder receives measure text only; owner lists never appear in encoded strings or persisted feature files. Empty queries/label-only context fail without row dropping or imputation.
7. Tokenization/truncation contract: effective 256 cap, special tokens, casing, right truncation and padding; over-limit input blocks publication with a diagnostic. Mock the encoder; tokenizer-only checks may use the verified local cache.
8. Local revision/tree/per-file mismatches, broken cache links, unexpected dimensions/pooling/precision or absent dependencies fail with no network fallback. Validation-only mode must never instantiate an encoder.
9. Context-mask validation: reject target/reverse/provenance edges, duplicates or endpoints outside the 9,036 context nodes; preserve all pinned files and never create outcome-owner edges.
10. Repeat/output integrity: identical fake-encoder inputs give matching payload hashes; non-finite, non-normalized, wrong-dimensional or differing repeats fail before publication. Record numerical/environment limitations rather than relax assertions silently.
11. No-overwrite, exclusive lock, interrupted-write and final-publication tests; readers reject incomplete/mismatched bundles. `.npy` loading rejects object/pickle payloads.
12. Cache invalidation for model/tokenizer/config/seed/batch/runtime/policy/input changes; consistent mapping/hash round trips; no accidental existing five-trial/Chroma overwrite.
13. Authorization independence: `training_permitted=False` and original default loader block remain unchanged through audit/feature-only operation. No optimizer, model training or automatic evaluation is reachable from the feature generator.

Real MiniLM repeat validation and peak-resource measurement belong to the later explicitly authorized feature-generation run, not mocked unit-test pass counts.

## 8. Smallest implementation sequence and next gates

1. **Review this specification.** Approve the proposed 390-dimensional policy, explicit six-slot mapping, 384-dimensional detached query features, 256-token contract, strict repetition and bounded publication rules. This document is currently proposed, not owner-approved.
2. **Implement only the feature policy and isolated reader/generator after approval.** Suggested new files: `gnn_graphrag/src/full_cohort_features.py` and `gnn_graphrag/tests/test_full_cohort_features.py`; keep original `features.py`, graph loaders and frozen protocols untouched. Default CLI is `--validate-only` without encoder instantiation. A later execution path must require a separate hash-bound authorization record, not merely a `--generate` flag or a copied freeze document.
3. **Run offline regression/mock tests.** Confirm file access, linkage separation, masks, shapes, reproducibility contracts, atomicity and blocked training; do not regenerate partitions or create full-cohort embeddings.
4. **Obtain explicit Gate B authorization** for actual pinned MiniLM execution, including reviewed policy/configuration, resources, implementation/test results and authorized context/training-query scope. Evaluation-query generation remains separately controlled.
5. **Generate actual features once authorized**, offline/local, to the versioned new destination with fixed schedule and repeat validation; no GraphSAGE message passing or fitting.
6. **Review feature validation**, measured RAM/runtime, hashes, finite/norm/type/order/tokenization checks and repeat results before consuming features for learning.
7. **Obtain separate Gate C authorization** for a prespecified trained ranking experiment: multi-positive objective, train-only negative sampling/exclusions, scoring architecture, baseline fairness, optimizer/budget/early stopping, validation-only selection and checkpoint/test-lock provenance. Do not relax the current loader or permissions as a side effect of feature work.

### Compatible ranking space required later

MiniLM query vectors are 384-dimensional; the existing GraphSAGE trial output is 64-dimensional. Their raw cosine similarity is undefined, and the old five-trial trick of passing target-linked outcome nodes through the same graph must not be reused: all such target edges are masked here.

A defensible future option is a separately specified query projection `384 → 64`, trained jointly with the GraphSAGE trial encoder using training-only registered associations and multi-positive handling, followed by declared normalization/scoring. Architecture, loss, negative distribution and optimization remain undecided until Gate C. Baselines must use their own compatible spaces (for example MiniLM 384-to-384 cosine), identical frozen queries/candidates and declared text/context access. No improvement is assumed, no ranking experiment is run now, and no test performance may be used to choose this feature policy.

**Outstanding approvals:** this design and its implementation plan, followed by separate authorization for actual feature generation and separate authorization for training. Stop after design/audit review.
