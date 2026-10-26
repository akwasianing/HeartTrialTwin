# Challenge 3 publication preparation — runtime boundary

This is a source/documentation publication candidate, **not a standalone release**.
The owner has asked to retain the existing password and database. No credentials,
account grants, Neo4j records, frozen experiments, or historical results were
changed for this review. Preparation is not authorization to push.

## Required external provision

The demo uses three existing environments, whose names are part of its fixed
subprocess boundary: `.venv-full-system` (UI), `.venv-graphrag` (backend), and
`.venv-vector-rag` (offline encoder). See the original
[environment guide](../final_project/STEP_66G_5_v1/REPRODUCIBILITY_GUIDE.md).
The older classification app's scikit-learn pins are deliberately separate.

Separately provision and verify:

1. The local **hearttrialtwin-full2824** Neo4j database, with a dedicated read-only
   account. Graph version: `HTT-KG-AACT-20260905-FULL2824-v1`; 28,777 nodes and
   79,125 relationships. The importer is a separately authorized write workflow,
   not part of normal demo startup.
2. The pinned graph bundle and original 2,824-member manifest dependencies.
   Full graph manifest SHA-256:
   `3ef82624d131b36abc1eb9ad4e89b3439fed9f9600b92262c21bbcbfe6cf8757`.
3. Frozen Version 2 protocol payloads, whose manifest SHA-256 is
   `b13d662390b687b62a08cc1fb81bd3413f2c9d1fbb3b6ec86438b1a6854cd95b`.
   Metadata is included for provenance; omitted data/label files must be supplied
   to run all saved-fixture integrity tests. Do not regenerate or revise splits
   merely to get a passing test.
4. The immutable MiniLM context feature bundle: `context_features.npy`,
   `context_index.csv`, `feature_policy.json`, and its original manifest under
   `gnn_graphrag/feature_artifacts/HTT-GNN-ASSOC-FEATURES-v1/`. Runtime manifest
   SHA-256: `e2f167b01b2e83aef1f11ef6e4dba673d741246927a43f30936888beecf99a17`.
5. The exact cached `sentence-transformers/all-MiniLM-L6-v2` revision
   `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, with the encoder manifest's exact
   package/file identities. Loading is CPU-only and local-files-only. The source
   publication does not redistribute third-party model weights or grant a
   license for their redistribution; consult the upstream model license.

The full AACT archive, source caches, large derived CSVs, embedding arrays,
GraphSAGE checkpoints and fitted TF-IDF objects remain local. Original manifests
still describe complete immutable bundles; their hashes must not be rewritten
to disguise omitted files. The trained checkpoint is retained locally for
research, but is not needed by the MiniLM serving path. AACT/ClinicalTrials.gov
source terms and the exact archived snapshot must be checked before distributing
any additional data bundle. No new blanket dataset/model redistribution license
is asserted here.

## Launch and tests on the provisioned local setup

Create `full_cohort_graphrag/.env` from its placeholder template **only if absent**,
and edit it privately. Do not put secrets in command arguments, README examples,
screenshots, traces, or Git. Password rotation remains strongly recommended due
to the documented earlier exposure; the owner has not authorized it in this task.

```bash
.venv-graphrag/bin/python -B -m full_cohort_graphrag.semantic_v1.demo
.venv-full-system/bin/python -B -m streamlit run full_cohort_graphrag/semantic_v1/demo_v2/app.py --server.address 127.0.0.1 --server.port 8502 --server.headless true --browser.gatherUsageStats false
```

Open <http://127.0.0.1:8502/>. Default exact factual lookup and complete registered
outcome listings need no Ollama. Optional constrained generation requires the
existing local Ollama service with `qwen2.5:1.5b`; no model is downloaded by the
demo. Start with the eight examples in the
[demo README](../../full_cohort_graphrag/semantic_v1/demo_v2/README.md).

```bash
.venv-graphrag/bin/python -B -m unittest discover -s full_cohort_graphrag/tests -p 'test_*.py' -q
.venv-graphrag/bin/python -B -m unittest full_cohort_graphrag.semantic_v1.test_pipeline full_cohort_graphrag.semantic_v1.demo_v2.test_demo -q
.venv-full-system/bin/python -B -m unittest full_cohort_graphrag.semantic_v1.demo_v2.test_app -q
.venv-vector-rag/bin/python -B -m unittest full_cohort_graphrag.semantic_v1.test_ranking gnn_graphrag.tests.test_full_cohort_diagnosis gnn_graphrag.tests.test_full_cohort_execution -q
.venv-vector-rag/bin/python -B reports/final_project/STEP_66G_5_v1/protocol_checks.py
```

These are offline regressions, not a new benchmark, training run, or live service
test. Some require the external frozen bundles; a fresh clone without them is
expected to fail closed. Saved validation/test comparisons are descriptive; do
not use the inspected test set for additional model selection.

## Publication inventory

`publication_files.txt` is the exact **proposed**, not staged, file list;
`publication_files.json` records each selected file's SHA-256 and byte count.
The local review scan output is not selected automatically for publication.
No command in these review utilities stages, commits, pushes, or connects to a
database/model service. Existing tracked Challenge 1/2 model artifacts remain
unchanged; the new publication selection adds no model weights.
