# Completed pinned MiniLM feature validation

Dataset `HTT-P1-AACT-20260905`; graph `HTT-KG-AACT-20260905-FULL2824-v1`; snapshot September 5, 2026. Bound Version 2 protocol manifest: `b13d662390b687b62a08cc1fb81bd3413f2c9d1fbb3b6ec86438b1a6854cd95b`.

## Verified bundles

| Payload | File | Shape | Canonical little-endian float32 payload SHA-256 |
|---|---|---|---|
| Context | [context_features.npy](../../feature_artifacts/HTT-GNN-ASSOC-FEATURES-v1/context_features.npy) | 9,036 × 390 | `35532f7fc88af6d97e58b3dd74f2c7b8963be1b7ef92cc12672c893647e20195` |
| Training queries | [train_query_semantic.npy](../../feature_artifacts/HTT-GNN-ASSOC-FEATURES-v1/train_query_semantic.npy) | 11,712 × 384 | `bc91e82d871c9700d80e5622aeabf75959cee79486421f17f8936d9753e7bff7` |
| Validation queries | [query_semantic.npy](../../feature_artifacts/HTT-GNN-EVAL-FEATURES-validation-v1/query_semantic.npy) | 2,068 × 384 | `88cd59df8b4ba5a6cf6be517f158deac10dd44b7328a61799ec32f61431d4ba2` |
| Test queries | [query_semantic.npy](../../feature_artifacts/HTT-GNN-EVAL-FEATURES-test-v1/query_semantic.npy) | 2,219 × 384 | `25712b8844de58113ca094fd43719a3698061abf44ff01a48980ead7d974d074` |

Manifests/checksum lists separately hash complete `.npy` files, including their headers. Row mapping CSVs bind stable original node/query IDs and exact approved text hashes. No NCT ID or owner/source linkage metadata was supplied to the encoder.

Context indices remain 0–9,035: Trial 2,824; ConditionTerm 1,743; Intervention 3,417; Sponsor 1,052. Semantic columns 0–383 are finite normalized float32; one-hot columns 384–389 follow Trial/ConditionTerm/Intervention/Sponsor/PlannedOutcome/SourceDataset. Every row has exactly one permitted active slot and the last two slots are zero. The combined vector is not re-normalized. PlannedOutcome/SourceDataset nodes do not appear in context.

Pinned encoder revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`; full snapshot hash `fa4e0ce8c98e7af6762dcc8d1930113fab9c487f5c59ba80c5e9d3e098b0f8b2`. Manifests preserve per-file model/tokenizer hashes and package versions. Effective limit 256 tokens, CPU float32, batches 16, one thread; max observed lengths 87/88/80/71 for context/train/validation/test, respectively. No row truncated. All four semantic repeat checks recorded maximum difference 0.0.

The context matrix was copied byte-for-byte from the recovered original file after successful fresh comparison. Its original first-pass timing is deliberately null in the durable audit; [the recovery record](context_recovery_verification.json) preserves the measured successful 306.818-second verification. Training/validation/test first-pass timings are 134.536/48.090/25.500 seconds; repeat-pass durations were not independently recorded. These are not total end-to-end execution times.

The validation bundle was reused unchanged. Test queries were generated separately only after selected-checkpoint provenance existed. Query feature generation did not open held-out association truth. Optimization consumed training features/labels only; shared observed held-out context is permitted by the frozen research scope, not evidence of inductive generalization.

All six execution/feature bundle hashes and the unchanged protocol/prototype checks appear in [final_integrity_audit.json](final_integrity_audit.json). No embedding regeneration or test inference was needed for final verification. Original incomplete artifacts are retained; no frozen files were overwritten.
