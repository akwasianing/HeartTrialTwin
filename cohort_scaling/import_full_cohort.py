#!/usr/bin/env python3
"""Pinned full-cohort importer. Default execution is a completely offline dry run.

Live execution is a separate, explicitly authorized operation. It requires a
pre-created empty local database, dedicated credentials and exact confirmations.
No database creation, deletion, automatic resume, or overwrite is implemented.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit

import import_pilot as pilot
import prepare_full_cohort as preparation


EXPECTED_MANIFEST_SHA256 = "3ef82624d131b36abc1eb9ad4e89b3439fed9f9600b92262c21bbcbfe6cf8757"
NODE_SPECS = pilot.NODE_SPECS
RELATIONSHIP_SPECS = pilot.RELATIONSHIP_SPECS
reference = pilot.reference
DEFAULT_BATCH_SIZE = 250
MAX_BATCH_SIZE = 1000
IDENTITY_QUERY = "CALL db.info() YIELD name RETURN name"


class FullImportError(ValueError):
    """Public error text/details are safe to print; driver messages never are."""

    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details or {}


@dataclass
class PreparedFullCohort:
    manifest: dict = field(repr=False)
    nodes: dict = field(repr=False)
    relationships: dict = field(repr=False)
    payload_sha256: str


def verify_manifest(manifest):
    # The preparation script wrote sorted, indented UTF-8 JSON plus a newline.
    encoded = (json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()
    if hashlib.sha256(encoded).hexdigest() != EXPECTED_MANIFEST_SHA256:
        raise FullImportError("Full-cohort manifest SHA-256 mismatch")
    if (manifest.get("graph_version") != preparation.VERSION
            or manifest.get("authoritative_dataset_version") != preparation.DATASET
            or manifest.get("snapshot_date") != "2026-09-05"):
        raise FullImportError("Full-cohort manifest identity mismatch")


def payload_hash(graph):
    """Hash rows incrementally rather than copying/stringifying the whole graph."""
    digest = hashlib.sha256()
    for specs, values, key in ((NODE_SPECS, graph.nodes, "label"),
                               (RELATIONSHIP_SPECS, graph.relationships, "filename")):
        for spec in specs:
            name = getattr(spec, key)
            digest.update((name + "\n").encode())
            for row in values[name]:
                digest.update((json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode())
    return digest.hexdigest()


def validate_payload(graph):
    verify_manifest(graph.manifest)
    expected = graph.manifest["validation"]
    if set(graph.nodes) != {s.label for s in NODE_SPECS} or set(graph.relationships) != {s.filename for s in RELATIONSHIP_SPECS}:
        raise FullImportError("Full-cohort payload schema mismatch")
    ids = {}
    for spec in NODE_SPECS:
        rows = graph.nodes[spec.label]
        keys = [row["id"] for row in rows]
        if len(keys) != len(set(keys)) or any(not key for key in keys):
            raise FullImportError("Missing or duplicate node identifier")
        if len(rows) != expected["node_counts"][spec.label]:
            raise FullImportError("Node counts differ from pinned manifest")
        allowed = (set(spec.header) - {spec.id_header, ":LABEL"}) | {spec.id_property}
        for row in rows:
            props = row["properties"]
            if (set(row) != {"id", "properties"} or set(props) != allowed
                    or props.get(spec.id_property) != row["id"]
                    or props.get("dataset_version") != preparation.DATASET):
                raise FullImportError("Node schema/identity/provenance mismatch")
            preparation.pilot.assert_safe_fields([props])
        ids[spec.label] = set(keys)
    if ids["Trial"] != set(preparation.membership_ids()) or any(row["id"] != row["properties"]["nct_id"] for row in graph.nodes["Trial"]):
        raise FullImportError("Full frozen membership mismatch")
    if ids["SourceDataset"] != {preparation.DATASET}:
        raise FullImportError("Expected one pinned SourceDataset")
    source = graph.nodes["SourceDataset"][0]["properties"]
    archive = graph.manifest["archive"]
    source_expected = {
        "graph_version": preparation.VERSION, "snapshot_date": "2026-09-05",
        "snapshot_file": archive["filename"], "snapshot_url": archive["source_url"],
        "archive_md5": archive["md5"], "archive_sha256": archive["sha256"],
        "pinned_manifest_sha256": preparation.pilot.MEMBERSHIP_SHA,
    }
    if any(source.get(key) != value for key, value in source_expected.items()):
        raise FullImportError("SourceDataset provenance mismatch")
    outcomes = {row["id"]: row["properties"] for row in graph.nodes["PlannedOutcome"]}
    if any(key != "planned_outcome:" + props["source_record_id"] or props["evidence_safeguard"] != preparation.pilot.SAFEGUARD for key, props in outcomes.items()):
        raise FullImportError("Registered planned outcome provenance/safeguard mismatch")
    triples, counts, linked = set(), Counter(), set()
    for spec in RELATIONSHIP_SPECS:
        allowed = set(spec.header) - {spec.start_header, spec.end_header, ":TYPE"}
        for row in graph.relationships[spec.filename]:
            if row["start_id"] not in ids[spec.start_label] or row["end_id"] not in ids[spec.end_label]:
                raise FullImportError("Missing relationship endpoint")
            key = (spec.start_label, row["start_id"], spec.relationship_type, spec.end_label, row["end_id"])
            if key in triples:
                raise FullImportError("Duplicate relationship")
            triples.add(key)
            counts[spec.relationship_type] += 1
            props = row["properties"]
            if set(row) != {"start_id", "end_id", "properties"} or set(props) != allowed or props.get("dataset_version") != preparation.DATASET:
                raise FullImportError("Relationship schema/provenance mismatch")
            preparation.pilot.assert_safe_fields([props])
            if spec.relationship_type == "HAS_PLANNED_OUTCOME":
                outcome = outcomes[row["end_id"]]
                if outcome["nct_id"] != row["start_id"] or outcome["source_record_id"] != props["source_record_id"]:
                    raise FullImportError("Planned outcome trial/source linkage mismatch")
                linked.add(row["end_id"])
    if (counts != expected["relationship_counts"] or len(triples) != expected["total_relationships"]
            or sum(map(len, graph.nodes.values())) != expected["total_nodes"] or linked != set(outcomes)):
        raise FullImportError("Payload totals/outcome coverage mismatch")
    if payload_hash(graph) != graph.payload_sha256:
        raise FullImportError("Payload changed after verified CSV loading")


def load_full_cohort(directory=preparation.OUTPUT):
    directory = Path(directory)
    path = directory / "full_cohort_manifest.json"
    if preparation.pilot.digest(path) != EXPECTED_MANIFEST_SHA256:
        raise FullImportError("Full-cohort manifest SHA-256 mismatch")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    verify_manifest(manifest)
    # Offline only: full source coverage, original membership, hashes, provenance,
    # endpoints and preserved baseline checks; no ZIP reread or Neo4j driver.
    preparation.validate_saved(directory)
    nodes, relationships = {}, {}
    for spec in NODE_SPECS:
        rows = reference.read_csv(directory / spec.filename, spec.header)
        if any(row[":LABEL"] != spec.label for row in rows):
            raise FullImportError("Unexpected node label")
        nodes[spec.label] = [reference.node_payload(spec, row) for row in rows]
    for spec in RELATIONSHIP_SPECS:
        rows = reference.read_csv(directory / spec.filename, spec.header)
        if any(row[":TYPE"] != spec.relationship_type for row in rows):
            raise FullImportError("Unexpected relationship type")
        relationships[spec.filename] = [reference.relationship_payload(spec, row) for row in rows]
    graph = PreparedFullCohort(manifest, nodes, relationships, "")
    graph.payload_sha256 = payload_hash(graph)
    validate_payload(graph)
    return graph


@dataclass(frozen=True)
class FullConfig:
    uri: str = field(repr=False)
    username: str = field(repr=False)
    password: str = field(repr=False)
    database: str


def validate_target(config):
    try:
        parsed = urlsplit(config.uri)
        host = unquote(parsed.hostname or "").casefold().rstrip(".")
        port = parsed.port
    except ValueError:
        raise FullImportError("Invalid full-cohort URI") from None
    database = config.database
    if pilot.BASELINE_DATABASE in unquote(config.uri).casefold() or database.casefold() == pilot.BASELINE_DATABASE:
        raise FullImportError("Five-trial Aura target is prohibited")
    # The existing Pilot50 uses database `neo4j` on loopback port 7687.
    # Reject that database name on EVERY endpoint, including DNS aliases.
    if database.casefold() in {"neo4j", "system"} or "pilot" in database.casefold():
        raise FullImportError("Pilot50/default/system database is prohibited")
    if not re.fullmatch(r"[a-z][a-z0-9.-]{2,62}", database):
        raise FullImportError("Explicit dedicated lowercase database name is required")
    # Direct Bolt only: no routing discovery or arbitrary remote host names.
    if (parsed.scheme not in {"bolt", "bolt+s"} or host not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"} or (port is not None and not 1 <= port <= 65535)):
        raise FullImportError("Full-cohort target must use direct Bolt on loopback with separate credentials")
    if not config.username.strip() or not config.password.strip():
        raise FullImportError("Dedicated full-cohort credentials are required")


def load_config(env_file=None, *, environ=None):
    values = {}
    if env_file is not None:
        if not Path(env_file).is_file():
            raise FullImportError("Explicit full-cohort environment file was not found")
        from dotenv import dotenv_values
        values.update(dotenv_values(env_file, interpolate=False))
    values.update(os.environ if environ is None else environ)
    names = ("URI", "USERNAME", "PASSWORD", "DATABASE")
    selected = {key: values.get("FULL_NEO4J_" + key, "") for key in names}
    if any(not isinstance(value, str) or not value.strip() for value in selected.values()):
        raise FullImportError("All four dedicated FULL_NEO4J_* settings are required; no fallback")
    config = FullConfig(selected["URI"].strip(), selected["USERNAME"].strip(), selected["PASSWORD"], selected["DATABASE"])
    validate_target(config)
    return config


def validate_batch_size(value):
    if type(value) is not int or not 1 <= value <= MAX_BATCH_SIZE:
        raise FullImportError(f"Batch size must be an integer from 1 to {MAX_BATCH_SIZE}")


def summary(graph, batch_size=DEFAULT_BATCH_SIZE):
    validate_batch_size(batch_size)
    expected = graph.manifest["validation"]
    return {
        "mode": "OFFLINE_DRY_RUN", "network_calls": 0, "validated": True,
        "graph_version": preparation.VERSION, "dataset_version": preparation.DATASET,
        "snapshot_date": graph.manifest["snapshot_date"],
        "manifest_sha256": EXPECTED_MANIFEST_SHA256, "payload_sha256": graph.payload_sha256,
        **{key: expected[key] for key in ("node_counts", "relationship_counts", "total_nodes", "total_relationships")},
        "batch_size": batch_size,
        "planned_data_transactions": sum(math.ceil(len(rows) / batch_size) for group in (graph.nodes, graph.relationships) for rows in group.values()),
    }


def _read(driver, database, query):
    records, _, _ = driver.execute_query(query, parameters_={}, database_=database, routing_="r")
    return [dict(record) for record in records]


def _totals(driver, database):
    rows = _read(driver, database, reference.TOTALS_QUERY)
    if len(rows) != 1:
        raise FullImportError("Invalid database totals response")
    return int(rows[0]["node_count"]), int(rows[0]["relationship_count"])


def _verify_imported(driver, database, graph):
    expected = graph.manifest["validation"]
    if _totals(driver, database) != (expected["total_nodes"], expected["total_relationships"]):
        raise FullImportError("Imported full-cohort totals mismatch")
    # Stream result rows, comparing one label/type at a time rather than sorting
    # duplicate copies of the entire graph in memory.
    with driver.session(database=database, default_access_mode="READ", fetch_size=250) as session:
        for spec in NODE_SPECS:
            by_id = {row["id"]: row["properties"] for row in graph.nodes[spec.label]}
            seen = set()
            result = session.run(f"MATCH (n:{spec.label}) RETURN n.{spec.id_property} AS id, properties(n) AS properties, labels(n) AS labels")
            for row in result:
                key = row["id"]
                if key in seen or key not in by_id or dict(row["properties"]) != by_id[key] or row["labels"] != [spec.label]:
                    raise FullImportError("Imported node IDs/labels/properties mismatch")
                seen.add(key)
            if seen != set(by_id):
                raise FullImportError("Missing imported nodes")
        for spec in RELATIONSHIP_SPECS:
            by_pair = {(row["start_id"], row["end_id"]): row["properties"] for row in graph.relationships[spec.filename]}
            seen = set()
            query = (f"MATCH (a:{spec.start_label})-[r:{spec.relationship_type}]->(b:{spec.end_label}) "
                     f"RETURN a.{spec.start_id_property} AS start_id, b.{spec.end_id_property} AS end_id, properties(r) AS properties")
            for row in session.run(query):
                key = (row["start_id"], row["end_id"])
                if key in seen or key not in by_pair or dict(row["properties"]) != by_pair[key]:
                    raise FullImportError("Imported relationship endpoints/properties mismatch")
                seen.add(key)
            if seen != set(by_pair):
                raise FullImportError("Missing imported relationships")


def execute_full_cohort(graph, config, *, confirm_database, confirm_graph_version,
                        batch_size=DEFAULT_BATCH_SIZE, driver_factory=None):
    """Future live path. Tests inject a fake driver; default CLI never calls it."""
    validate_target(config)
    validate_batch_size(batch_size)
    if confirm_database != config.database or confirm_graph_version != preparation.VERSION:
        raise FullImportError("Exact database-name and graph-version confirmations are required")
    validate_payload(graph)
    progress = {"stage": "connection", "confirmed_data_transactions": 0,
                "confirmed_node_rows": 0, "confirmed_relationship_rows": 0,
                "schema_may_exist": False, "commit_outcome_unknown": False}
    try:
        if driver_factory is None:
            from neo4j import GraphDatabase
            driver_factory = GraphDatabase.driver
        with driver_factory(config.uri, auth=(config.username, config.password),
                            connection_timeout=30, max_connection_pool_size=1) as driver:
            driver.verify_connectivity()
            progress["stage"] = "preflight"
            identity = _read(driver, config.database, IDENTITY_QUERY)
            if len(identity) != 1 or identity[0].get("name") != config.database:
                raise FullImportError("Live database identity mismatch")
            if _totals(driver, config.database) != (0, 0):
                raise FullImportError("Target must be empty; completed or partial imports are refused without writes")
            progress["stage"] = "constraints"
            progress["schema_may_exist"] = True
            reference.create_constraints(driver, config.database)
            if _totals(driver, config.database) != (0, 0):
                raise FullImportError("Target changed during preflight; refusing data writes")
            with driver.session(database=config.database) as session:
                for specs, rows_by_key, key_name, category in (
                    (NODE_SPECS, graph.nodes, "label", "node"),
                    (RELATIONSHIP_SPECS, graph.relationships, "filename", "relationship"),
                ):
                    for spec in specs:
                        key = getattr(spec, key_name)
                        rows = rows_by_key[key]
                        query = reference.node_merge_query(spec) if category == "node" else reference.relationship_merge_query(spec)
                        for offset in range(0, len(rows), batch_size):
                            batch = rows[offset:offset + batch_size]
                            progress.update(stage="data", category=category, file=spec.filename,
                                            batch_index=offset // batch_size + 1)
                            # Explicit one-batch transaction: no managed retry that
                            # could silently repeat a batch after an ambiguous commit.
                            with session.begin_transaction() as tx:
                                count = tx.run(query, rows=batch).single(strict=True)["imported"]
                                if count != len(batch):
                                    raise FullImportError("Batch count mismatch; current transaction rolled back")
                                progress["commit_outcome_unknown"] = True
                                tx.commit()
                                progress["commit_outcome_unknown"] = False
                            progress["confirmed_data_transactions"] += 1
                            progress[f"confirmed_{category}_rows"] += len(batch)
            progress["stage"] = "verification"
            _verify_imported(driver, config.database, graph)
    except Exception as exc:
        message = str(exc) if isinstance(exc, FullImportError) else f"Neo4j operation failed ({type(exc).__name__}); connection details suppressed"
        raise FullImportError(message, {
            **progress, "status": "STOPPED", "exception_type": type(exc).__name__,
            "automatic_retry": False, "automatic_cleanup": False,
            "next_action": "Human review required; do not clear or automatically resume this target. Prior commits may remain.",
        }) from None
    return {"mode": "IMPORTED_AND_VERIFIED", "graph_version": preparation.VERSION,
            "database": config.database, "batch_size": batch_size,
            "confirmed_data_transactions": progress["confirmed_data_transactions"],
            "total_nodes": progress["confirmed_node_rows"],
            "total_relationships": progress["confirmed_relationship_rows"],
            "manifest_sha256": EXPECTED_MANIFEST_SHA256, "payload_sha256": graph.payload_sha256}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-dir", type=Path, default=preparation.OUTPUT)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--confirm-database")
    parser.add_argument("--confirm-graph-version")
    args = parser.parse_args(argv)
    validate_batch_size(args.batch_size)
    graph = load_full_cohort(args.full_dir)
    if not args.execute:
        print(json.dumps(summary(graph, args.batch_size), indent=2, sort_keys=True))
        return 0
    config = load_config(args.env_file)
    result = execute_full_cohort(graph, config, confirm_database=args.confirm_database,
                                 confirm_graph_version=args.confirm_graph_version, batch_size=args.batch_size)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        error = str(exc) if isinstance(exc, FullImportError) else f"Offline validation failed ({type(exc).__name__}); inspect local source files"
        print(json.dumps({"status": "REFUSED", "error": error,
                          "details": exc.details if isinstance(exc, FullImportError) else {}}, sort_keys=True), file=sys.stderr)
        raise SystemExit(1) from None
