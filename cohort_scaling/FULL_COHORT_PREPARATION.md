# Full frozen-cohort graph preparation

Graph version: `HTT-KG-AACT-20260905-FULL2824-v1`.
Authoritative membership: `HTT-P1-AACT-20260905`, exactly 2,824 unique NCT IDs.

All IDs are included in lexical order without source-availability, label,
planned-outcome, or prediction filtering. The source manifest checksum remains
`5a2d6bbb0973a45988275efb4e9caff8400438edf4e3c560b1b7c0b1688fe7ab`.

The full entry point reuses the unchanged pilot's ZIP scanners, normalization,
stable identifiers, field allowlist, CSV writer and graph schemas. Only the six
required archive members are streamed, and only frozen-cohort rows are retained.
It never extracts the entire ZIP to disk. Safe per-table subsets are cached as
JSONL; memory is bounded by cohort-sized records and graph structures rather
than the complete registry. Observed process peak memory is saved in the manifest.

## Commands

From the project root, initial offline preparation:

```bash
.venv-graphrag/bin/python -B cohort_scaling/prepare_full_cohort.py \
  --archive /Users/lovelaceashong/Downloads/20260905_export_ctgov.zip
```

Existing output directories are refused. Subsequent local validation does not
rescan the archive or regenerate data:

```bash
.venv-graphrag/bin/python -B cohort_scaling/prepare_full_cohort.py --validate-only
.venv-graphrag/bin/python -B -m unittest discover \
  -s cohort_scaling/tests -p 'test_prepare_full_cohort.py' -v
```

## Outputs and safeguards

Outputs live under
`artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1/`:

- Six node CSVs and ten relationship CSVs with Neo4j import identifiers.
- `cohort_membership.csv`: complete frozen membership without outcome labels.
- Six `source_cache/*.jsonl` files containing safe linked source records.
- `source_coverage.csv`: one row per trial/table, including absent records and
  blank-field counts; zero records never remove a trial.
- `COVERAGE_REPORT.md`, `VALIDATION_REPORT.md`, `full_cohort_manifest.json`, and
  `SHA256SUMS`.

The archive's size, MD5, SHA-256, member identities and full-read member CRCs are
verified. Validation checks exact membership, identifiers, endpoints, duplicates,
dataset/graph provenance, all source-record links, planned-outcome values and
coverage, output checksums and preservation of the five-trial and pilot artifacts.
All available registered outcomes are retained, including blank optional fields.
Lead sponsors become graph relationships; collaborators remain in the safe cache.
Submitted conditions and browse terms remain distinct.

Enrollment, study dates, terminal status, termination reasons, prediction labels,
and scores are excluded. Snapshot date and planned measurement time frames remain
as provenance and registered measure descriptions. This September 2026 snapshot
may contain amendments; it is not an initial-registration reconstruction.
Registered planned outcomes are not observed clinical results. The frozen cohort
contains terminal-outcome studies, not every registered HF trial.

No database, index, embedding, or model is involved. Importer modules supply pure
schema/helper definitions only; no driver is instantiated. The existing pilot
importer deliberately rejects this full-cohort version. A separately reviewed
full-cohort import configuration is needed before any future database import.
