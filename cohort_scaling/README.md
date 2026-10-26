# Isolated 50-trial pilot importer

Pilot: `HTT-KG-AACT-20260905-PILOT50-v1`, dataset `HTT-P1-AACT-20260905`,
snapshot September 5, 2026. Expected counts are derived from the checksum-pinned
`pilot_manifest.json`: 50 trials, 336 planned outcomes, 645 nodes, and 1,494
relationships across six labels and seven types.

## Offline verification (no credentials or network)

From the project root using the existing GraphRAG environment:

```bash
.venv-graphrag/bin/python -B cohort_scaling/import_pilot.py
.venv-graphrag/bin/python -B -m unittest discover -s cohort_scaling/tests -v
```

The dry run validates hashes, frozen membership, exact pilot CSV headers,
identifier/property conversion, provenance, relationships and the complete
parameterized import payload. It prints counts and a deterministic payload hash.
It neither loads an environment file nor creates a Neo4j driver. No ZIP reread,
archive download, embeddings, or inference is needed.

The baseline importer is referenced only for specifications, property conversion,
parameterized MERGE query construction, constraints and batching. Its fixed
26/65 validation and baseline credential loader are never called.

## Future separately authorized execution

Live execution has **not been performed**. First provision/identify an empty,
separate Neo4j instance, confirm its actual database name, and obtain approval.
No database is provisioned by this importer. Reuse the existing official Neo4j
driver and python-dotenv dependencies in `.venv-graphrag`.

Copy `.env.example` to the ignored `.env.pilot`, replacing placeholders privately.
Only `PILOT_NEO4J_URI`, `PILOT_NEO4J_USERNAME`, `PILOT_NEO4J_PASSWORD` and
`PILOT_NEO4J_DATABASE` are used; ordinary `NEO4J_*` variables and baseline `.env`
files are never fallbacks. Process variables override an explicitly supplied
pilot environment file. Do not commit credentials.

After separate human authorization, the command format is:

```bash
.venv-graphrag/bin/python -B cohort_scaling/import_pilot.py \
  --execute --env-file cohort_scaling/.env.pilot \
  --confirm-database ACTUAL_PILOT_DATABASE_NAME \
  --confirm-pilot-version HTT-KG-AACT-20260905-PILOT50-v1
```

Both the original database ID `57aa5fa3` and its known endpoint are rejected
before driver creation. URI validation is offline; arbitrary DNS aliases cannot
be proven distinct offline. A separate confirmed endpoint is therefore required.
The live gate checks the actual database name and zero nodes/relationships before
creating constraints. Nonempty targets are refused; nothing is deleted or merged
into an existing graph. MERGE batches run in one data transaction, followed by
exact node/property and relationship comparison. A completed target cannot be
rerun automatically; this deliberate restriction protects existing contents.

## Compatibility boundaries

- Neo4j identifiers and relationship types match the established schema.
- Pilot filenames/headers are explicit, including renamed provenance CSVs.
- Missing values remain empty strings; source values are not backfilled.
- Conditions retain plural `source_record_ids`; no scalar citation is invented.
- Enrollment, study dates, terminal status and prediction labels remain excluded.
- The existing baseline retriever still checks 26/65 and the baseline graph
  version. Its Agentic condition projection expects a scalar source ID. A future
  pilot retrieval adapter must handle the pilot version/counts and plural IDs;
  this importer does not change retrieval behavior.
- Planned outcomes are registered measures, not observed clinical results.
- Snapshot records can include amendments; initial-registration validity is not
  asserted. Connectivity includes provenance links, not necessarily clinical
  paths between every pair of trials.

Any change to pilot data requires a reviewed new version and manifest hash;
the importer will reject unreviewed manifest changes.
