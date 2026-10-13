# HeartTrialTwin Neo4j import validation

- Graph version: `HTT-KG-AACT-20260905-v1`
- Authoritative dataset: `HTT-P1-AACT-20260905`
- Pinned cohort membership: 2,824 trials
- Exact AACT snapshot: `20260905_export_ctgov.zip` (2026-09-05)
- Archive ETag: `99e62b3f8ae5838b36bc0c2277ad2714`
- Transport metadata source: `pinned_audit_and_verified_preflight`
- Bounded range bytes transferred: 446,076,940
- Range requests: 14
- Prediction nodes: omitted because this graph preparation does not create a new durable prediction-to-trial/model/input-data binding.

## Deterministic outcome-blind selection

The script retained pinned trials with at least one submitted condition, one named intervention, one named lead sponsor, and two planned outcomes. It ranked shared pairs by descending support, then normalized condition, intervention type, and intervention name. The primary rule required an HF-specific submitted condition and excluded only exact generic control names. The first five NCT IDs in lexical order from the highest-ranked pair were selected. Status, discontinuation labels, predictions, and model performance were not used.

- Selection mode: HF-specific submitted condition plus non-generic intervention
- Shared submitted condition: `Heart Failure`
- Shared intervention: `DRUG — Spironolactone`
- Pair support before selecting five: 11 trials
- Selected NCT IDs: NCT00206232, NCT00391846, NCT00574119, NCT00604006, NCT01130597

## Node counts

- Trial: 5
- ConditionTerm: 4
- Intervention: 1
- Sponsor: 5
- PlannedOutcome: 10
- SourceDataset: 1
- Total: 26

## Relationship counts

- HAS_BROWSE_CONDITION: 15
- HAS_INTERVENTION: 5
- HAS_PLANNED_OUTCOME: 10
- HAS_SUBMITTED_CONDITION: 5
- LEAD_SPONSORED_BY: 5
- MEMBER_OF_DATASET: 5
- SOURCED_FROM: 20
- Total: 65
- Distinct relationship types: 7

## Validation checks

- PASS — all trial ids in pinned cohort
- PASS — archive identity matches pinned audit
- PASS — every relationship endpoint exists
- PASS — exactly five outcome blind trials selected
- PASS — graph is connected
- PASS — no prediction evidence review or graphrag nodes
- PASS — node count within 20 to 40
- PASS — node identifiers unique within type
- PASS — relationship triples unique
- PASS — relationship type count within 5 to 12
- PASS — shared intervention path exists
- PASS — shared submitted condition path exists
- PASS — source members fully read and crc checked

## Limitations

- The 2.5 GB archive was not downloaded as one file, so a whole-archive SHA-256 was not computed. Provenance is bound to the audited URL, byte size, ETag, Last-Modified value, and member CRCs.
- Submitted-condition and browse-condition source row IDs were not retained in the Step-2 aggregate used here. Their relationships are exact term-to-trial matches from that verified extract, and the missing raw row-ID provenance is explicit in each CSV.
- PlannedOutcome nodes describe registry-planned measures. They are not trial results and are not terminal status evidence.
- This small graph is intentionally selected for shared-path demonstration; it is not a statistically representative sample of all 2,824 trials.
- No Prediction, Evidence, HumanReview, or GraphRAG nodes are included.

## Neo4j readiness

All node IDs are unique within their import groups, every relationship endpoint exists, all Trial nodes belong to the pinned cohort, the graph is connected, and shared submitted-condition and intervention traversal paths were verified. The CSVs are ready for a bounded Neo4j import after human approval.
