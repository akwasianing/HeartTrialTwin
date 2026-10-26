# Consolidated reproducibility guide

Use the existing HeartTrialTwin working tree and pinned artifacts. Commands below
are relative to the repository root. No installation, training, embedding
regeneration or benchmark inference was performed for the final audit.

## 1. Security prerequisite and environments

**Before sharing or publishing:** privately rotate the read-only password that
was found in the example template, update the ignored
`full_cohort_graphrag/.env`, and verify the account's original read-only grants.
Do not put the replacement in chat, `.env.example`, result JSON or command-line
arguments. The sanitized example now contains placeholders only.

The current local setup intentionally uses three environments:

| Environment | Purpose / verified key packages |
| --- | --- |
| `.venv-full-system` | UI: Streamlit 1.64.0, NumPy 2.1.3, PyArrow 24.0.0 |
| `.venv-graphrag` | Backend: Neo4j 6.4.0, python-dotenv 1.2.4 |
| `.venv-vector-rag` | CPU encoder/GNN: Python 3.12.14, torch 2.2.2, NumPy 1.26.4, Sentence Transformers 5.1.2, Transformers 4.57.1, HF Hub 0.36.2, tokenizers 0.22.2, safetensors 0.8.0 |

Saved baseline-evaluation environment also records scikit-learn **1.9.1**, SciPy
**1.17.1** and joblib **1.6.0** in the vector/GNN environment. This is separate
from the earlier frozen clinical-trial classification app's scikit-learn 1.6.1
requirement; do not replace or combine their environments.

Existing declarations: [GraphRAG requirements](../../../graphrag/requirements.txt),
[Vector RAG requirements](../../../vector_rag/requirements.txt),
[older full-system/UI requirements](../../../requirements-full-system.txt).
The exact encoder-package pins are enforced from its feature manifest, including
transitive packages not all pinned in the older requirements files. A fresh
machine needs a separately verified environment/cache/data provision; the
requirements files alone are not asserted to recreate all three stacks exactly.

## 2. Required runtime artifacts

- `full_cohort_graphrag/semantic_v1/demo_v2/` and the unchanged serving/backend
  sources it imports. Streamlit calls only the fixed backend subprocess.
- `artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1/` graph contract,
  original frozen membership dependencies and the separately provisioned local
  Neo4j database **hearttrialtwin-full2824**. See [retrieval configuration](../../../full_cohort_graphrag/README.md).
- `gnn_graphrag/protocols/HTT-GNN-ASSOC-PROTOCOL-v2/split_manifest.json` and
  `candidate_trials.csv`.
- `gnn_graphrag/feature_artifacts/HTT-GNN-ASSOC-FEATURES-v1/`: manifest,
  `context_features.npy`, `context_index.csv`, `feature_policy.json`.
- Local cached `sentence-transformers/all-MiniLM-L6-v2` revision
  `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, with the manifest's exact model/
  tokenizer files. Model snapshot SHA-256:
  `fa4e0ce8c98e7af6762dcc8d1930113fab9c487f5c59ba80c5e9d3e098b0f8b2`.

Serving does not read association truth, training-query vectors, validation/test
query caches or the GraphSAGE checkpoint. These remain research evidence, not
inputs to an interactive retrieval decision. Do not distribute private config.
The complete new full-cohort working tree is not yet published to the existing
GitHub main branch; obtain the reviewed local files/assets rather than assuming
that cloning main already reproduces this final demo.

## 3. Offline artifact verification

From the repository root:

```bash
.venv-graphrag/bin/python -B -m full_cohort_graphrag.semantic_v1.demo
```

This validates pinned MiniLM candidate artifacts and a fixed-vector lookup. It
does not download/encode text, contact Neo4j/Ollama or evaluate benchmark truth.
Expected status: `OK`, `validation_only: true`, 2,824 candidates, 384 dimensions.

The final read-only evidence auditor can be rerun with a **new destination**:

```bash
AUDIT_TMP="$(mktemp -d /tmp/htt-final-audit.XXXXXX)"
.venv-graphrag/bin/python -B reports/final_project/STEP_66G_5_v1/audit_checks.py --output "$AUDIT_TMP/evidence.json"
```

It hashes frozen payloads, checks identity/counts, parses saved benchmark
summaries and scans bounded nonignored text for credential patterns. It does not
select/train models or compute new benchmark predictions. Hashing a frozen truth
file is opaque integrity verification, not use of its labels for model selection.
The original 2.53 GB archive is identified by recorded pinned provenance; this
audit did not re-download or rehash the whole archive.

## 4. Run the demonstration

Ensure local Neo4j is running and the ignored `.env` contains only the dedicated
`FULL_GRAPHRAG_NEO4J_*` configuration. No Aura/importer fallback is used.

```bash
.venv-full-system/bin/python -B -m streamlit run full_cohort_graphrag/semantic_v1/demo_v2/app.py --server.address 127.0.0.1 --server.port 8502 --server.headless true --browser.gatherUsageStats false
```

Open <http://127.0.0.1:8502>. If already running, use that server. Exact lookup
and deterministic listings do not require Ollama. For the optional existing
constrained explanation mode, Ollama must already serve `qwen2.5:1.5b` locally
at `http://localhost:11434`. Do not automatically download a replacement model.

Suggested questions, including safe failures:

```text
What title is registered for NCT00206232?
Who is the lead sponsor of NCT00206232?
What intervention is registered for clinical trial NCT00206232?
What planned outcomes were registered for NCT00206232?
Find trials with registered planned outcomes about quality of life.
Did spironolactone improve survival in NCT00206232?
What planned outcomes were registered for NCT99999999?
What planned outcomes were registered for NCT00000475?
```

The first four return cited facts/complete seven-outcome listing when source
coverage is complete. Discovery preserves scores/ranks and records skipped
candidates. The last three abstain for unsupported clinical evidence, unknown
membership and missing outcomes respectively. Exact-NCT queries never silently
switch to a semantically similar trial.

## 5. Regression commands and current counts

```bash
.venv-graphrag/bin/python -B -m unittest discover -s full_cohort_graphrag/tests -p 'test_*.py' -q
.venv-graphrag/bin/python -B -m unittest full_cohort_graphrag.semantic_v1.test_pipeline full_cohort_graphrag.semantic_v1.demo_v2.test_demo -q
.venv-full-system/bin/python -B -m unittest full_cohort_graphrag.semantic_v1.demo_v2.test_app -q
.venv-vector-rag/bin/python -B -m unittest full_cohort_graphrag.semantic_v1.test_ranking gnn_graphrag.tests.test_full_cohort_diagnosis gnn_graphrag.tests.test_full_cohort_execution -q
.venv-vector-rag/bin/python -B reports/final_project/STEP_66G_5_v1/protocol_checks.py
```

Current results: **102 + 39 + 4 + 44 + 31 = 220 passed**, zero failures/errors/
skips. Eight protocol regeneration/mutation tests are deliberately unselected.
These are offline regression methods, not live-generation accuracy cases.

For exclusive new logs plus the first four suites:

```bash
AUDIT_TEST_TMP="$(mktemp -d /tmp/htt-final-tests.XXXXXX)"
.venv-graphrag/bin/python -B reports/final_project/STEP_66G_5_v1/audit_checks.py --run-tests --output "$AUDIT_TEST_TMP/evidence.json"
.venv-vector-rag/bin/python -B reports/final_project/STEP_66G_5_v1/protocol_checks.py "$AUDIT_TEST_TMP/protocol_tests.txt"
```

The saved-fixture protocol wrapper uses the unchanged tests and their existing
audit-only data path solely for integrity checking. It does not grant training
permission or rewrite datasets.

## 6. Reuse live and experimental evidence; do not repeat expensive work

- [G-3 traces](../../../full_cohort_graphrag/semantic_v1/live_validation/HTT-MINILM-GRAPHRAG-LIVE-v1/summary.json)
  retain original successes, model timeouts and blocked answers.
- [G-4 smoke](../../../full_cohort_graphrag/semantic_v1/demo_v2/validation/HTT-DEMO-v2-SMOKE-v1/summary.json)
  and [actual UI backend trace](../../../full_cohort_graphrag/semantic_v1/demo_v2/validation/ui_live_v1.json)
  substantiate deterministic behavior and bounded discovery.
- [Current service identity/read-only metadata](current_services.json) and two
  [screenshots](CHALLENGE_3_REPORT_EVIDENCE.md#actual-screenshots-versus-instructions)
  are this audit's bounded live checks. No model generation was repeated.

Training/encoding/evaluation commands are preserved in the original
[experiment README](../../../gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/README.md).
They are historical first-execution instructions, **not steps to rerun for a demo
or this audit**. Completed destinations refuse overwrite. Any requested future
training reproduction must use a separate output, preserve this run and avoid
another test-guided selection. A revised model needs independent confirmation.

## 7. Interpretation and troubleshooting

- A failed graph identity, checksum, source association or citation check must
  remain a failure. Do not loosen pins, use live newer AACT records or backfill
  missing evidence to make a demo run.
- Deterministic mode is an explicit default, not a silent repair of invalid
  model output. Optional generation is one attempt with a 60-second request
  timeout; the backend has a 240-second subprocess bound. Timed-out server-side
  inference may continue, so do not repeatedly retry.
- Profiles are bounded at 200 evidence rows; too much or missing source evidence
  abstains. Discovery examines at most ten candidates, three accepted, and is not
  exhaustive clinical search.
- Registered endpoints are not observed effects. Similarity is not clinical
  evidence. The app is local research software, not a clinical recommendation.
- See the final audit for credential rotation, Git/publication status, scan
  exclusions and reproducibility limitations before submission or sharing.
