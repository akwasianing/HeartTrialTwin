# Full-cohort GraphSAGE extraction — Step 66B

Version: `HTT-GNN-FULL2824-EXTRACT-v1`.
Source graph: `HTT-KG-AACT-20260905-FULL2824-v1`.
Dataset: `HTT-P1-AACT-20260905`; snapshot: September 5, 2026.

This is an **offline pre-split graph export, not a leakage-safe training graph**.
No model, encoder, database, credentials, network, or new dependency is used.
The five-trial implementation and its existing data/results remain unchanged.

## Run

From the project root, using the existing environment:

```bash
.venv-vector-rag/bin/python -B gnn_graphrag/src/extract_full_cohort.py
.venv-vector-rag/bin/python -B -m unittest discover \
  -s gnn_graphrag/tests -p 'test_extract_full_cohort.py' -v
```

To run the original 21 tests without the new extraction tests:

```bash
.venv-vector-rag/bin/python -B -m unittest discover \
  -s gnn_graphrag/tests -p 'test_extract_graph.py' -v
.venv-vector-rag/bin/python -B -m unittest discover \
  -s gnn_graphrag/tests -p 'test_graphsage_demo.py' -v
.venv-vector-rag/bin/python -B -m unittest discover \
  -s gnn_graphrag/tests -p 'test_trial_ranking_demo.py' -v
```

The adapter requires manifest SHA-256
`3ef82624d131b36abc1eb9ad4e89b3439fed9f9600b92262c21bbcbfe6cf8757`,
verifies all 26 manifest-listed source-file hashes and the original frozen
membership-manifest hash, and validates exact CSV schemas and graph associations.
It reads existing local exports, not the ZIP archive or live registry.

## Output

Default destination: `gnn_graphrag/data/HTT-GNN-FULL2824-EXTRACT-v1/`.
An existing destination is refused. For a separate reproducibility check, use
`--output-dir` with a new directory; never overwrite an existing version.

- `nodes.csv`: all 28,777 nodes with deterministic zero-based indices, stable
  IDs, label, source file, dataset/graph/snapshot metadata, original properties
  (including blanks), missing-feature fields, approved feature text and its hash.
- `relationships.csv`: all 79,125 original directed relationships and exact
  source properties, including source-record identifiers and provenance links.
- `message_edges_semantic.csv`: 50,349 forward and 50,349 computational reverse
  edges (100,698 total), each linked to its original relationship index.
- `extraction_manifest.json`: source/output/code hashes, schemas' version,
  ordering, counts, feature policy, missingness and explicit training warnings.
- `SHA256SUMS`: hashes of the three CSVs and extraction manifest. The manifest
  does not recursively hash itself; `SHA256SUMS` supplies its external hash.

Indices sort by Trial, ConditionTerm, Intervention, Sponsor, PlannedOutcome,
SourceDataset, then lexical stable identifier within each label. Relationships
sort by declared type order, source/target indices, filename and canonical
properties. Forward/reverse message pairs follow original relationship order.
Typed computational duplicates are rejected. Missing evidence never removes
a trial. Output rows and checksum reads are streamed; cohort-sized graph
records are held in memory, not an archive-sized dataset or embedding matrix.

## Feature and provenance policy

The original prototype's approved text formatter is reused without modification.
Trial text includes title, study type and phase, **not NCT ID**. Other feature
fields remain condition name/source classification, intervention name/type,
sponsor name/agency class, planned outcome type/measure/time frame, and dataset
version/graph version/snapshot date. NCT tokens appearing inside any approved
text field are redacted from feature text only. Exact original values remain
in `properties_json` and stable linkage metadata.

There is no imputation. Blank source values remain empty strings in metadata;
blank feature values are omitted and recorded explicitly. Submitted conditions
and browse terms remain distinct. Termination status/reasons, observed results,
enrollment, completion dates, prediction labels/scores and other prohibited
fields are not features. Planned outcomes are registered measures, not observed
clinical results. September 2026 values may include amendments and are not
claimed to represent original-registration values.

`MEMBER_OF_DATASET` and `SOURCED_FROM` remain in original relationships but
are excluded from computational message passing. The SourceDataset node is
retained and isolated in the semantic computational graph.

## Training boundary

All source target associations are still present. Future development must
define study-family-aware train/validation/test partitions and remove withheld
target associations **and their computational reverses** before computing any
embeddings or message passing. Avoid target leakage through feature text or
precomputed full-graph embeddings. Do not pass this export directly into an
evaluation and describe it as held out. No split, embedding, training objective,
message-passing run or GraphRAG integration is implemented in Step 66B.

Checksum verification establishes fidelity to the pinned local export; it does
not revalidate clinical truth or inspect the live Neo4j database. A write error
can leave an incomplete new destination; it is never silently reused, repaired
or deleted. Investigate that directory and choose a new destination explicitly.
