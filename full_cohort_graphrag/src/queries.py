"""Allowlisted read-only Cypher; only values and validated page bounds vary."""

DATABASE_INFO = "CALL db.info() YIELD name RETURN name LIMIT 2"
TOTALS = """CALL () { MATCH (n) RETURN count(n) AS node_count }
CALL () { MATCH ()-[r]->() RETURN count(r) AS relationship_count }
RETURN node_count, relationship_count LIMIT 1"""
LABEL_COUNTS = """MATCH (n) UNWIND labels(n) AS label
RETURN label, count(*) AS count ORDER BY label LIMIT 16"""
RELATIONSHIP_COUNTS = """MATCH ()-[r]->() RETURN type(r) AS relationship_type,
count(*) AS count ORDER BY relationship_type LIMIT 16"""

SOURCE_PROJECTION = """dataset { .source_dataset_id, .dataset_version, .graph_version,
.snapshot_date, .snapshot_file, .snapshot_url, .archive_md5, .archive_sha256,
.pinned_manifest_sha256 }"""
SOURCE_DATASET = f"MATCH (dataset:SourceDataset) RETURN {SOURCE_PROJECTION} AS source_dataset LIMIT 2"

# Every property projection is explicit. No properties(n), user Cypher, or
# enrollment/status/date fields can enter evidence through these templates.
TRIALS = f"""UNWIND $nct_ids AS nct_id
MATCH (trial:Trial {{trial_id: nct_id}})
OPTIONAL MATCH (trial)-[membership:MEMBER_OF_DATASET]->(dataset:SourceDataset)
RETURN trial {{ .trial_id, .nct_id, .brief_title, .study_type, .phase,
.source_table, .source_record_id, .source_evidence_status, .dataset_version }} AS trial,
type(membership) AS membership_type,
membership {{ .dataset_version }} AS membership_properties,
{SOURCE_PROJECTION} AS source_dataset
ORDER BY trial.trial_id LIMIT $limit"""

EVIDENCE_COUNTS = """UNWIND $nct_ids AS nct_id
MATCH (trial:Trial {trial_id: nct_id})-[r]->()
WHERE type(r) IN $relationship_types
RETURN trial.trial_id AS nct_id, type(r) AS relationship_type, count(*) AS count
ORDER BY nct_id, relationship_type LIMIT $limit"""

EVIDENCE_PAGE = """UNWIND $nct_ids AS nct_id
MATCH (trial:Trial {trial_id: nct_id})-[r]->(evidence)
WHERE type(r) IN $relationship_types
WITH trial, r, evidence,
CASE type(r)
WHEN 'HAS_SUBMITTED_CONDITION' THEN evidence.condition_id
WHEN 'HAS_BROWSE_CONDITION' THEN evidence.condition_id
WHEN 'HAS_INTERVENTION' THEN evidence.intervention_id
WHEN 'LEAD_SPONSORED_BY' THEN evidence.sponsor_id
WHEN 'HAS_PLANNED_OUTCOME' THEN evidence.planned_outcome_id END AS evidence_id
RETURN trial.trial_id AS nct_id, type(r) AS relationship_type, evidence_id,
labels(evidence) AS evidence_labels,
r { .dataset_version, .source_table, .source_record_id, .source_record_ids } AS relationship_properties,
evidence { .condition_id, .name, .normalized_name, .source_kind,
.intervention_id, .intervention_type, .sponsor_id, .agency_class,
.planned_outcome_id, .nct_id, .outcome_type, .measure, .time_frame,
.population, .description, .evidence_safeguard, .source_record_id,
.source_table, .dataset_version } AS evidence_properties
ORDER BY nct_id, relationship_type, evidence_id
SKIP $offset LIMIT $limit"""

# EXISTS checks avoid multiplying trials by condition/intervention matches.
# Sponsors and outcomes are deliberately not required for matching membership.
SEARCH_MATCH = """MATCH (trial:Trial)
WHERE trial.dataset_version = $dataset_version
AND EXISTS {
 MATCH (trial)-[:HAS_SUBMITTED_CONDITION]->(condition:ConditionTerm)
 WHERE condition.normalized_name = $condition_normalized
 AND condition.source_kind = 'submitted'
 AND condition.dataset_version = $dataset_version
}
AND EXISTS {
 MATCH (trial)-[:HAS_INTERVENTION]->(intervention:Intervention)
 WHERE intervention.normalized_name = $intervention_normalized
 AND intervention.dataset_version = $dataset_version
}"""
SEARCH_COUNT = SEARCH_MATCH + "\nRETURN count(trial) AS total LIMIT 1"
SEARCH_PAGE = SEARCH_MATCH + "\nRETURN trial.trial_id AS nct_id ORDER BY nct_id SKIP $offset LIMIT $limit"

READ_ONLY_QUERIES = (
    DATABASE_INFO, TOTALS, LABEL_COUNTS, RELATIONSHIP_COUNTS, SOURCE_DATASET,
    TRIALS, EVIDENCE_COUNTS, EVIDENCE_PAGE, SEARCH_COUNT, SEARCH_PAGE,
)
