# Full-cohort Neo4j importer

Graph: `HTT-KG-AACT-20260905-FULL2824-v1`; dataset:
`HTT-P1-AACT-20260905`; snapshot: September 5, 2026.
The pinned manifest supplies all expected counts: 2,824 trials, 28,777 nodes,
79,125 relationships and 19,740 registered planned outcomes.

Manifest SHA-256:
`3ef82624d131b36abc1eb9ad4e89b3439fed9f9600b92262c21bbcbfe6cf8757`.

## Offline validation — safe default

From the repository root, using the existing environment:

```bash
.venv-graphrag/bin/python -B cohort_scaling/import_full_cohort.py
.venv-graphrag/bin/python -B -m unittest discover \
  -s cohort_scaling/tests -p 'test_import_full_cohort.py' -v
```

The dry run does not load credentials, instantiate a driver, connect to Neo4j,
or reread the ZIP. It verifies the manifest pin, original frozen membership,
all prepared-file hashes, safe source caches, exact CSV headers and property
mappings, unique IDs, endpoints, source-record links, provenance, missing evidence,
outcome safeguards and preservation of baseline artifacts. It emits a reproducible
payload hash and a planned transaction count. No output files are overwritten.

The unchanged pilot importer supplies only schema and mapping/helper definitions.
The full importer does not call the pilot credential loader or live importer.
It revalidates the in-memory payload before any future live connection.

## Prerequisites for a separately authorized live import

1. Obtain explicit human approval. No live import has been performed by this step.
2. Have an administrator provision a dedicated, empty local database, for example
   `hearttrialtwin-full2824`. This script never creates a database.
3. Independently confirm the actual target name. Never reuse the Pilot50 `neo4j`
   database or the five-trial Aura database. If using another local instance, use
   its explicit Bolt port. A separate database in the existing Enterprise instance
   is supported; resource usage is shared with the pilot.
4. Supply dedicated credentials scoped to this database with access, node and
   relationship write privileges and permission to create the six uniqueness
   constraints. Avoid a shared administrator account; arrange an exclusive import
   window with no other writers. Offline tests cannot verify server permissions.
5. Ensure adequate free disk space for stores, indexes and transaction logs, and
   adequate RAM. CSV size is not a database-size estimate. Leave several GiB of
   headroom and monitor disk use; the script does not change server memory/log
   settings or establish a guaranteed minimum storage requirement.
6. Keep the pinned artifacts and original frozen manifest available. Changed
   source files or versions require separate review, not bypassing checksum checks.

## Private configuration

Copy `cohort_scaling/full-cohort.env.example` to
`cohort_scaling/.env.full` and fill it privately using a local editor.
Existing `.gitignore` rules exclude `.env.*`. Confirm exclusion with:

```bash
git check-ignore cohort_scaling/.env.full
```

Only `FULL_NEO4J_URI`, `FULL_NEO4J_USERNAME`, `FULL_NEO4J_PASSWORD` and
`FULL_NEO4J_DATABASE` are accepted. Process variables override an explicitly
supplied environment file. There is no fallback to `NEO4J_*`, `PILOT_NEO4J_*`,
or existing credential files, and dotenv variable interpolation is disabled.
No passwords are accepted as command-line arguments or printed in reports.

This importer intentionally accepts only direct `bolt://` or `bolt+s://` URLs
on `localhost`, `127.0.0.1` or `::1`. Routed `neo4j://` and remote hosts are
rejected. The Aura instance ID/endpoint, `neo4j`, `system`, and database names
containing `pilot` are rejected before driver creation. Database names must be
explicit lowercase names; there is no implicit/default database selection.

## Future live command — do not run without approval

For a pre-created database named exactly `hearttrialtwin-full2824`:

```bash
.venv-graphrag/bin/python -B cohort_scaling/import_full_cohort.py \
  --execute --env-file cohort_scaling/.env.full \
  --confirm-database hearttrialtwin-full2824 \
  --confirm-graph-version HTT-KG-AACT-20260905-FULL2824-v1 \
  --batch-size 250
```

The importer checks `CALL db.info()` and empty node/relationship totals before
constraints, then checks emptiness again before data writes. Every session and
query names the selected database explicitly, including constraints and reads.
Only fixed queries are used; clinical values are passed as `$rows` parameters.

All six node types are imported before relationships. Each batch is one explicit,
sequential transaction, with a default maximum of 250 rows and a configurable
range of 1–1,000. Constraints use separate schema transactions. Data transactions
have no automatic retry. Final verification streams every node and relationship
to compare exact identifiers, labels, properties, endpoints and provenance against
the verified local payload, in addition to the manifest totals.

## Failure and rerun policy

Any nonempty target is refused **before constraints or data writes**, whether it
contains a completed graph, a partial import, or unrelated data. There is no
automatic resume, deletion, clearing, or overwrite path. `MERGE` is used only
after the empty-target gate, not as permission to merge into an existing graph.

On failure, JSON reports the stage, file/batch where relevant, confirmed committed
row and transaction counts, and whether a commit acknowledgment was ambiguous.
Raw driver exceptions/connection details are suppressed. Earlier committed batches
and constraints may remain; a lost commit acknowledgment may mean the latest
batch also committed. Stop for human inspection. A later run against that nonempty
target will be refused. Do not automatically delete it or point at a baseline.
An empty target containing only constraints may be retried after human review.

The emptiness checks are not a distributed lock: another authorized writer could
race with import. Database-scoped permissions and an exclusive import window are
operational prerequisites. Existing instances/databases and all source artifacts
remain outside this script's provisioning/cleanup scope.

## Scientific boundaries

These are September 2026 snapshot records, potentially amended after registration.
The frozen membership consists of trials with observed terminal outcomes, not all
registered HF trials. Registered planned outcomes are not observed clinical
results. Missing values remain unchanged; no enrollment, terminal status,
termination reasons, prediction scores or new clinical claims are introduced.
