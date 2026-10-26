# HTT-KG-AACT-20260905-FULL2824-v1 local validation

Dataset: HTT-P1-AACT-20260905; snapshot: 2026-09-05. All frozen IDs included in lexical order.

## Node counts

- Trial: 2824
- ConditionTerm: 1743
- Intervention: 3417
- Sponsor: 1052
- PlannedOutcome: 19740
- SourceDataset: 1
- Total: 28777

## Relationship counts

- HAS_BROWSE_CONDITION: 17587
- HAS_INTERVENTION: 4716
- HAS_PLANNED_OUTCOME: 19740
- HAS_SUBMITTED_CONDITION: 5482
- LEAD_SPONSORED_BY: 2824
- MEMBER_OF_DATASET: 2824
- SOURCED_FROM: 25952
- Total: 79125

## Checks

- PASS — exact_2824_unique_frozen_membership
- PASS — unique_node_ids
- PASS — unique_relationship_triples
- PASS — valid_endpoints_and_versions
- PASS — connected_via_provenance
- PASS — all_available_source_records_linked
- PASS — all_outcomes_preserved_without_cap
- PASS — outcome_values_and_source_ids_exact
- PASS — missing_evidence_and_fields_verified
- PASS — prohibited_fields_excluded
- PASS — archive size, MD5, SHA-256 and all six fully streamed ZIP member CRCs.
- PASS — five-trial and 50-trial protected artifacts unchanged.

## Limitations

- The frozen 2,824-trial membership is restricted to observed terminal outcomes; this is not all registered HF trials.
- Snapshot values may contain later amendments and are not asserted to be initial-registration predictors.
- Registered planned outcomes are planned measures, not observed clinical results.
- Missing fields stay blank; absent rows mean no record found in this pinned table, not proof no evidence ever existed.
- Only lead sponsors become graph relationships; collaborator rows remain in the safe source cache.
- Conservative normalization merges equivalent names/types; exact per-row values remain cached with original source IDs.
- Connectivity is through provenance links and does not assert clinical similarity among all trials.
- The five-trial and 50-trial importers/retrievers remain unchanged and cannot ingest this version without separate configuration.
