# MiniLM + full-cohort GraphRAG — opt-in v1

Version: `HTT-MINILM-GRAPHRAG-v1`. This separate CLI path does not replace the
existing retriever, generator, Streamlit prediction app, or any five-trial,
GraphSAGE, Vector RAG or Agentic GraphRAG implementation.

## Actual workflow

1. An explicit NCT registered-field question bypasses semantic search. One NCT
   is supported at a time; malformed or multiple IDs never trigger substitution.
2. Without an NCT, the supported discovery form is:
   **`Find trials with registered planned outcomes about <measure>`**.
   MiniLM ranks all 2,824 trial vectors; default top-k is 3, pipeline cap 5.
   These are fixed engineering bounds, not benchmark-tuned settings.
3. The existing read-only `FullCohortRetriever` verifies database identity and
   fetches each selected profile with limit 200, offset 0. Submitted/browse
   conditions remain distinct. No source categories or missing trials are dropped.
4. Existing `prepare_evidence()` validates trial associations, source paths,
   citations, snapshot identity and complete coverage.
5. Explicit planned-outcome questions use the existing deterministic complete
   listing entry point, not Ollama. Other supported exact-NCT fields use the
   existing one-attempt Ollama catalog-ID generator, with all its original checks.
6. Discovery publishes **candidate evidence**, not a claim that a candidate owns
   the query's measure or that the measures are clinically equivalent. For each
   candidate, the derived question `What planned outcomes were registered for
   <NCT>?` and its derivation flag are visible in the trace. It returns complete
   registered records, not a model-written explanation of semantic similarity.

No hidden rewrite is sent to the LLM for an unsupported original question.
Clinical effectiveness/results/termination questions abstain before retrieval.
Ambiguous or out-of-grammar questions also abstain. This is not unrestricted
natural-language medical QA. Discovery does not call Ollama; its source facts
are deterministically assembled. Exact factual selection is the optional LLM path.

## Frozen data and implementation

- Dataset `HTT-P1-AACT-20260905`; snapshot `2026-09-05`.
- Graph `HTT-KG-AACT-20260905-FULL2824-v1`: 2,824 trials, 28,777 nodes,
  79,125 relationships, 19,740 registered planned outcomes.
- Protocol `HTT-GNN-ASSOC-PROTOCOL-v2`, SHA-256
  `b13d662390b687b62a08cc1fb81bd3413f2c9d1fbb3b6ec86438b1a6854cd95b`.
  Its internal flags are unchanged; serving does not invoke training loaders.
- Existing feature manifest SHA-256
  `e2f167b01b2e83aef1f11ef6e4dba673d741246927a43f30936888beecf99a17`.
  The adapter checks this manifest, the protocol manifest, runtime context/index/
  feature-policy files and candidate CSV. It checks 9,036 x 390 context values,
  canonical payload hash, norms, six-slot types and full node/candidate ordering.
  It uses only Trial rows' first **384 semantic dimensions** for ranking.
- Model `sentence-transformers/all-MiniLM-L6-v2`, revision
  `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. Query loading is CPU/offline-only;
  all cached model files, snapshot hash and recorded package versions are checked.
  Queries use the frozen NFKC/casefold/whitespace policy, normalized embeddings,
  and a verified **256-token** cap. Overlong inputs fail, rather than truncate.
- Cosine scoring uses the existing normalized vectors and stable descending-score,
  ascending-NCT tie breaking. Float roundoff is clipped to [-1,1] before ranking.
  Scores are not probabilities. No new corpus embeddings, index or model fit.
- No training query arrays, association labels, held-out queries/truth or test
  benchmark results are loaded by the serving adapter.

Files: `ranking.py` (feature integrity and encoder), `worker.py` (bounded JSON
process), `bridge.py` (validated process boundary), `pipeline.py` (existing
GraphRAG composition), `demo.py` (CLI), `identity.py` (pinned configuration).

## Existing environments — no installation needed here

The environments are deliberately **not** mixed in one Python interpreter:

- `.venv-vector-rag`: compatible torch 2.2.2, NumPy 1.26.4,
  sentence-transformers 5.1.2 and the pinned local model cache.
- `.venv-graphrag`: Neo4j 6.4.0 and python-dotenv 1.2.4.

The controller invokes the fixed local worker using `subprocess.run`, no shell,
one request, a 180-second timeout and no retries. Neo4j credentials are removed
from the child environment. Only bounded rankings/provenance return over JSON;
raw subprocess errors are not exposed. No package installation or dependency
pin changes were made. These commands assume this existing local checkout and
its verified assets; this is not yet a self-contained public installation bundle.

Run all commands from the project root:

```bash
cd "/Users/lovelaceashong/Desktop/Courses/Fall 2026/Project"

# Default: offline feature validation only; no text encoding, Neo4j or Ollama.
.venv-graphrag/bin/python -B -m full_cohort_graphrag.semantic_v1.demo

# New numeric/encoder-policy checks plus existing diagnostic/execution regression.
.venv-vector-rag/bin/python -B -m unittest \
  full_cohort_graphrag.semantic_v1.test_ranking \
  gnn_graphrag.tests.test_full_cohort_diagnosis \
  gnn_graphrag.tests.test_full_cohort_execution -v

# Mocked integration and all unchanged full-cohort GraphRAG regressions.
.venv-graphrag/bin/python -B -m unittest full_cohort_graphrag.semantic_v1.test_pipeline -v
.venv-graphrag/bin/python -B -m unittest discover \
  -s full_cohort_graphrag/tests -p 'test_*.py' -v
```

## Future authorized live demonstration

Not executed during this implementation. The existing local database
`hearttrialtwin-full2824` must be running with the dedicated read-only account in
the ignored `full_cohort_graphrag/.env`. The original `FULL_GRAPHRAG_NEO4J_*`
configuration and identity/count checks are reused; no Aura/importer fallback.
Do not place credentials in CLI arguments, code or result files.

```bash
# Read-only Neo4j + deterministic seven-outcome listing; no Ollama needed.
.venv-graphrag/bin/python -B -m full_cohort_graphrag.semantic_v1.demo --live \
  --question "What planned outcomes were registered for NCT00206232?" \
  --output full_cohort_graphrag/semantic_v1/results/manual_live_listing_v1.json

# MiniLM candidates + read-only Neo4j + deterministic candidate evidence.
.venv-graphrag/bin/python -B -m full_cohort_graphrag.semantic_v1.demo --live \
  --question "Find trials with registered planned outcomes about quality of life." --top-k 1 \
  --output full_cohort_graphrag/semantic_v1/results/manual_live_candidates_v1.json

# Requires local Ollama with qwen2.5:1.5b already available.
.venv-graphrag/bin/python -B -m full_cohort_graphrag.semantic_v1.demo --live \
  --question "What intervention is registered for clinical trial NCT00206232?" \
  --output full_cohort_graphrag/semantic_v1/results/manual_live_facts_v1.json
```

Use a new output filename for each run; existing paths are rejected before live
calls. Source traces retain raw retrieval, prepared evidence, source citations,
coverage and the original generation/listing trace. No arbitrary Cypher is added.

## Fail-closed limits and research scope

Any missing source category, pagination, bad citation, integrity failure or
unsupported selection abstains. A profile needing more than 200 evidence rows
is not silently paged or merged. Listings retain the original 200-outcome /
50,000-byte cap. All source-bound outcomes are published or none; the 1–3-ID
Ollama contract is unchanged. If any selected candidate fails, no complete
composite answer is published; previously verified evidence remains separate in
the trace. Candidates after the first failure are not attempted. Rank lists
are therefore not proof that every candidate was retrieved.

`GROUNDED_CANDIDATE_EVIDENCE` means source facts were validated, **not** semantic
association/relevance established. No similarity threshold, clinical equivalence,
new performance superiority, unseen-trial generalization or clinical prediction
is asserted. Trial vectors describe approved registered trial context, not an
index of every outcome measure. No performance tuning used the frozen test set.
The terminal-outcome cohort is not all HF registrations. September 2026 records
may contain amendments and are not asserted to be initial-registration values.
**Registered planned outcomes are not observed clinical results.**

See [VALIDATION.md](VALIDATION.md) for actual offline results. Saved offline
demonstrations use the real pinned CSV data through a mocked database; they are
not live Neo4j results or formal retrieval benchmark evaluations.
