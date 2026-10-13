#!/usr/bin/env python3
"""Safely import the verified HeartTrialTwin graph into Neo4j.

This script is inert unless ``--execute`` is supplied. Its default behavior is
to validate the local graph manifest, checksums, CSV headers, identifiers, and
relationship endpoints without connecting to Neo4j.

Required environment variables for execution:
    NEO4J_URI
    NEO4J_USERNAME
    NEO4J_PASSWORD
    NEO4J_DATABASE

The same values may be stored in ``artifacts/knowledge_graph/.env``. Process
environment variables take precedence over the local file. The repository's
.gitignore excludes .env files while retaining .env.example.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ARTIFACT_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = ARTIFACT_DIR / "graph_import_manifest.json"
DOTENV_PATH = ARTIFACT_DIR / ".env"

EXPECTED_GRAPH_VERSION = "HTT-KG-AACT-20260905-v1"
EXPECTED_DATASET_VERSION = "HTT-P1-AACT-20260905"
EXPECTED_NODE_TOTAL = 26
EXPECTED_RELATIONSHIP_TOTAL = 65
EXPECTED_LABEL_COUNT = 6
EXPECTED_RELATIONSHIP_TYPE_COUNT = 7
BATCH_SIZE = 100


@dataclass(frozen=True)
class NodeSpec:
    filename: str
    label: str
    id_header: str
    id_property: str
    header: tuple[str, ...]


@dataclass(frozen=True)
class RelationshipSpec:
    filename: str
    start_label: str
    start_id_property: str
    start_header: str
    relationship_type: str
    end_label: str
    end_id_property: str
    end_header: str
    header: tuple[str, ...]


NODE_SPECS = (
    NodeSpec(
        "nodes_trial.csv",
        "Trial",
        "trial_id:ID(Trial)",
        "trial_id",
        (
            "trial_id:ID(Trial)",
            "nct_id",
            "brief_title",
            "study_type",
            "phase",
            "enrollment",
            "start_date",
            "completion_date",
            "study_first_submitted_date",
            "submission_year:int",
            "temporal_group",
            "dataset_version",
            ":LABEL",
        ),
    ),
    NodeSpec(
        "nodes_condition_term.csv",
        "ConditionTerm",
        "condition_id:ID(ConditionTerm)",
        "condition_id",
        (
            "condition_id:ID(ConditionTerm)",
            "name",
            "normalized_name",
            "source_kind",
            "source_table",
            "dataset_version",
            ":LABEL",
        ),
    ),
    NodeSpec(
        "nodes_intervention.csv",
        "Intervention",
        "intervention_id:ID(Intervention)",
        "intervention_id",
        (
            "intervention_id:ID(Intervention)",
            "name",
            "normalized_name",
            "intervention_type",
            "normalized_intervention_type",
            "source_table",
            "dataset_version",
            ":LABEL",
        ),
    ),
    NodeSpec(
        "nodes_sponsor.csv",
        "Sponsor",
        "sponsor_id:ID(Sponsor)",
        "sponsor_id",
        (
            "sponsor_id:ID(Sponsor)",
            "name",
            "normalized_name",
            "agency_class",
            "source_table",
            "dataset_version",
            ":LABEL",
        ),
    ),
    NodeSpec(
        "nodes_planned_outcome.csv",
        "PlannedOutcome",
        "planned_outcome_id:ID(PlannedOutcome)",
        "planned_outcome_id",
        (
            "planned_outcome_id:ID(PlannedOutcome)",
            "source_record_id",
            "nct_id",
            "outcome_type",
            "measure",
            "time_frame",
            "population",
            "description",
            "source_table",
            "dataset_version",
            ":LABEL",
        ),
    ),
    NodeSpec(
        "nodes_source_dataset.csv",
        "SourceDataset",
        "source_dataset_id:ID(SourceDataset)",
        "source_dataset_id",
        (
            "source_dataset_id:ID(SourceDataset)",
            "dataset_version",
            "graph_version",
            "snapshot_date",
            "snapshot_file",
            "snapshot_url",
            "archive_size_bytes:long",
            "archive_etag",
            "archive_last_modified",
            "pinned_manifest_sha256",
            ":LABEL",
        ),
    ),
)


RELATIONSHIP_SPECS = (
    RelationshipSpec(
        "relationships_trial_submitted_condition.csv",
        "Trial",
        "trial_id",
        ":START_ID(Trial)",
        "HAS_SUBMITTED_CONDITION",
        "ConditionTerm",
        "condition_id",
        ":END_ID(ConditionTerm)",
        (
            ":START_ID(Trial)",
            ":END_ID(ConditionTerm)",
            "source_table",
            "source_record_id",
            "source_record_id_status",
            "dataset_version",
            ":TYPE",
        ),
    ),
    RelationshipSpec(
        "relationships_trial_browse_condition.csv",
        "Trial",
        "trial_id",
        ":START_ID(Trial)",
        "HAS_BROWSE_CONDITION",
        "ConditionTerm",
        "condition_id",
        ":END_ID(ConditionTerm)",
        (
            ":START_ID(Trial)",
            ":END_ID(ConditionTerm)",
            "source_table",
            "source_record_id",
            "source_record_id_status",
            "dataset_version",
            ":TYPE",
        ),
    ),
    RelationshipSpec(
        "relationships_trial_intervention.csv",
        "Trial",
        "trial_id",
        ":START_ID(Trial)",
        "HAS_INTERVENTION",
        "Intervention",
        "intervention_id",
        ":END_ID(Intervention)",
        (
            ":START_ID(Trial)",
            ":END_ID(Intervention)",
            "source_table",
            "source_record_ids",
            "dataset_version",
            ":TYPE",
        ),
    ),
    RelationshipSpec(
        "relationships_trial_sponsor.csv",
        "Trial",
        "trial_id",
        ":START_ID(Trial)",
        "LEAD_SPONSORED_BY",
        "Sponsor",
        "sponsor_id",
        ":END_ID(Sponsor)",
        (
            ":START_ID(Trial)",
            ":END_ID(Sponsor)",
            "source_table",
            "source_record_ids",
            "dataset_version",
            ":TYPE",
        ),
    ),
    RelationshipSpec(
        "relationships_trial_planned_outcome.csv",
        "Trial",
        "trial_id",
        ":START_ID(Trial)",
        "HAS_PLANNED_OUTCOME",
        "PlannedOutcome",
        "planned_outcome_id",
        ":END_ID(PlannedOutcome)",
        (
            ":START_ID(Trial)",
            ":END_ID(PlannedOutcome)",
            "source_table",
            "source_record_id",
            "dataset_version",
            ":TYPE",
        ),
    ),
    RelationshipSpec(
        "relationships_trial_source_dataset.csv",
        "Trial",
        "trial_id",
        ":START_ID(Trial)",
        "MEMBER_OF_DATASET",
        "SourceDataset",
        "source_dataset_id",
        ":END_ID(SourceDataset)",
        (
            ":START_ID(Trial)",
            ":END_ID(SourceDataset)",
            "dataset_version",
            ":TYPE",
        ),
    ),
    RelationshipSpec(
        "relationships_condition_source_dataset.csv",
        "ConditionTerm",
        "condition_id",
        ":START_ID(ConditionTerm)",
        "SOURCED_FROM",
        "SourceDataset",
        "source_dataset_id",
        ":END_ID(SourceDataset)",
        (
            ":START_ID(ConditionTerm)",
            ":END_ID(SourceDataset)",
            "dataset_version",
            ":TYPE",
        ),
    ),
    RelationshipSpec(
        "relationships_intervention_source_dataset.csv",
        "Intervention",
        "intervention_id",
        ":START_ID(Intervention)",
        "SOURCED_FROM",
        "SourceDataset",
        "source_dataset_id",
        ":END_ID(SourceDataset)",
        (
            ":START_ID(Intervention)",
            ":END_ID(SourceDataset)",
            "dataset_version",
            ":TYPE",
        ),
    ),
    RelationshipSpec(
        "relationships_sponsor_source_dataset.csv",
        "Sponsor",
        "sponsor_id",
        ":START_ID(Sponsor)",
        "SOURCED_FROM",
        "SourceDataset",
        "source_dataset_id",
        ":END_ID(SourceDataset)",
        (
            ":START_ID(Sponsor)",
            ":END_ID(SourceDataset)",
            "dataset_version",
            ":TYPE",
        ),
    ),
    RelationshipSpec(
        "relationships_outcome_source_dataset.csv",
        "PlannedOutcome",
        "planned_outcome_id",
        ":START_ID(PlannedOutcome)",
        "SOURCED_FROM",
        "SourceDataset",
        "source_dataset_id",
        ":END_ID(SourceDataset)",
        (
            ":START_ID(PlannedOutcome)",
            ":END_ID(SourceDataset)",
            "dataset_version",
            ":TYPE",
        ),
    ),
)


CONSTRAINT_QUERIES = (
    "CREATE CONSTRAINT htt_trial_id_unique IF NOT EXISTS "
    "FOR (n:Trial) REQUIRE n.trial_id IS UNIQUE",
    "CREATE CONSTRAINT htt_condition_id_unique IF NOT EXISTS "
    "FOR (n:ConditionTerm) REQUIRE n.condition_id IS UNIQUE",
    "CREATE CONSTRAINT htt_intervention_id_unique IF NOT EXISTS "
    "FOR (n:Intervention) REQUIRE n.intervention_id IS UNIQUE",
    "CREATE CONSTRAINT htt_sponsor_id_unique IF NOT EXISTS "
    "FOR (n:Sponsor) REQUIRE n.sponsor_id IS UNIQUE",
    "CREATE CONSTRAINT htt_planned_outcome_id_unique IF NOT EXISTS "
    "FOR (n:PlannedOutcome) REQUIRE n.planned_outcome_id IS UNIQUE",
    "CREATE CONSTRAINT htt_source_dataset_id_unique IF NOT EXISTS "
    "FOR (n:SourceDataset) REQUIRE n.source_dataset_id IS UNIQUE",
)

DATABASE_IDENTITY_QUERY = (
    "SHOW DATABASES YIELD name, currentStatus "
    "WHERE name = $target_database RETURN name, currentStatus"
)
TOTALS_QUERY = (
    "CALL { MATCH (n) RETURN count(n) AS node_count } "
    "CALL { MATCH ()-[r]->() RETURN count(r) AS relationship_count } "
    "RETURN node_count, relationship_count"
)
LABEL_COUNTS_QUERY = (
    "MATCH (n) UNWIND labels(n) AS label "
    "RETURN label, count(*) AS count ORDER BY label"
)
RELATIONSHIP_COUNTS_QUERY = (
    "MATCH ()-[r]->() RETURN type(r) AS relationship_type, "
    "count(*) AS count ORDER BY relationship_type"
)
DATASET_MEMBERSHIP_QUERY = (
    "MATCH (n) RETURN count(n) AS total, "
    "sum(CASE WHEN n.dataset_version = $dataset_version THEN 1 ELSE 0 END) "
    "AS matching_dataset"
)
CONNECTIVITY_NODES_QUERY = "MATCH (n) RETURN elementId(n) AS node_id"
CONNECTIVITY_EDGES_QUERY = (
    "MATCH (a)-[r]->(b) RETURN elementId(a) AS start_id, "
    "elementId(b) AS end_id"
)
SOURCE_PROVENANCE_QUERY = (
    "MATCH (s:SourceDataset {source_dataset_id: $source_dataset_id}) "
    "RETURN properties(s) AS properties"
)


@dataclass
class PreparedGraph:
    manifest: dict[str, Any]
    node_rows: dict[str, list[dict[str, Any]]]
    relationship_rows: dict[str, list[dict[str, Any]]]


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str
    username: str
    password: str
    database: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path, expected_header: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        actual_header = tuple(reader.fieldnames or ())
        if actual_header != expected_header:
            raise RuntimeError(
                f"Header mismatch in {path.name}: {actual_header} != {expected_header}"
            )
        rows = [dict(row) for row in reader]
    if not rows:
        raise RuntimeError(f"Import file is empty: {path.name}")
    return rows


def typed_property(header: str, value: str) -> tuple[str, Any]:
    if header.endswith(":int"):
        return header.removesuffix(":int"), int(value)
    if header.endswith(":long"):
        return header.removesuffix(":long"), int(value)
    return header, value


def node_payload(spec: NodeSpec, row: dict[str, str]) -> dict[str, Any]:
    properties: dict[str, Any] = {spec.id_property: row[spec.id_header]}
    for header, value in row.items():
        if header in {spec.id_header, ":LABEL"}:
            continue
        key, typed_value = typed_property(header, value)
        properties[key] = typed_value
    return {"id": row[spec.id_header], "properties": properties}


def relationship_payload(
    spec: RelationshipSpec, row: dict[str, str]
) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for header, value in row.items():
        if header in {spec.start_header, spec.end_header, ":TYPE"}:
            continue
        key, typed_value = typed_property(header, value)
        properties[key] = typed_value
    return {
        "start_id": row[spec.start_header],
        "end_id": row[spec.end_header],
        "properties": properties,
    }


def chunks(rows: list[dict[str, Any]]) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(rows), BATCH_SIZE):
        yield rows[start : start + BATCH_SIZE]


def load_and_validate_local_graph() -> PreparedGraph:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("graph_version") != EXPECTED_GRAPH_VERSION:
        raise RuntimeError("Unexpected graph version in graph_import_manifest.json")
    if manifest.get("authoritative_dataset_version") != EXPECTED_DATASET_VERSION:
        raise RuntimeError("Unexpected dataset version in graph_import_manifest.json")
    if manifest.get("total_nodes") != EXPECTED_NODE_TOTAL:
        raise RuntimeError("Manifest node total is not 26")
    if manifest.get("total_relationships") != EXPECTED_RELATIONSHIP_TOTAL:
        raise RuntimeError("Manifest relationship total is not 65")

    file_hashes = manifest.get("files_sha256", {})
    node_rows: dict[str, list[dict[str, Any]]] = {}
    relationship_rows: dict[str, list[dict[str, Any]]] = {}
    node_ids: dict[str, set[str]] = {}

    for spec in NODE_SPECS:
        path = ARTIFACT_DIR / spec.filename
        expected_hash = file_hashes.get(spec.filename)
        if not expected_hash or sha256_file(path) != expected_hash:
            raise RuntimeError(f"Checksum mismatch: {spec.filename}")
        raw_rows = read_csv(path, spec.header)
        if any(row[":LABEL"] != spec.label for row in raw_rows):
            raise RuntimeError(f"Unexpected label value in {spec.filename}")
        ids = [row[spec.id_header] for row in raw_rows]
        if any(not value for value in ids) or len(ids) != len(set(ids)):
            raise RuntimeError(f"Missing or duplicate node ID in {spec.filename}")
        expected_count = manifest["node_counts"][spec.label]
        if len(raw_rows) != expected_count:
            raise RuntimeError(f"Row-count mismatch in {spec.filename}")
        node_ids[spec.label] = set(ids)
        node_rows[spec.filename] = [node_payload(spec, row) for row in raw_rows]

    relationship_type_counts: Counter[str] = Counter()
    relationship_total = 0
    relationship_keys: set[tuple[str, str, str]] = set()
    for spec in RELATIONSHIP_SPECS:
        path = ARTIFACT_DIR / spec.filename
        expected_hash = file_hashes.get(spec.filename)
        if not expected_hash or sha256_file(path) != expected_hash:
            raise RuntimeError(f"Checksum mismatch: {spec.filename}")
        raw_rows = read_csv(path, spec.header)
        if any(row[":TYPE"] != spec.relationship_type for row in raw_rows):
            raise RuntimeError(f"Unexpected relationship type in {spec.filename}")
        prepared_rows: list[dict[str, Any]] = []
        for row in raw_rows:
            start_id = row[spec.start_header]
            end_id = row[spec.end_header]
            if start_id not in node_ids[spec.start_label]:
                raise RuntimeError(f"Missing start node for {spec.filename}: {start_id}")
            if end_id not in node_ids[spec.end_label]:
                raise RuntimeError(f"Missing end node for {spec.filename}: {end_id}")
            key = (start_id, spec.relationship_type, end_id)
            if key in relationship_keys:
                raise RuntimeError(f"Duplicate relationship triple: {key}")
            relationship_keys.add(key)
            prepared_rows.append(relationship_payload(spec, row))
        relationship_rows[spec.filename] = prepared_rows
        relationship_type_counts[spec.relationship_type] += len(prepared_rows)
        relationship_total += len(prepared_rows)

    actual_node_total = sum(len(rows) for rows in node_rows.values())
    if actual_node_total != EXPECTED_NODE_TOTAL:
        raise RuntimeError(f"Expected 26 local nodes; found {actual_node_total}")
    if relationship_total != EXPECTED_RELATIONSHIP_TOTAL:
        raise RuntimeError(f"Expected 65 local relationships; found {relationship_total}")
    if dict(relationship_type_counts) != manifest["relationship_counts"]:
        raise RuntimeError("Relationship counts do not match the manifest")
    if len(node_ids) != EXPECTED_LABEL_COUNT:
        raise RuntimeError("Expected six node labels")
    if len(relationship_type_counts) != EXPECTED_RELATIONSHIP_TYPE_COUNT:
        raise RuntimeError("Expected seven relationship types")

    adjacency: dict[str, set[str]] = defaultdict(set)
    all_ids = set().union(*node_ids.values())
    for spec in RELATIONSHIP_SPECS:
        for row in relationship_rows[spec.filename]:
            adjacency[row["start_id"]].add(row["end_id"])
            adjacency[row["end_id"]].add(row["start_id"])
    source_id = node_rows["nodes_source_dataset.csv"][0]["id"]
    reached: set[str] = set()
    queue: deque[str] = deque([source_id])
    while queue:
        current = queue.popleft()
        if current in reached:
            continue
        reached.add(current)
        queue.extend(adjacency[current] - reached)
    if reached != all_ids:
        raise RuntimeError("Prepared local graph is not fully connected")

    return PreparedGraph(manifest, node_rows, relationship_rows)


def load_config() -> Neo4jConfig:
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise RuntimeError(
            "python-dotenv is required for execution. Install requirements-neo4j.txt."
        ) from exc
    load_dotenv(DOTENV_PATH, override=False)
    values = {
        "uri": os.environ.get("NEO4J_URI", "").strip(),
        "username": os.environ.get("NEO4J_USERNAME", "").strip(),
        "password": os.environ.get("NEO4J_PASSWORD", ""),
        "database": os.environ.get("NEO4J_DATABASE", "").strip(),
    }
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise RuntimeError(
            "Missing required Neo4j configuration: " + ", ".join(missing)
        )
    allowed_schemes = ("neo4j://", "neo4j+s://", "bolt://", "bolt+s://")
    if not values["uri"].startswith(allowed_schemes):
        raise RuntimeError("NEO4J_URI must use a supported Neo4j/Bolt URI scheme")
    return Neo4jConfig(**values)


def configure_password() -> None:
    """Prompt without echo and store only the local ignored password value."""
    from getpass import getpass

    if not DOTENV_PATH.exists():
        raise RuntimeError(
            f"Local configuration is missing: {DOTENV_PATH}. Copy .env.example first."
        )
    lines = DOTENV_PATH.read_text(encoding="utf-8").splitlines()
    password = getpass("Neo4j password (input hidden): ")
    if not password:
        raise RuntimeError("Password was empty; local configuration was not changed")

    output: list[str] = []
    replaced = False
    encoded_password = json.dumps(password)
    for line in lines:
        if line.startswith("NEO4J_PASSWORD="):
            output.append(f"NEO4J_PASSWORD={encoded_password}")
            replaced = True
        else:
            output.append(line)
    if not replaced:
        output.append(f"NEO4J_PASSWORD={encoded_password}")

    fd, temporary_name = tempfile.mkstemp(
        prefix=".env.", suffix=".tmp", dir=DOTENV_PATH.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("\n".join(output) + "\n")
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, DOTENV_PATH)
        os.chmod(DOTENV_PATH, 0o600)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    print(
        "Password stored in the local ignored .env file with mode 0600. "
        "No Neo4j connection was opened."
    )


def execute_query(driver: Any, database: str, query: str, **parameters: Any) -> list[dict[str, Any]]:
    records, _, _ = driver.execute_query(
        query,
        parameters_=parameters,
        database_=database,
    )
    return [dict(record) for record in records]


def verify_database_identity(driver: Any, config: Neo4jConfig) -> None:
    rows = execute_query(
        driver,
        "system",
        DATABASE_IDENTITY_QUERY,
        target_database=config.database,
    )
    if len(rows) != 1 or rows[0]["name"] != config.database:
        raise RuntimeError(
            f"Target database {config.database!r} was not found exactly. Import aborted."
        )
    if str(rows[0]["currentStatus"]).lower() != "online":
        raise RuntimeError(
            f"Target database {config.database!r} is not online. Import aborted."
        )


def node_merge_query(spec: NodeSpec) -> str:
    return (
        f"UNWIND $rows AS row "
        f"MERGE (n:{spec.label} {{{spec.id_property}: row.id}}) "
        "SET n = row.properties "
        "RETURN count(n) AS imported"
    )


def relationship_merge_query(spec: RelationshipSpec) -> str:
    return (
        f"UNWIND $rows AS row "
        f"MATCH (a:{spec.start_label} {{{spec.start_id_property}: row.start_id}}) "
        f"MATCH (b:{spec.end_label} {{{spec.end_id_property}: row.end_id}}) "
        f"MERGE (a)-[r:{spec.relationship_type}]->(b) "
        "SET r = row.properties "
        "RETURN count(r) AS imported"
    )


def create_constraints(driver: Any, database: str) -> None:
    with driver.session(database=database) as session:
        for query in CONSTRAINT_QUERIES:
            session.run(query).consume()
        session.run("CALL db.awaitIndexes(30)").consume()


def database_totals(driver: Any, database: str) -> tuple[int, int]:
    row = execute_query(driver, database, TOTALS_QUERY)[0]
    return int(row["node_count"]), int(row["relationship_count"])


def import_transaction(tx: Any, graph: PreparedGraph) -> None:
    # All six node types are imported before the first relationship query.
    for spec in NODE_SPECS:
        query = node_merge_query(spec)
        imported = 0
        for batch in chunks(graph.node_rows[spec.filename]):
            record = tx.run(query, rows=batch).single(strict=True)
            imported += int(record["imported"])
        if imported != len(graph.node_rows[spec.filename]):
            raise RuntimeError(f"Node import count mismatch for {spec.filename}")

    for spec in RELATIONSHIP_SPECS:
        query = relationship_merge_query(spec)
        imported = 0
        for batch in chunks(graph.relationship_rows[spec.filename]):
            record = tx.run(query, rows=batch).single(strict=True)
            imported += int(record["imported"])
        if imported != len(graph.relationship_rows[spec.filename]):
            raise RuntimeError(f"Relationship import count mismatch for {spec.filename}")

    node_count = tx.run("MATCH (n) RETURN count(n) AS count").single(strict=True)["count"]
    relationship_count = tx.run(
        "MATCH ()-[r]->() RETURN count(r) AS count"
    ).single(strict=True)["count"]
    if node_count != EXPECTED_NODE_TOTAL or relationship_count != EXPECTED_RELATIONSHIP_TOTAL:
        raise RuntimeError(
            "In-transaction totals differ from the expected 26 nodes and 65 relationships"
        )


def expected_node_properties(graph: PreparedGraph, spec: NodeSpec) -> dict[str, dict[str, Any]]:
    return {
        row["id"]: dict(row["properties"])
        for row in graph.node_rows[spec.filename]
    }


def expected_relationship_records(
    graph: PreparedGraph, spec: RelationshipSpec
) -> list[dict[str, Any]]:
    return sorted(
        (
            {
                "start_id": row["start_id"],
                "end_id": row["end_id"],
                "properties": dict(row["properties"]),
            }
            for row in graph.relationship_rows[spec.filename]
        ),
        key=lambda row: (
            row["start_id"],
            row["end_id"],
            json.dumps(row["properties"], sort_keys=True),
        ),
    )


def validate_database(driver: Any, database: str, graph: PreparedGraph) -> dict[str, Any]:
    validations: dict[str, Any] = {}

    node_count, relationship_count = database_totals(driver, database)
    validations["node_count"] = node_count
    validations["relationship_count"] = relationship_count
    if (node_count, relationship_count) != (
        EXPECTED_NODE_TOTAL,
        EXPECTED_RELATIONSHIP_TOTAL,
    ):
        raise RuntimeError("Database totals are not exactly 26 nodes and 65 relationships")

    label_counts = {
        row["label"]: int(row["count"])
        for row in execute_query(driver, database, LABEL_COUNTS_QUERY)
    }
    if label_counts != graph.manifest["node_counts"]:
        raise RuntimeError(f"Database label counts differ: {label_counts}")
    validations["label_counts"] = label_counts

    relationship_counts = {
        row["relationship_type"]: int(row["count"])
        for row in execute_query(driver, database, RELATIONSHIP_COUNTS_QUERY)
    }
    if relationship_counts != graph.manifest["relationship_counts"]:
        raise RuntimeError(
            f"Database relationship-type counts differ: {relationship_counts}"
        )
    validations["relationship_counts"] = relationship_counts

    membership = execute_query(
        driver,
        database,
        DATASET_MEMBERSHIP_QUERY,
        dataset_version=EXPECTED_DATASET_VERSION,
    )[0]
    if int(membership["total"]) != int(membership["matching_dataset"]):
        raise RuntimeError("At least one database node lacks the prepared dataset version")
    validations["all_nodes_match_dataset_version"] = True

    for spec in NODE_SPECS:
        query = (
            f"MATCH (n:{spec.label}) "
            f"RETURN n.{spec.id_property} AS id, properties(n) AS properties"
        )
        actual = {
            row["id"]: dict(row["properties"])
            for row in execute_query(driver, database, query)
        }
        expected = expected_node_properties(graph, spec)
        if actual != expected:
            raise RuntimeError(f"Node IDs or property values differ for {spec.label}")

    for spec in RELATIONSHIP_SPECS:
        query = (
            f"MATCH (a:{spec.start_label})-[r:{spec.relationship_type}]->"
            f"(b:{spec.end_label}) "
            f"RETURN a.{spec.start_id_property} AS start_id, "
            f"b.{spec.end_id_property} AS end_id, properties(r) AS properties"
        )
        actual = sorted(
            (
                {
                    "start_id": row["start_id"],
                    "end_id": row["end_id"],
                    "properties": dict(row["properties"]),
                }
                for row in execute_query(driver, database, query)
            ),
            key=lambda row: (
                row["start_id"],
                row["end_id"],
                json.dumps(row["properties"], sort_keys=True),
            ),
        )
        expected = expected_relationship_records(graph, spec)
        if actual != expected:
            raise RuntimeError(
                f"Relationship endpoints or properties differ for {spec.filename}"
            )
    validations["all_ids_endpoints_and_properties_match_csv"] = True

    source_id = graph.node_rows["nodes_source_dataset.csv"][0]["id"]
    source_rows = execute_query(
        driver,
        database,
        SOURCE_PROVENANCE_QUERY,
        source_dataset_id=source_id,
    )
    if len(source_rows) != 1:
        raise RuntimeError("Expected exactly one SourceDataset provenance node")
    expected_source = graph.node_rows["nodes_source_dataset.csv"][0]["properties"]
    if dict(source_rows[0]["properties"]) != expected_source:
        raise RuntimeError("SourceDataset provenance values differ from the CSV")
    validations["source_provenance_exact"] = True

    node_ids = {
        row["node_id"]
        for row in execute_query(driver, database, CONNECTIVITY_NODES_QUERY)
    }
    adjacency: dict[str, set[str]] = defaultdict(set)
    for row in execute_query(driver, database, CONNECTIVITY_EDGES_QUERY):
        adjacency[row["start_id"]].add(row["end_id"])
        adjacency[row["end_id"]].add(row["start_id"])
    if not node_ids:
        raise RuntimeError("Database graph contains no nodes")
    reached: set[str] = set()
    queue: deque[str] = deque([next(iter(node_ids))])
    while queue:
        current = queue.popleft()
        if current in reached:
            continue
        reached.add(current)
        queue.extend(adjacency[current] - reached)
    if reached != node_ids:
        raise RuntimeError("Imported graph is not fully connected")
    validations["fully_connected"] = True

    validations["label_count"] = len(label_counts)
    validations["relationship_type_count"] = len(relationship_counts)
    if validations["label_count"] != EXPECTED_LABEL_COUNT:
        raise RuntimeError("Expected exactly six populated labels")
    if validations["relationship_type_count"] != EXPECTED_RELATIONSHIP_TYPE_COUNT:
        raise RuntimeError("Expected exactly seven populated relationship types")
    return validations


def import_graph(
    graph: PreparedGraph,
    config: Neo4jConfig,
    confirmed_database: str,
    allow_existing_prepared_graph: bool,
) -> dict[str, Any]:
    if confirmed_database != config.database:
        raise RuntimeError(
            "--confirm-database must exactly match NEO4J_DATABASE. Import aborted."
        )
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise RuntimeError(
            "The official neo4j package is required. Install requirements-neo4j.txt."
        ) from exc

    with GraphDatabase.driver(
        config.uri,
        auth=(config.username, config.password),
        connection_timeout=30,
        max_connection_pool_size=5,
    ) as driver:
        driver.verify_connectivity()
        verify_database_identity(driver, config)

        existing_nodes, existing_relationships = database_totals(
            driver, config.database
        )
        if existing_nodes or existing_relationships:
            if not allow_existing_prepared_graph:
                raise RuntimeError(
                    "Target database is not empty. Use --allow-existing-prepared-graph "
                    "only for an exact, previously validated idempotent rerun."
                )
            validate_database(driver, config.database, graph)

        # No schema or data write occurs until the named target is confirmed and
        # its existing contents are either empty or an exact validated rerun.
        create_constraints(driver, config.database)
        with driver.session(database=config.database) as session:
            session.execute_write(import_transaction, graph)
        return validate_database(driver, config.database, graph)


def expanded_validation_queries() -> list[str]:
    queries = [
        DATABASE_IDENTITY_QUERY,
        TOTALS_QUERY,
        LABEL_COUNTS_QUERY,
        RELATIONSHIP_COUNTS_QUERY,
        DATASET_MEMBERSHIP_QUERY,
        SOURCE_PROVENANCE_QUERY,
        CONNECTIVITY_NODES_QUERY,
        CONNECTIVITY_EDGES_QUERY,
    ]
    for spec in NODE_SPECS:
        queries.append(
            f"MATCH (n:{spec.label}) RETURN n.{spec.id_property} AS id, "
            "properties(n) AS properties"
        )
    for spec in RELATIONSHIP_SPECS:
        queries.append(
            f"MATCH (a:{spec.start_label})-[r:{spec.relationship_type}]->"
            f"(b:{spec.end_label}) RETURN a.{spec.start_id_property} AS start_id, "
            f"b.{spec.end_id_property} AS end_id, properties(r) AS properties"
        )
    return queries


def plan_summary(graph: PreparedGraph) -> dict[str, Any]:
    return {
        "mode": "local validation only; no Neo4j connection opened",
        "graph_version": graph.manifest["graph_version"],
        "dataset_version": graph.manifest["authoritative_dataset_version"],
        "node_counts": graph.manifest["node_counts"],
        "relationship_counts": graph.manifest["relationship_counts"],
        "total_nodes": graph.manifest["total_nodes"],
        "total_relationships": graph.manifest["total_relationships"],
        "node_import_order": [spec.label for spec in NODE_SPECS],
        "relationship_file_order": [spec.filename for spec in RELATIONSHIP_SPECS],
        "credential_source": (
            "NEO4J_* environment variables, optionally loaded from ignored "
            "artifacts/knowledge_graph/.env"
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--configure-password",
        action="store_true",
        help="Prompt privately and store the password in the ignored local .env file.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Connect, import, and run all database validation checks.",
    )
    parser.add_argument(
        "--confirm-database",
        default="",
        help="Required with --execute; must exactly equal NEO4J_DATABASE.",
    )
    parser.add_argument(
        "--allow-existing-prepared-graph",
        action="store_true",
        help=(
            "Permit an idempotent rerun only when the existing database already "
            "passes every exact prepared-graph validation."
        ),
    )
    parser.add_argument(
        "--show-validation-queries",
        action="store_true",
        help="Print the exact Cypher validation queries without connecting.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    graph = load_and_validate_local_graph()

    if args.configure_password and args.execute:
        raise RuntimeError("--configure-password and --execute cannot be combined")

    if args.configure_password:
        configure_password()
        return

    if args.show_validation_queries:
        for index, query in enumerate(expanded_validation_queries(), start=1):
            print(f"-- Validation query {index}\n{query};\n")

    if not args.execute:
        print(json.dumps(plan_summary(graph), indent=2, sort_keys=True))
        return

    if not args.confirm_database:
        raise RuntimeError("--confirm-database is required with --execute")
    config = load_config()
    results = import_graph(
        graph,
        config,
        args.confirm_database,
        args.allow_existing_prepared_graph,
    )
    print(
        json.dumps(
            {
                "database": config.database,
                "graph_version": EXPECTED_GRAPH_VERSION,
                "validation": results,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
