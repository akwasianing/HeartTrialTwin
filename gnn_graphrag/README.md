# HeartTrialTwin GNN-Enhanced GraphRAG

This directory contains deterministic graph extraction and a CPU-only,
two-layer GraphSAGE message-passing demonstration for the five-trial prototype.
It uses verified local artifacts and does not require a Neo4j connection.

The source graph is versioned as `HTT-KG-AACT-20260905-v1`, derived from the
pinned September 5, 2026 dataset `HTT-P1-AACT-20260905`. The 26-node graph is
an illustrative subset of the 2,824-trial cohort; it is not the complete cohort.

## Extract

From the repository root:

```bash
python3 gnn_graphrag/src/extract_graph.py
```

The command verifies the import manifest and all 16 source CSV hashes before
creating:

- `data/nodes.csv` — stable node indices and approved canonical feature text;
- `data/relationships.csv` — all 65 original directed relationships;
- `data/message_edges_full.csv` — 130 forward/reverse message edges;
- `data/message_edges_semantic.csv` — 80 message edges after excluding only
  `MEMBER_OF_DATASET` and `SOURCED_FROM`; and
- `data/extraction_manifest.json` — versions, policies, checks, and hashes.

Provenance relationships remain in `relationships.csv` and the full message
graph. Their exclusion from the semantic message graph does not delete or
alter the source evidence.

## Test

```bash
.venv-vector-rag/bin/python -B -m unittest discover \
  -s gnn_graphrag/tests -p 'test_*.py' -v
```

## Run the message-passing demonstration

The existing `.venv-vector-rag` environment supplies the compatible Intel Mac
CPU stack: PyTorch 2.2.2, Sentence Transformers 5.1.2, Transformers 4.57.1,
and NumPy 1.26.4. No additional installation is required.

The script resolves only the already cached model revision and forces offline,
local-files-only loading:

- model: `sentence-transformers/all-MiniLM-L6-v2`;
- revision: `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`;
- device: CPU; and
- node features: 384 normalized semantic dimensions followed by six node-type
  one-hot dimensions.

Run once from the repository root:

```bash
.venv-vector-rag/bin/python -B \
  gnn_graphrag/src/message_passing_demo.py
```

The default report is created at
`gnn_graphrag/results/message_passing_demo_v1.json`. The writer refuses to
overwrite an existing report. Supply a new path for a separate run:

```bash
.venv-vector-rag/bin/python -B \
  gnn_graphrag/src/message_passing_demo.py \
  --output gnn_graphrag/results/message_passing_demo_repeat.json
```

The model is a seeded, **untrained** GraphSAGE encoder with dimensions
390 → 128 → 64. Reported cosine and norm-change diagnostics compare full,
zero-neighbor, or ablated representations only within the same layer and
dimensional space. They are message-flow observations, not causal explanations
or evidence of improved retrieval.

This stage performs no model training, LLM generation, live Neo4j access,
Vector RAG index regeneration, or clinical inference. Registered planned
outcomes remain distinct from observed clinical results.

## Run the trial-ranking demonstration

The ranking experiment uses all ten registered PlannedOutcome nodes as queries
and the same five Trial nodes as candidates. It compares cosine rankings in
three separate representation spaces:

- Layer 0: the original 384-dimensional normalized MiniLM component only;
- Layer 1: 128-dimensional seeded, untrained GraphSAGE representations; and
- Layer 2: 64-dimensional seeded, untrained GraphSAGE representations.

```bash
.venv-vector-rag/bin/python -B \
  gnn_graphrag/src/trial_ranking_demo.py
```

The versioned report is created at
`gnn_graphrag/results/trial_ranking_demo_v1.json`; the writer will not
overwrite an existing report. A separate output can be requested explicitly:

```bash
.venv-vector-rag/bin/python -B \
  gnn_graphrag/src/trial_ranking_demo.py \
  --output gnn_graphrag/results/trial_ranking_demo_repeat.json
```

Every target `HAS_PLANNED_OUTCOME` relationship is present during message
passing. The experiment is therefore an in-graph structural sanity check, not
held-out retrieval, prospective evaluation, or evidence that GNN ranking is
better. A future integration could use GNN scores to propose exact NCT IDs,
after which the existing parameterized Neo4j retrieval must still obtain the
source evidence and provenance used by grounded answer generation.
