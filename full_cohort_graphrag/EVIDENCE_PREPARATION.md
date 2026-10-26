# Offline evidence preparation — Step 1

`src/prepare_evidence.py` accepts one existing `trial_profile`, `trial_search`,
or `planned_outcome_comparison` response. It reads no credentials, creates no
driver, performs no retrieval or graph import, and does not call an LLM.
The existing retriever and queries are unchanged.

```python
from full_cohort_graphrag.src.prepare_evidence import prepare_evidence

bundle = prepare_evidence(saved_retrieval_response)
```

The input must be an existing Python dictionary in the
`HTT-FULL-STATIC-RETRIEVAL-v1` format, not an invented or legacy five-trial
response. The default loads only the local checksum-pinned manifest/membership
contract. An already loaded contract can be passed as `contract=...`.

## Output

- `schema_version`: `HTT-FULL-EVIDENCE-PREPARATION-v1`.
- `retrieval_status`: the original validated COMPLETE/PARTIAL/NOT_FOUND status.
- Dataset, graph, snapshot, manifest hash and complete `source_dataset` metadata.
- `scope`: selected/returned NCT IDs, original pagination and its unit; search
  criteria and matching rule are preserved. For search, selected IDs represent
  only the returned trial page, not all matching trials.
- `completeness`: independent flags for complete evidence, pagination limitation,
  missing source categories, and nonexistent trials. `prepared_all_supplied_evidence`
  means no supplied records were dropped, **not** that other pages were fetched.
- `trials`: deterministically ordered entries, each preserving trial fields,
  the actual Trial→SourceDataset relationship, source coverage and typed
  `categories`: submitted conditions, browse conditions, interventions, lead
  sponsors, and/or registered planned outcomes as appropriate to the workflow.
- Every prepared record retains its original path/evidence ID, node ID,
  properties, relationship and raw semicolon-separated source IDs, source
  references and blank-field flags. Additional `citation_ids` reference the
  separate citations array. `absent_fields` distinguishes omitted properties
  from source properties explicitly containing an empty string.
- `citations`: stable hashed citation IDs keyed by graph version, NCT ID,
  source table/record and evidence path. The full source identifiers and trial
  associations are retained; entity names are never used as join keys. Trial
  metadata citations use its actual `studies.txt` record and `evidence_id=null`
  because retrieval does not assign a path ID to the trial node itself.
- `summary` and `summary_sha256`: deterministic evidence formatting, **not an
  LLM explanation**. Titles/names and planned measure/type/time-frame values
  are quoted; embedded newlines are escaped rather than interpreted. The
  structure retains all approved supplied fields even when optional long
  descriptions/population are not repeated in the summary.

Registered planned outcomes are not observed clinical results. Comparison
formats exact fields per trial; it does not infer equivalence, effectiveness,
or universal similarity, and does not reinterpret the retriever's derived
shared-measure statistics. Snapshot values may contain later amendments.

## Completeness and limits

The adapter does not fetch or merge pages. A final page remains response-local
PARTIAL when it represents only part of the available evidence, even when
`has_more=false`. Available evidence omitted by pagination is never labeled a
missing source record. Existing trials lacking outcomes remain distinct from
nonexistent NCT IDs. Optional blank fields remain unchanged and do not alone
make category coverage incomplete. Source absence is not proof that evidence
never existed outside this pinned graph.

Bounds: 20 trials, 200 records per supplied retrieval page, 4,000 total records,
10,000 citation references, 2,000,000 counted source-property characters, and
250,000 summary characters by default. `max_records` may reduce the record
budget; `max_summary_characters` may be set from 1 to 1,000,000. These are
preparation limits, **not** a guarantee of fitting an LLM context window.
Budget failures raise `EvidencePreparationError` and return no silently
truncated bundle. Smaller explicitly scoped retrieval is required.

Version/coverage contradictions, duplicate paths, wrong trial bindings,
source-reference mismatches, unexpected properties and inconsistent comparison
flat/per-trial evidence are rejected. No model judgment or free-text factual
claim validation is performed at this stage.

This checks internal consistency and the pinned provenance identity of trusted
retrieval responses; it does not independently authenticate every value or
re-query the graph. A completely self-consistent forged response cannot be
disproved without its trusted retrieval/source record. The adapter is not a
general semantic-entailment or clinical-equivalence system.

## Offline tests

```bash
.venv-graphrag/bin/python -B -m unittest discover \
  -s full_cohort_graphrag/tests -p 'test_*.py' -v
```

Adapter tests reuse the existing checksum-verified CSV fixture and fake driver,
block live driver creation, and assert that preparation issues no additional
retrieval calls. No Neo4j, Ollama, embeddings, imports or benchmark run is needed.
No evidence bundles are automatically written to disk.
