#!/usr/bin/env python3
"""Isolated pilot importer. Default dry run is entirely offline.

Live execution requires --execute, dedicated PILOT_NEO4J_* configuration,
explicit database/pilot confirmation, and an empty separate database.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import unquote, urlsplit

import prepare_pilot as preparation


EXPECTED_MANIFEST_SHA256 = "af9ed17cc73d75cce3ec34c698beb84841a6f3f5a7d01e61e2caf2b5ea3d6f56"
BASELINE_DATABASE = "57aa5fa3"
BASELINE_HOST = "57aa5fa3.databases.neo4j.io"


class PilotImportError(ValueError):
    """A local payload or isolated target failed validation."""


def _load_reference():
    path = preparation.ROOT / "artifacts/knowledge_graph/import_to_neo4j.py"
    spec = importlib.util.spec_from_file_location("htt_pilot_import_reference", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


reference = _load_reference()  # Definitions only; no credentials or driver loaded.

# Exact pilot headers. Keep baseline specifications and artifacts unchanged.
NODE_HEADERS = {
    "Trial": ("trial_id:ID(Trial)", "nct_id", "brief_title", "study_type", "phase", "source_table", "source_record_id", "source_evidence_status", "dataset_version", ":LABEL"),
    "ConditionTerm": ("condition_id:ID(ConditionTerm)", "name", "normalized_name", "source_table", "dataset_version", ":LABEL", "source_kind"),
    "Intervention": ("intervention_id:ID(Intervention)", "name", "normalized_name", "source_table", "dataset_version", ":LABEL", "intervention_type"),
    "Sponsor": ("sponsor_id:ID(Sponsor)", "name", "normalized_name", "source_table", "dataset_version", ":LABEL", "agency_class"),
    "PlannedOutcome": ("planned_outcome_id:ID(PlannedOutcome)", "source_record_id", "nct_id", "outcome_type", "measure", "time_frame", "population", "description", "source_table", "evidence_safeguard", "dataset_version", ":LABEL"),
    "SourceDataset": ("source_dataset_id:ID(SourceDataset)", "dataset_version", "graph_version", "snapshot_date", "snapshot_file", "snapshot_url", "archive_md5", "archive_sha256", "pinned_manifest_sha256", ":LABEL"),
}
NODE_SPECS = tuple(
    reference.NodeSpec(item.filename, item.label, item.id_header, item.id_property, NODE_HEADERS[item.label])
    for item in reference.NODE_SPECS
)
RELATIONSHIP_SPECS = tuple(
    reference.RelationshipSpec(
        {"relationships_condition_source_dataset.csv": "relationships_condition_term_source_dataset.csv",
         "relationships_outcome_source_dataset.csv": "relationships_planned_outcome_source_dataset.csv"}.get(item.filename, item.filename),
        item.start_label, item.start_id_property, item.start_header,
        item.relationship_type, item.end_label, item.end_id_property, item.end_header,
        (item.start_header, item.end_header, "source_table", "source_record_ids", "dataset_version", ":TYPE")
        if item.relationship_type in {"HAS_SUBMITTED_CONDITION", "HAS_BROWSE_CONDITION"} else item.header,
    )
    for item in reference.RELATIONSHIP_SPECS
)


@dataclass
class PreparedPilot:
    manifest: dict
    nodes: dict
    relationships: dict


def validate_payload(graph):
    manifest = graph.manifest
    if manifest.get("pilot_version") != preparation.VERSION or manifest.get("authoritative_dataset_version") != preparation.DATASET or manifest.get("snapshot_date") != "2026-09-05":
        raise PilotImportError("Pilot manifest identity mismatch")
    expected = manifest["validation"]
    if set(graph.nodes) != {item.label for item in NODE_SPECS} or set(graph.relationships) != {item.filename for item in RELATIONSHIP_SPECS}:
        raise PilotImportError("Pilot payload label/file schema mismatch")
    node_ids = {}
    for spec in NODE_SPECS:
        rows = graph.nodes[spec.label]
        ids = [row["id"] for row in rows]
        if len(ids) != len(set(ids)) or any(not value for value in ids):
            raise PilotImportError("Missing or duplicate node identifier")
        if len(rows) != expected["node_counts"][spec.label]:
            raise PilotImportError("Pilot node counts differ from verified manifest")
        for row in rows:
            props = row["properties"]
            if props.get(spec.id_property) != row["id"] or props.get("dataset_version") != preparation.DATASET:
                raise PilotImportError("Node identity/provenance mismatch")
            preparation.assert_safe_fields([props])
        node_ids[spec.label] = set(ids)
    trial_rows = graph.nodes["Trial"]
    if node_ids["Trial"] != set(manifest["selection"]["selected_nct_ids"]) or any(row["properties"].get("nct_id") != row["id"] for row in trial_rows):
        raise PilotImportError("Pilot trial membership mismatch")
    source_rows = graph.nodes["SourceDataset"]
    if len(source_rows) != 1 or source_rows[0]["id"] != preparation.DATASET:
        raise PilotImportError("Expected exactly one pinned SourceDataset")
    source = source_rows[0]["properties"]
    expected_source = {
        "graph_version": preparation.VERSION, "snapshot_date": "2026-09-05",
        "snapshot_file": manifest["archive"]["filename"],
        "snapshot_url": manifest["archive"]["source_url"],
        "pinned_manifest_sha256": preparation.MEMBERSHIP_SHA,
        "archive_md5": manifest["archive"]["md5"], "archive_sha256": manifest["archive"]["sha256"],
    }
    if any(source.get(key) != value for key, value in expected_source.items()):
        raise PilotImportError("SourceDataset provenance mismatch")
    outcomes = {row["id"]: row["properties"] for row in graph.nodes["PlannedOutcome"]}
    if any(props.get("evidence_safeguard") != preparation.SAFEGUARD or key != "planned_outcome:" + props.get("source_record_id", "") for key, props in outcomes.items()):
        raise PilotImportError("Registered outcome provenance/safeguard mismatch")
    relationship_keys, counts, outcome_links = set(), Counter(), set()
    for spec in RELATIONSHIP_SPECS:
        for row in graph.relationships[spec.filename]:
            if row["start_id"] not in node_ids[spec.start_label] or row["end_id"] not in node_ids[spec.end_label]:
                raise PilotImportError("Missing relationship endpoint")
            key = (spec.start_label, row["start_id"], spec.relationship_type, spec.end_label, row["end_id"])
            if key in relationship_keys:
                raise PilotImportError("Duplicate relationship")
            relationship_keys.add(key)
            counts[spec.relationship_type] += 1
            props = row["properties"]
            preparation.assert_safe_fields([props])
            if props.get("dataset_version") != preparation.DATASET:
                raise PilotImportError("Relationship provenance mismatch")
            if spec.relationship_type == "HAS_PLANNED_OUTCOME":
                outcome = outcomes[row["end_id"]]
                if outcome["nct_id"] != row["start_id"] or props.get("source_record_id") != outcome["source_record_id"]:
                    raise PilotImportError("Planned outcome trial/source linkage mismatch")
                outcome_links.add(row["end_id"])
    if counts != expected["relationship_counts"] or len(relationship_keys) != expected["total_relationships"] or sum(map(len, graph.nodes.values())) != expected["total_nodes"]:
        raise PilotImportError("Pilot totals differ from verified manifest")
    if outcome_links != set(outcomes):
        raise PilotImportError("Unlinked planned outcomes")


def load_pilot(directory=preparation.OUTPUT):
    directory = Path(directory)
    if preparation.digest(directory / "pilot_manifest.json") != EXPECTED_MANIFEST_SHA256:
        raise PilotImportError("Pilot manifest SHA-256 mismatch")
    # Reuses frozen membership, output checksums, endpoint, connectivity, outcome,
    # baseline-preservation and source-file checks without archive access.
    preparation.validate_saved(directory)
    manifest = json.loads((directory / "pilot_manifest.json").read_text())
    nodes, relationships = {}, {}
    for spec in NODE_SPECS:
        rows = reference.read_csv(directory / spec.filename, spec.header)
        if any(row[":LABEL"] != spec.label for row in rows):
            raise PilotImportError("Unexpected node label")
        nodes[spec.label] = [reference.node_payload(spec, row) for row in rows]
    for spec in RELATIONSHIP_SPECS:
        rows = reference.read_csv(directory / spec.filename, spec.header)
        if any(row[":TYPE"] != spec.relationship_type for row in rows):
            raise PilotImportError("Unexpected relationship type")
        relationships[spec.filename] = [reference.relationship_payload(spec, row) for row in rows]
    graph = PreparedPilot(manifest, nodes, relationships)
    validate_payload(graph)
    return graph


@dataclass(frozen=True)
class PilotConfig:
    uri: str = field(repr=False)
    username: str = field(repr=False)
    password: str = field(repr=False)
    database: str


def validate_target(config):
    try:
        parsed = urlsplit(config.uri)
        host = unquote(parsed.hostname or "").casefold().rstrip(".")
        port = parsed.port
    except ValueError as exc:
        raise PilotImportError("Invalid pilot URI") from exc
    if config.database.strip().casefold() == BASELINE_DATABASE or BASELINE_DATABASE in unquote(config.uri).casefold() or host == BASELINE_HOST:
        raise PilotImportError("Original five-trial database/endpoint is prohibited")
    if not config.database or config.database != config.database.strip():
        raise PilotImportError("Explicit pilot database name is required")
    if parsed.scheme not in {"neo4j", "neo4j+s", "bolt", "bolt+s"} or not host or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise PilotImportError("Pilot URI must use a supported scheme and separate credentials")
    if port is not None and not 1 <= port <= 65535:
        raise PilotImportError("Invalid pilot port")
    if not config.username.strip() or not config.password:
        raise PilotImportError("Dedicated pilot username/password are required")


def load_config(env_file=None, *, environ=None):
    # No fallback to NEO4J_* variables or baseline .env files.
    values = {}
    if env_file is not None:
        if not Path(env_file).is_file():
            raise PilotImportError("Explicit pilot environment file was not found")
        from dotenv import dotenv_values
        values.update(dotenv_values(env_file))
    values.update(os.environ if environ is None else environ)
    names = ("URI", "USERNAME", "PASSWORD", "DATABASE")
    selected = {name: values.get("PILOT_NEO4J_" + name, "") for name in names}
    if any(not isinstance(value, str) or not value.strip() for value in selected.values()):
        raise PilotImportError("All four dedicated PILOT_NEO4J_* settings are required")
    config = PilotConfig(selected["URI"].strip(), selected["USERNAME"].strip(), selected["PASSWORD"], selected["DATABASE"].strip())
    validate_target(config)
    return config


def summary(graph):
    payload = {"nodes": graph.nodes, "relationships": graph.relationships}
    return {
        "mode": "OFFLINE_DRY_RUN", "network_calls": 0,
        "pilot_version": graph.manifest["pilot_version"],
        "dataset_version": preparation.DATASET, "snapshot_date": graph.manifest["snapshot_date"],
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "node_counts": graph.manifest["validation"]["node_counts"],
        "relationship_counts": graph.manifest["validation"]["relationship_counts"],
        "total_nodes": sum(map(len, graph.nodes.values())),
        "total_relationships": sum(map(len, graph.relationships.values())),
        "payload_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
        "validated": True,
    }


def _execute_query(driver, database, query, **parameters):
    records, _, _ = driver.execute_query(query, parameters_=parameters, database_=database)
    return [dict(record) for record in records]


def _totals(driver, database):
    row = _execute_query(driver, database, reference.TOTALS_QUERY)[0]
    return int(row["node_count"]), int(row["relationship_count"])


def _verify_imported(driver, database, graph):
    expected = graph.manifest["validation"]
    if _totals(driver, database) != (expected["total_nodes"], expected["total_relationships"]):
        raise PilotImportError("Imported pilot totals mismatch")
    for spec in NODE_SPECS:
        rows = _execute_query(driver, database, f"MATCH (n:{spec.label}) RETURN n.{spec.id_property} AS id, properties(n) AS properties")
        if len(rows) != len(graph.nodes[spec.label]) or {row["id"]: row["properties"] for row in rows} != {row["id"]: row["properties"] for row in graph.nodes[spec.label]}:
            raise PilotImportError("Imported node IDs/properties mismatch")
    for spec in RELATIONSHIP_SPECS:
        query = (f"MATCH (a:{spec.start_label})-[r:{spec.relationship_type}]->(b:{spec.end_label}) "
                 f"RETURN a.{spec.start_id_property} AS start_id, b.{spec.end_id_property} AS end_id, properties(r) AS properties")
        rows = _execute_query(driver, database, query)
        canonical = lambda values: sorted(json.dumps(row, sort_keys=True, ensure_ascii=False) for row in values)
        if canonical(rows) != canonical(graph.relationships[spec.filename]):
            raise PilotImportError("Imported relationship endpoints/properties mismatch")


def execute_pilot(graph, config, *, confirm_database, confirm_pilot_version, driver_factory=None):
    """Future explicitly authorized execution; never invoked by offline mode."""
    validate_target(config)  # Recheck even if a caller bypassed load_config.
    validate_payload(graph)
    if confirm_database != config.database or confirm_pilot_version != preparation.VERSION:
        raise PilotImportError("Exact database and pilot-version confirmations are required")
    if driver_factory is None:
        from neo4j import GraphDatabase
        driver_factory = GraphDatabase.driver
    try:
        with driver_factory(config.uri, auth=(config.username, config.password), connection_timeout=30, max_connection_pool_size=2) as driver:
            driver.verify_connectivity()
            identity = _execute_query(driver, config.database, "CALL db.info() YIELD name RETURN name")
            if len(identity) != 1 or identity[0].get("name") != config.database:
                raise PilotImportError("Live database identity mismatch")
            if _totals(driver, config.database) != (0, 0):
                raise PilotImportError("Pilot target must be empty; existing data will not be merged or cleared")
            reference.create_constraints(driver, config.database)

            def transaction(tx):
                for spec in NODE_SPECS:
                    for batch in reference.chunks(graph.nodes[spec.label]):
                        count = tx.run(reference.node_merge_query(spec), rows=batch).single(strict=True)["imported"]
                        if count != len(batch):
                            raise PilotImportError("Node batch count mismatch")
                for spec in RELATIONSHIP_SPECS:
                    for batch in reference.chunks(graph.relationships[spec.filename]):
                        count = tx.run(reference.relationship_merge_query(spec), rows=batch).single(strict=True)["imported"]
                        if count != len(batch):
                            raise PilotImportError("Relationship batch count mismatch")
                _expected = graph.manifest["validation"]
                for query, key in (("MATCH (n) RETURN count(n) AS count", "total_nodes"), ("MATCH ()-[r]->() RETURN count(r) AS count", "total_relationships")):
                    if tx.run(query).single(strict=True)["count"] != _expected[key]:
                        raise PilotImportError("In-transaction pilot totals mismatch")
            with driver.session(database=config.database) as session:
                session.execute_write(transaction)
            _verify_imported(driver, config.database, graph)
    except PilotImportError:
        raise
    except Exception as exc:
        # Driver messages may embed URIs; do not expose raw exception text.
        raise PilotImportError(f"Pilot operation failed ({type(exc).__name__}); connection details suppressed") from None
    return {"mode": "IMPORTED_AND_VERIFIED", "pilot_version": preparation.VERSION, "database": config.database}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-dir", type=Path, default=preparation.OUTPUT)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--confirm-database")
    parser.add_argument("--confirm-pilot-version")
    args = parser.parse_args(argv)
    graph = load_pilot(args.pilot_dir)
    if not args.execute:
        print(json.dumps(summary(graph), indent=2, sort_keys=True))
        return 0
    config = load_config(args.env_file)
    result = execute_pilot(graph, config, confirm_database=args.confirm_database, confirm_pilot_version=args.confirm_pilot_version)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Pilot import refused: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
