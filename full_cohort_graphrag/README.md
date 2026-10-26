# Full-cohort Static GraphRAG — retrieval only

Separate read-only retrieval for `hearttrialtwin-full2824`. It does not replace
the five-trial `graphrag/` implementation, importer, or other RAG components.
No LLM, embeddings, automatic ingestion, or benchmark evaluation is included.

## Pinned contract

- Dataset: `HTT-P1-AACT-20260905`; snapshot: **September 5, 2026**.
- Graph: `HTT-KG-AACT-20260905-FULL2824-v1`.
- 2,824 trials; 28,777 nodes; 79,125 relationships; 19,740 planned outcomes.
- Manifest: [full_cohort_manifest.json](../artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1/full_cohort_manifest.json).
- Manifest SHA-256: `3ef82624d131b36abc1eb9ad4e89b3439fed9f9600b92262c21bbcbfe6cf8757`.

Local initialization checks the manifest hash, pilot-independent full membership
CSV hash, original frozen manifest hash, and membership identity/uniqueness.
Before retrieval, the live path checks the actual database name, total counts,
all six label counts, all seven relationship-type counts, and the complete
SourceDataset provenance against the pinned manifest. Counts are derived from
the manifest, not substituted five-trial constants. This is an identity gate,
not a cryptographic audit of every live property; offline import validation and
exclusive preservation of the pinned database remain important.

## Configuration

Use the existing `.venv-graphrag` environment with its installed Neo4j driver
and python-dotenv. No dependency installation or model download is required.
Copy `.env.example` to the ignored `full_cohort_graphrag/.env` and enter a
**dedicated read-only** username/password privately. Do not reuse write-capable
import credentials. Required variables:

```text
FULL_GRAPHRAG_NEO4J_URI=bolt://127.0.0.1:7687
FULL_GRAPHRAG_NEO4J_USERNAME=<enter privately>
FULL_GRAPHRAG_NEO4J_PASSWORD=<enter privately>
FULL_GRAPHRAG_NEO4J_DATABASE=hearttrialtwin-full2824
```

Only these variables are read. An explicit `--env-file` or this module's `.env`
is used; process variables take precedence. There is no fallback to `NEO4J_*`,
`FULL_NEO4J_*`, pilot credentials, or Aura files. Dotenv interpolation is disabled.
Only local direct `bolt://`/`bolt+s://` connections and the exact full database
are accepted. No routed remote target or default/pilot database is accepted.

```bash
git check-ignore full_cohort_graphrag/.env
```

## Offline tests — no database or model required

Run from the repository root:

```bash
.venv-graphrag/bin/python -B -m unittest discover \
  -s full_cohort_graphrag/tests -p 'test_*.py' -v
```

Tests use checksum-verified local CSV fixtures and an in-memory fake Neo4j
driver. Live driver creation is blocked during tests. They cover the six
inspection cases: NCT00206232 (seven outcomes), NCT00057356 (missing browse),
NCT00000475 (no outcomes), NCT00012818 (neither), NCT05256303 (108 outcomes),
and unknown NCT99999999. No live connection is established by the test suite.

## Supported workflows — future authorized live commands

**The following commands connect to Neo4j; do not run until live testing is approved.**
They print JSON and do not save/overwrite traces or modify the database.

Exact profile, with independently typed submitted and browse condition evidence:

```bash
.venv-graphrag/bin/python -B -m full_cohort_graphrag.src.retrieve \
  profile --nct-id NCT00206232 --limit 50 --offset 0
```

Search by exact registered entity strings after Unicode NFKC, whitespace and
case normalization; the condition must be a **submitted** condition. No synonyms
or clinical equivalences are inferred. Search pages trials first, without
requiring sponsors, browse terms, or outcomes. Each returned profile has a
separate evidence page:

```bash
.venv-graphrag/bin/python -B -m full_cohort_graphrag.src.retrieve \
  search --condition 'heart failure' --intervention spironolactone \
  --trial-limit 5 --limit 50 --offset 0
```

Explicit-subset planned-outcome comparison; duplicate IDs and implicit all-cohort
comparisons are rejected:

```bash
.venv-graphrag/bin/python -B -m full_cohort_graphrag.src.retrieve \
  compare --nct-ids NCT00206232 NCT00000475 NCT00012818 \
  --limit 50 --offset 0
```

## Pagination, coverage and provenance

- Evidence page default: 50 records; allowed range: 1–200. Search defaults to
  five trials per page, with at most 20. Comparison requires 1–20 explicit IDs.
- Every query has an explicit result bound and 30-second server transaction
  timeout. Queries are fixed/allowlisted; values and page bounds are parameters.
  Count aggregations may examine more nodes than their bounded returned rows.
- Evidence ordering is NCT ID, relationship type, then stable entity ID. This
  is deterministic lexical ordering, not relevance ranking or numeric ID order.
- `pagination` reports total, returned, offset, limit, next offset and
  `all_evidence_returned`. Later pages alone are never labeled a complete result.
- Profile coverage separates submitted conditions, browse conditions,
  interventions, lead sponsors and registered planned outcomes. `source_status`
  distinguishes available-but-not-returned evidence from no linked source record.
- `COMPLETE` means all requested categories have records and all evidence in the
  requested scope is returned. It does **not** assert every optional source field
  is populated. Blank strings remain unchanged and are listed in `missing_fields`.
- `PARTIAL` means a source category is missing, some requested trials are absent,
  or pagination is incomplete. `NOT_FOUND` means no trial/search match exists in
  the pinned membership/scope. Known trials without outcomes are never discarded.
- Search `--offset` pages matching trials. `--limit` limits evidence within each
  returned trial; use the profile workflow with its `next_offset` to fetch more.
  Coverage outside the returned trial page is not assumed complete.
- Comparison pagination is across the selected trials' outcome paths, not trials.
  Per-trial coverage retains zero-outcome and unknown trials. Exact shared-measure
  computation is deferred unless all outcome pages are returned in one response.
  It compares literal, case-sensitive names only, with no clinical interpretation.
- Each evidence record carries its NCT association, stable path identifier,
  category, approved node fields, actual relationship properties and source
  references. Semicolon-separated `source_record_ids` remain unchanged in the
  relationship; individual table/record/NCT citations are also supplied.
- The enclosing envelope supplies verified dataset/graph versions, snapshot,
  archive/frozen-membership checksums, and SourceDataset metadata. Profiles also
  carry the actual Trial→MEMBER_OF_DATASET path. Never detach citations from
  their envelope or imply that unqueried provenance edges were retrieved.

## Safeguards and remaining limitations

Registered planned outcomes are not observed clinical results. Snapshot values
may include later amendments and are not asserted to be initial-registration
records. The terminal-outcome membership is not all registered HF trials.
An absent link means no linked evidence in this pinned graph, not proof that
the information never existed. Source values are not backfilled.

Cypher and Python both use property allowlists. Enrollment, trial status,
termination reasons, predictions, completion/submission dates, and arbitrary
extra properties cannot be exposed. Source snapshot metadata and planned
measurement time frames remain allowed. Raw driver exceptions and credentials
are suppressed; all operations use explicit database selection and read routing.
Read routing is not authorization: the server account must actually be read-only.

Exact trial retrieval uses the existing unique `trial_id` key. Entity search
can scan this modest cohort; no indexes are created or changed here. Query plans,
real latency, actual server privileges, and live Cypher behavior still require a
separately approved smoke test. Count and page queries are separate transactions;
concurrent graph edits can invalidate pagination. Treat this pinned graph as
immutable during retrieval. No generator integration is provided.
