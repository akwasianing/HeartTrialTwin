# Step 66G-2 — offline implementation validation

This is an implementation record, **not the final Challenge 3 report** and not
a new association-ranking benchmark. No test-set performance selection occurred.

## Results actually executed

| Suite | Passed | Failed |
| --- | ---: | ---: |
| New MiniLM numeric/integrity/encoder-policy tests | 12 | 0 |
| New mocked integration/worker tests | 17 | 0 |
| Unchanged full-cohort GraphRAG suite | 102 | 0 |
| Existing GraphSAGE diagnostic/execution checks | 32 | 0 |
| **Total distinct tests** | **163** | **0** |

The numeric and existing GraphSAGE checks ran together as 44 tests in 9.049 s;
integration ran as 17 tests in 2.913 s; the existing full-cohort suite ran as
102 tests in 10.865 s. An earlier development pass also passed; it is not added
to the distinct-test total. Run commands are in [README.md](README.md).

The tests cover actual pinned vector dimensions/norms, stable score/ID ordering,
feature/protocol checksum failures, source index corruption, prevention of label
reads, query bounds/truncation refusal, correct ID-to-evidence mapping,
trial-bound citations, seven-outcome completeness, supported factual model
selection, unsupported clinical claims, unknown/malformed IDs, missing source
categories, incomplete pages, worker errors/timeouts, credential suppression,
and exclusive trace creation. Neo4j/Ollama/network calls are mocked or blocked.

## Offline end-to-end demonstration

Question: `Find trials with registered planned outcomes about quality of life.`

- **Real** pinned local MiniLM query encoding; CPU, no download, no new corpus
  embedding generation. Revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.
- Scored all **2,824** existing trial vectors, returning top-k **1** for this
  bounded functional check. No relevance threshold or ranking parameter tuning.
- First candidate: **NCT00939146**, cosine **0.4297686517238617**.
- Read-only Neo4j interface was exercised using the existing **fake driver backed
  by checksum-verified full-cohort CSVs**, not a live database.
- Prepared **28 evidence records** for that candidate; the existing complete
  listing returned `COMPLETE_LISTING` with validated source citations.
- Outer status: **`GROUNDED_CANDIDATE_EVIDENCE`**; no errors.
- Controller elapsed time: **19.353517471 s**, including subprocess/model startup.
- No Ollama generation; no observed clinical results or query association claimed.

Trace: [results/offline_e2e_v1.json](results/offline_e2e_v1.json).
It explicitly records
`OFFLINE_MOCK_NEO4J_REAL_PINNED_CSV_AND_MINILM_NO_LIVE_LLM`.
This shows the implemented path functions with real vectors and verified local
source records; it does **not** prove live server compatibility, general semantic
relevance, association ownership, clinical equivalence, or improved retrieval.

The separate initial encoder-only check is retained as
`results/offline_query_ranking_v1.json`; it is not a GraphRAG answer or a live
trace. The final integrated trace includes explicit dataset/graph/snapshot fields.

The default demonstration command also passed offline feature validation through
the two-environment worker. It ranks a reused existing vector and performs no
text encoding, Neo4j call, or Ollama call.

## Preservation and live boundary

Only new files under `full_cohort_graphrag/semantic_v1/` were created. No original
retrieval/query/evidence/generation/listing source, old app, environment pins,
Neo4j data, embeddings, frozen protocol, checkpoint, or benchmark was modified.
The 51 protected files recorded by Step 66G-1 remain checksum-identical.
There was no training, calibration, test evaluation, commit or push.

Live validation is **NOT RUN**. Before separately authorized live checks:

1. Start the existing local Neo4j database `hearttrialtwin-full2824` and use its
   established dedicated read-only `.env`; the original identity gate must pass.
2. Keep both existing virtual environments and the pinned MiniLM cache available.
   No new dependencies were installed.
3. For the optional exact-NCT factual LLM path only, start local Ollama with
   `qwen2.5:1.5b` already installed. Model timeout/abstention behavior is unchanged.
4. Use one exact seven-outcome listing and one bounded candidate query first,
   saving new traces. Then, if approved, test one supported factual LLM answer.

Missing categories, excessive evidence/output size, failed provenance checks or
unsupported questions remain reasons to abstain, not reasons to relax validators.
