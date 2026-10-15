"""Fixed, parameterized Cypher retrieval queries for HeartTrialTwin GraphRAG.

These queries are intentionally read-only. They retrieve evidence from the
verified six-label, seven-relationship HeartTrialTwin Neo4j graph and never
generate Cypher from user text.
"""

DATABASE_INFO_QUERY = "CALL db.info() YIELD name RETURN name"

GRAPH_TOTALS_QUERY = """
CALL () { MATCH (n) RETURN count(n) AS node_count }
CALL () { MATCH ()-[r]->() RETURN count(r) AS relationship_count }
RETURN node_count, relationship_count
""".strip()

SOURCE_DATASET_QUERY = """
MATCH (dataset:SourceDataset {source_dataset_id: $dataset_version})
RETURN properties(dataset) AS source_dataset
""".strip()

# Question 1: one exact trial plus every supported outgoing evidence path.
BASIC_TRIAL_QUERY = """
MATCH (trial:Trial {nct_id: $nct_id})
OPTIONAL MATCH (trial)-[relationship]->(evidence)
WHERE type(relationship) IN $relationship_types
WITH trial, relationship, evidence
ORDER BY type(relationship),
         coalesce(evidence.source_record_id,
                  evidence.name,
                  evidence.source_dataset_id,
                  evidence.nct_id)
WITH trial,
     collect({
       relationship_type: type(relationship),
       relationship_properties: properties(relationship),
       evidence_labels: labels(evidence),
       evidence_properties: properties(evidence)
     }) AS evidence_paths
RETURN properties(trial) AS trial, evidence_paths
""".strip()

# Question 2: Trial -> submitted HF condition, intervention, sponsor, planned
# outcome, and source dataset. Every relationship in the multi-hop evidence path
# is returned with its stored provenance properties.
SPONSOR_OUTCOME_QUERY = """
MATCH (trial:Trial)-[condition_relationship:HAS_SUBMITTED_CONDITION]->
      (condition:ConditionTerm {normalized_name: $condition_normalized})
MATCH (trial)-[intervention_relationship:HAS_INTERVENTION]->
      (intervention:Intervention {normalized_name: $intervention_normalized})
MATCH (trial)-[sponsor_relationship:LEAD_SPONSORED_BY]->(sponsor:Sponsor)
MATCH (trial)-[outcome_relationship:HAS_PLANNED_OUTCOME]->
      (outcome:PlannedOutcome)
MATCH (trial)-[dataset_relationship:MEMBER_OF_DATASET]->
      (dataset:SourceDataset {source_dataset_id: $dataset_version})
RETURN trial.nct_id AS nct_id,
       trial.brief_title AS brief_title,
       properties(condition) AS condition,
       properties(intervention) AS intervention,
       properties(sponsor) AS sponsor,
       properties(outcome) AS planned_outcome,
       properties(dataset) AS source_dataset,
       {
         condition: {type: type(condition_relationship),
                     properties: properties(condition_relationship)},
         intervention: {type: type(intervention_relationship),
                        properties: properties(intervention_relationship)},
         sponsor: {type: type(sponsor_relationship),
                   properties: properties(sponsor_relationship)},
         planned_outcome: {type: type(outcome_relationship),
                           properties: properties(outcome_relationship)},
         dataset: {type: type(dataset_relationship),
                   properties: properties(dataset_relationship)}
       } AS relationship_path
ORDER BY nct_id, toInteger(outcome.source_record_id)
""".strip()

# Question 3: retrieve every registered planned outcome across all five trials
# in this versioned illustrative graph. Similarities/differences are computed
# deterministically in Python from these exact records.
OUTCOME_COMPARISON_QUERY = """
MATCH (trial:Trial)-[outcome_relationship:HAS_PLANNED_OUTCOME]->
      (outcome:PlannedOutcome)
MATCH (trial)-[dataset_relationship:MEMBER_OF_DATASET]->
      (dataset:SourceDataset {source_dataset_id: $dataset_version})
WHERE trial.dataset_version = $dataset_version
RETURN trial.nct_id AS nct_id,
       trial.brief_title AS brief_title,
       properties(outcome) AS planned_outcome,
       properties(dataset) AS source_dataset,
       {
         planned_outcome: {type: type(outcome_relationship),
                           properties: properties(outcome_relationship)},
         dataset: {type: type(dataset_relationship),
                   properties: properties(dataset_relationship)}
       } AS relationship_path
ORDER BY nct_id, toInteger(outcome.source_record_id)
""".strip()


READ_ONLY_QUERIES = (
    DATABASE_INFO_QUERY,
    GRAPH_TOTALS_QUERY,
    SOURCE_DATASET_QUERY,
    BASIC_TRIAL_QUERY,
    SPONSOR_OUTCOME_QUERY,
    OUTCOME_COMPARISON_QUERY,
)
