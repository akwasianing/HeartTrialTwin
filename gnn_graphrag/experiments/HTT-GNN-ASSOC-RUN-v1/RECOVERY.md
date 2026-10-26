# Interrupted execution recovery — October 24, 2026

The owner authorized resuming the existing Steps 66D–66F work through the conversation request **“Resume Steps 66D–66F From Interrupted Execution.”** Configuration and original authorization remain unchanged.

Recovered state was inspected before launching a job. The old process-session IDs were unavailable; writer-lock probes found no holder, and an authorized process inventory found no running encoder Python process. The published validation bundle passed checksums, shape/norm checks and recorded an exact repeat maximum difference of 0.0. It is reused without regeneration or modification.

The original incomplete context/train directory contained only `context_features.npy`, shape 9,036×390, float32, normalized semantic block and reserved type slots zero. Its file SHA-256 was `477a4b7ec0a3f2177e08761dcd22f8ada867fd9ff4f13be69f55c40c4367f494`; canonical matrix SHA-256 was `35532f7fc88af6d97e58b3dd74f2c7b8963be1b7ef92cc12672c893647e20195`. No training-query file or complete manifest was present. Context-generation code writes this file only after its repeat check, but the original timing/audit was not durably retained; a fresh pinned pass is therefore required to independently verify its row-bound values before reuse. No failed determinism check was observed or disabled.

The recovery option verifies the exact preserved file hash and source input location, re-encodes context once, requires zero full-matrix difference, then copies the original bytes into a newly staged bundle. It does not repeat both original context passes, silently repair differences, overwrite the incomplete directory, or invent missing timing metadata. Only the unfinished training queries are encoded twice using the unchanged policy.

No training/checkpoint or benchmark output existed at recovery. Test-query encoding remains blocked until checkpoint selection. The added recovery function and two offline tests do not alter model features, hyperparameters, data, default training guards or the completed validation bundle.

Recovery command, executed only after confirming no active writer:

```bash
.venv-vector-rag/bin/python -B -m gnn_graphrag.src.full_cohort_features \
  --generate context-train \
  --resume-context gnn_graphrag/feature_artifacts/.HTT-GNN-ASSOC-FEATURES-v1.incomplete-jbr_hyxl/context_features.npy
```

Original partial artifacts are retained. Final measured completion status is reported separately in `RESULTS.md`.

## Successful comparison followed by bookkeeping failure

The recovery pass actually completed with **maximum absolute difference 0.0** in **306.81817753199994 seconds**. It then raised `ValueError` while converting the supplied relative path to a repository-relative provenance string. This was not a determinism failure. Training-query encoding had not started. The original partial directory and the second incomplete staging copy remain untouched.

The path bookkeeping now resolves the source path before computing its relative name. The successful comparison was durably recorded from its observed execution output in `context_recovery_verification.json`, binding its original file/payload hashes, source context hash, model revision/tree hash, protocol/configuration/authorization hashes and verification implementation hash. The optional `--recovery-verification` path accepts only that exact hash-bound record and rechecks all bindings, array/type integrity and current tokenizer/model identity. It does not accept a generic assertion that a cache was verified, relax numerical checks, or perform another context encoding pass.

The second resume command adds:

```text
--recovery-verification gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/context_recovery_verification.json
```

This avoids repeating successful inference while preserving the exact successful comparison and recording the later exception explicitly. The unfinished training queries still require two byte-identical passes.
