# Full-cohort registered-association experiment — RUN v1

This is a separately authorized, CPU-only experiment bound to frozen `HTT-GNN-ASSOC-PROTOCOL-v2`, manifest SHA-256 `b13d662390b687b62a08cc1fb81bd3413f2c9d1fbb3b6ec86438b1a6854cd95b`. See the [external execution authorization](../../reviews/STEPS_66D_66F_EXECUTION_AUTHORIZATION.md), [configuration](experiment_config.json), and [machine-readable authorization](authorization.json).

The task is registered planned-outcome-measure-to-trial association ranking within an **observed graph**, not clinical outcome prediction, treatment effectiveness, discontinuation risk or unseen-trial induction. Registered planned outcomes are not observed clinical results. Target associations and reverses are absent from all message passing. Held-out trial non-target context is intentionally visible. Family screening/embargoes are conservative and incomplete; unlinked trials are not confirmed clinical negatives.

## Components

- `gnn_graphrag/src/full_cohort_access.py`: hash-bound authorization, role-limited readers, independently checked training inputs, test-selection gate, no-overwrite atomic bundles.
- `gnn_graphrag/src/full_cohort_features.py`: exact offline MiniLM, normalized 384-dimensional vectors, six-slot context types (390 total), repeat checks, separate evaluation-query encoding.
- `gnn_graphrag/src/full_cohort_ranking.py`: two-layer GraphSAGE/query projection, multi-positive loss, training-only sampling, exact ranking/metrics and family bootstrap.
- `gnn_graphrag/src/full_cohort_experiment.py`: one prespecified training run, validation selection, baseline evaluation and SVG curves.
- `gnn_graphrag/tests/test_full_cohort_execution.py`: deterministic offline tests, fake encoder and synthetic loss/metric checks; no encoder or database required.

The default original training loader still refuses training; no `audit_only=True` bypass is used to optimize a model. The new path separately verifies the external owner authorization, original false permission/provisional metadata, source hashes, input schemas, training labels, families and masked context. This is an auditable API boundary, not OS-level access control.

## Exact first-execution commands

From the repository root, using the existing `.venv-vector-rag` environment. No dependency installation or model download is performed. These create new artifacts and **refuse to overwrite completed destinations**. Do not rerun completed generation/training/evaluation merely to view results.

```bash
# Source checks only; no encoder is instantiated.
.venv-vector-rag/bin/python -B -m gnn_graphrag.src.full_cohort_features

# Two passes per payload verify exact same-environment float32 repeatability.
.venv-vector-rag/bin/python -B -m gnn_graphrag.src.full_cohort_features --generate context-train
.venv-vector-rag/bin/python -B -m gnn_graphrag.src.full_cohort_features --generate validation

# Fixed settings; validation MRR selects an initial or trained checkpoint.
.venv-vector-rag/bin/python -B -m gnn_graphrag.src.full_cohort_experiment train
.venv-vector-rag/bin/python -B -m gnn_graphrag.src.full_cohort_experiment evaluate-validation

# These refuse before checkpoint selection. Never tune after this test bundle.
.venv-vector-rag/bin/python -B -m gnn_graphrag.src.full_cohort_features --generate test
.venv-vector-rag/bin/python -B -m gnn_graphrag.src.full_cohort_experiment evaluate-test
```

Training reproduction, if separately desired, uses the same configuration/features and a **new** output directory; it cannot overwrite the selected run or automatically trigger test evaluation:

```bash
.venv-vector-rag/bin/python -B -m gnn_graphrag.src.full_cohort_experiment train \
  --output gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/training_reproduction_01
```

Exact bit identity across different hardware/library/thread/batch configurations is not promised. Compare state tensors and ranking outputs, not raw checkpoint/manifest bytes containing measured timings. Any input/config/model mismatch fails rather than silently changing an experiment. Existing feature artifacts can be checked without encoding:

```bash
.venv-vector-rag/bin/python -B - <<'PY'
from gnn_graphrag.src import full_cohort_access as a
from gnn_graphrag.src import full_cohort_features as f
for path in (a.FEATURES,
             a.FEATURES.parent/'HTT-GNN-EVAL-FEATURES-validation-v1',
             a.FEATURES.parent/'HTT-GNN-EVAL-FEATURES-test-v1',
             a.RUN/'training', a.RUN/'evaluation_validation', a.RUN/'evaluation_test'):
    print(path, a.verify_bundle(path)['schema_version'])
context, queries = f.load_arrays()
print('Feature shapes:', context.shape, queries.shape)
print('Frozen selection:', a.selected_checkpoint())
PY
```

## Tests

```bash
.venv-vector-rag/bin/python -B -m unittest gnn_graphrag.tests.test_full_cohort_execution -v
PYTHONPATH=gnn_graphrag/tests .venv-vector-rag/bin/python -B -m unittest \
  gnn_graphrag.tests.test_extract_graph \
  gnn_graphrag.tests.test_graphsage_demo \
  gnn_graphrag.tests.test_trial_ranking_demo -v
```

For the 31 existing read-only Version 1/2 regression methods, use the saved-fixture command in [the freeze approval](../../reviews/STEP_66C_3U_V2_FREEZE_APPROVAL.md). It excludes eight regeneration/mutation tests without counting them as passed/skipped. Original protocol files, partitions and test files are not rewritten.

## Output locations

- `gnn_graphrag/feature_artifacts/HTT-GNN-ASSOC-FEATURES-v1/`: 9,036×390 context matrix, 11,712×384 training-query matrix, row mappings, token/repeat audits, policy and manifest/checksums.
- `gnn_graphrag/feature_artifacts/HTT-GNN-EVAL-FEATURES-{validation,test}-v1/`: separately generated eligible measure-only query vectors (2,068 and 2,219), mappings and provenance.
- `training/`: selected, last and identical-initialization untrained model checkpoints; full epoch history; immutable selection record; training curves and hash manifest.
- `evaluation_validation/`, `evaluation_test/`: five-method results, source-bound per-query ranks/top-10, paired family uncertainty, fitted training-only TF-IDF, comparison SVG and hash manifest.
- `RESULTS.md`: final measured execution report, when completed. No results are implied solely by this setup document.

## Metric and runtime interpretation

Every method ranks the identical 2,824 sorted candidates, including 41 missing-outcome trials and quarantined endpoints. Descending score ties use ascending NCT ID. Recall@K counts retrieved known owners divided by all known owners; Hit@K counts whether any known owner is retrieved; MRR uses the first known owner. Query, owner-trial and family macro results and single/multi-owner strata are reported. Family macro averages owner-trial means within family. Paired 1,000-replicate family bootstrap uses the same sorted families/draws for methods; its MRR interval is for **family-macro MRR**, not query-micro MRR.

The test query population excludes exact/flagged near overlaps and quarantined owners. Coverage within eligible queries is distinct from population retention (2,068/2,651 validation; 2,219/2,652 test). The benchmark does not establish relevance of unregistered semantic matches or exhaustive absence of family/query contamination.

Zero-vector query/candidate counts and informative query coverage are reported separately. Zero-vector queries are not silently dropped: they retain the same deterministic NCT tie-break ranking. This diagnostic does not alter features, scores, configuration or model selection.

Interrupted-run recovery is documented in [RECOVERY.md](RECOVERY.md). The completed validation bundle is reused; the original incomplete context file is preserved and compared to a fresh pinned pass before copying its exact bytes into a new staging bundle. `--resume-context` is only for that checksum-verified partial artifact, not a general cache bypass.

Latency reports actual per-query scoring/ranking median/p95 and one-time representation preparation. MiniLM encoding is measured in batches and reported as total/amortized per-row encoding time, not invented individual query percentiles. Repeat checks and offline model loading add execution cost. No LLM/Neo4j timing is mixed in.

There is one configuration, one seed and one primary checkpoint-selection run. Results do not authorize app release, clinical use, additional model search, graph mutations or modification of original five-trial artifacts.
