#!/usr/bin/env python3
"""Separate, bounded, read-only retrieval for the pinned 2,824-trial graph."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import queries


ROOT = Path(__file__).resolve().parents[2]
GRAPH_DIR = ROOT / "artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1"
MANIFEST_SHA256 = "3ef82624d131b36abc1eb9ad4e89b3439fed9f9600b92262c21bbcbfe6cf8757"
DATABASE = "hearttrialtwin-full2824"
DATASET = "HTT-P1-AACT-20260905"
GRAPH = "HTT-KG-AACT-20260905-FULL2824-v1"
SNAPSHOT = "2026-09-05"
MAX_TRIALS = 20
MAX_PAGE_SIZE = 200
TIMEOUT_SECONDS = 30.0
PLANNED_SAFEGUARD = "Registered planned outcomes are not observed clinical results."
SNAPSHOT_SAFEGUARD = "September 5, 2026 snapshot values may include amendments; original-registration availability is not asserted."

# category, label, ID property, source table, approved node properties
EVIDENCE_SPECS = {
    "HAS_SUBMITTED_CONDITION": ("submitted_conditions", "ConditionTerm", "condition_id", "conditions.txt", ("condition_id", "name", "normalized_name", "source_kind")),
    "HAS_BROWSE_CONDITION": ("browse_conditions", "ConditionTerm", "condition_id", "browse_conditions.txt", ("condition_id", "name", "normalized_name", "source_kind")),
    "HAS_INTERVENTION": ("interventions", "Intervention", "intervention_id", "interventions.txt", ("intervention_id", "name", "normalized_name", "intervention_type")),
    "LEAD_SPONSORED_BY": ("lead_sponsors", "Sponsor", "sponsor_id", "sponsors.txt", ("sponsor_id", "name", "normalized_name", "agency_class")),
    "HAS_PLANNED_OUTCOME": ("planned_outcomes", "PlannedOutcome", "planned_outcome_id", "design_outcomes.txt", ("planned_outcome_id", "nct_id", "source_record_id", "outcome_type", "measure", "time_frame", "population", "description", "evidence_safeguard")),
}
TRIAL_FIELDS = ("trial_id", "nct_id", "brief_title", "study_type", "phase", "source_table", "source_record_id", "source_evidence_status", "dataset_version")
SOURCE_FIELDS = ("source_dataset_id", "dataset_version", "graph_version", "snapshot_date", "snapshot_file", "snapshot_url", "archive_md5", "archive_sha256", "pinned_manifest_sha256")
REL_FIELDS = ("dataset_version", "source_table", "source_record_id", "source_record_ids")


class RetrievalError(RuntimeError):
    """Errors are safe to display and never include raw driver exceptions."""


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class Contract:
    manifest: dict = field(repr=False)
    membership: frozenset[str] = field(repr=False)

    @property
    def source(self):
        archive = self.manifest["archive"]
        return {"source_dataset_id": DATASET, "dataset_version": DATASET,
                "graph_version": GRAPH, "snapshot_date": SNAPSHOT,
                "snapshot_file": archive["filename"], "snapshot_url": archive["source_url"],
                "archive_md5": archive["md5"], "archive_sha256": archive["sha256"],
                "pinned_manifest_sha256": self.manifest["membership"]["frozen_source_sha256"]}


def load_contract(directory=GRAPH_DIR):
    directory = Path(directory)
    path = directory / "full_cohort_manifest.json"
    if sha256(path) != MANIFEST_SHA256:
        raise RetrievalError("Full-cohort manifest SHA-256 mismatch")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (manifest["graph_version"], manifest["authoritative_dataset_version"], manifest["snapshot_date"]) != (GRAPH, DATASET, SNAPSHOT):
        raise RetrievalError("Pinned manifest identity mismatch")
    membership_path = directory / manifest["membership"]["path"]
    if sha256(membership_path) != manifest["files_sha256"][membership_path.name]:
        raise RetrievalError("Membership SHA-256 mismatch")
    if sha256(ROOT / manifest["membership"]["frozen_source"]) != manifest["membership"]["frozen_source_sha256"]:
        raise RetrievalError("Original frozen manifest SHA-256 mismatch")
    with membership_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    ids = [row["nct_id"] for row in rows]
    if (len(ids) != manifest["membership"]["count"] or len(ids) != len(set(ids))
            or any(row["dataset_version"] != DATASET or row["graph_version"] != GRAPH for row in rows)
            or any(not re.fullmatch(r"NCT\d{8}", nct) for nct in ids)):
        raise RetrievalError("Pinned membership identity/uniqueness mismatch")
    return Contract(manifest, frozenset(ids))


@dataclass(frozen=True)
class Config:
    uri: str = field(repr=False)
    username: str = field(repr=False)
    password: str = field(repr=False)
    database: str = DATABASE


def validate_config(config):
    if config.database != DATABASE:
        raise RetrievalError("Only the dedicated hearttrialtwin-full2824 database is allowed")
    try:
        parsed = urlsplit(config.uri)
        host = unquote(parsed.hostname or "").casefold().rstrip(".")
        port = parsed.port
    except ValueError:
        raise RetrievalError("Invalid local Neo4j URI") from None
    if (parsed.scheme not in {"bolt", "bolt+s"} or host not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"} or (port is not None and not 1 <= port <= 65535)):
        raise RetrievalError("Only direct local Bolt with separate credentials is allowed")
    if not config.username.strip() or not config.password.strip():
        raise RetrievalError("Dedicated read-only credentials are required")


def load_config(env_file=None, *, environ=None):
    values = {}
    # Only this component's file is considered; no Aura/importer fallback.
    path = Path(env_file) if env_file is not None else ROOT / "full_cohort_graphrag/.env"
    if path.is_file():
        from dotenv import dotenv_values
        values.update(dotenv_values(path, interpolate=False))
    elif env_file is not None:
        raise RetrievalError("Explicit environment file was not found")
    values.update(os.environ if environ is None else environ)
    selected = [values.get("FULL_GRAPHRAG_NEO4J_" + name, "") for name in ("URI", "USERNAME", "PASSWORD", "DATABASE")]
    if any(not isinstance(value, str) or not value.strip() for value in selected):
        raise RetrievalError("All four FULL_GRAPHRAG_NEO4J_* settings are required; no fallback")
    config = Config(selected[0].strip(), selected[1].strip(), selected[2], selected[3])
    validate_config(config)
    return config


def project(value, fields):
    return {key: value[key] for key in fields if key in value and value[key] is not None}


def nct_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"NCT\d{8}", value.strip(), re.IGNORECASE):
        raise RetrievalError("NCT ID must be NCT followed by eight digits")
    return value.strip().upper()


def page_bounds(limit, offset, maximum=MAX_PAGE_SIZE):
    if type(limit) is not int or not 1 <= limit <= maximum or type(offset) is not int or offset < 0:
        raise RetrievalError(f"Limit must be 1–{maximum} and offset must be a nonnegative integer")


def pagination(total, returned, limit, offset):
    expected = min(limit, max(0, total - offset))
    if returned != expected:
        raise RetrievalError("Page size differs from counted evidence; graph may have changed")
    return {"total": total, "returned": returned, "limit": limit, "offset": offset,
            "has_more": offset + returned < total,
            "next_offset": offset + returned if offset + returned < total else None,
            "all_evidence_returned": offset == 0 and returned == total}


class FullCohortRetriever:
    def __init__(self, config, *, driver=None, contract=None):
        validate_config(config)
        self.config = config
        self.contract = contract or load_contract()
        self.source = None
        self._owns_driver = driver is None
        if driver is None:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(config.uri, auth=(config.username, config.password),
                                          connection_timeout=15, max_connection_pool_size=1)
        self.driver = driver

    def __enter__(self):
        return self

    def __exit__(self, *_):
        if self._owns_driver:
            self.driver.close()

    def _run(self, query, parameters=None, *, maximum):
        if query not in queries.READ_ONLY_QUERIES:
            raise RetrievalError("Query is not in the fixed read-only allowlist")
        from neo4j import Query
        try:
            records, _, _ = self.driver.execute_query(
                Query(query, timeout=TIMEOUT_SECONDS), parameters_=dict(parameters or {}),
                database_=DATABASE, routing_="r")
        except Exception as exc:
            raise RetrievalError(f"Neo4j read failed ({type(exc).__name__}); connection details suppressed") from None
        if len(records) > maximum:
            raise RetrievalError("Query exceeded its bounded result contract")
        return [dict(row) for row in records]

    def _source(self, value):
        safe = project(value or {}, SOURCE_FIELDS)
        if safe != self.contract.source:
            raise RetrievalError("Live SourceDataset provenance does not match the pinned manifest")
        return safe

    def verify_connection(self):
        self.source = None
        try:
            self.driver.verify_connectivity()
        except Exception as exc:
            raise RetrievalError(f"Neo4j connectivity failed ({type(exc).__name__}); connection details suppressed") from None
        rows = self._run(queries.DATABASE_INFO, maximum=2)
        if rows != [{"name": DATABASE}]:
            raise RetrievalError("Live database identity mismatch")
        expected = self.contract.manifest["validation"]
        totals = self._run(queries.TOTALS, maximum=1)
        if totals != [{"node_count": expected["total_nodes"], "relationship_count": expected["total_relationships"]}]:
            raise RetrievalError("Live graph totals differ from the pinned manifest")
        labels = self._run(queries.LABEL_COUNTS, maximum=16)
        types = self._run(queries.RELATIONSHIP_COUNTS, maximum=16)
        if ({row["label"]: row["count"] for row in labels} != expected["node_counts"]
                or {row["relationship_type"]: row["count"] for row in types} != expected["relationship_counts"]):
            raise RetrievalError("Live graph label/relationship counts mismatch")
        rows = self._run(queries.SOURCE_DATASET, maximum=2)
        if len(rows) != 1:
            raise RetrievalError("Expected exactly one SourceDataset")
        self.source = self._source(rows[0]["source_dataset"])
        return {"verified": True, "database": DATABASE, "manifest_sha256": MANIFEST_SHA256,
                "source_dataset": self.source, "node_counts": expected["node_counts"],
                "relationship_counts": expected["relationship_counts"]}

    def _ready(self):
        if self.source is None:
            raise RetrievalError("Graph verification is required before retrieval")

    def _base(self, workflow):
        self._ready()
        return {"schema_version": "HTT-FULL-STATIC-RETRIEVAL-v1", "workflow": workflow,
                "dataset_version": DATASET, "graph_version": GRAPH, "snapshot_date": SNAPSHOT,
                "manifest_sha256": MANIFEST_SHA256, "source_dataset": dict(self.source),
                "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                "safeguards": {"planned_outcomes": PLANNED_SAFEGUARD,
                               "snapshot": SNAPSHOT_SAFEGUARD, "read_only": True,
                               "no_answer_generation": True}}

    def _trials(self, ids):
        known = [nct for nct in ids if nct in self.contract.membership]
        if not known:
            return {}
        rows = self._run(queries.TRIALS, {"nct_ids": known, "limit": len(known) + 1}, maximum=len(known) + 1)
        result = {}
        for row in rows:
            trial = project(row["trial"], TRIAL_FIELDS)
            nct = trial.get("nct_id")
            if (nct not in known or nct in result or trial.get("trial_id") != nct
                    or trial.get("dataset_version") != DATASET
                    or row.get("membership_type") != "MEMBER_OF_DATASET"
                    or project(row.get("membership_properties") or {}, ("dataset_version",)) != {"dataset_version": DATASET}):
                raise RetrievalError("Trial identity/membership provenance mismatch")
            self._source(row.get("source_dataset"))
            result[nct] = {"trial": trial, "dataset_relationship": {
                "type": row["membership_type"], "properties": {"dataset_version": DATASET},
                "start_id": nct, "end_id": self.source["source_dataset_id"]}}
        if set(result) != set(known):
            raise RetrievalError("Frozen trial missing from live graph")
        return result

    def _counts(self, ids, types):
        result = {nct: {rel: 0 for rel in types} for nct in ids}
        if not ids:
            return result
        bound = len(ids) * len(types)
        rows = self._run(queries.EVIDENCE_COUNTS, {"nct_ids": ids, "relationship_types": types, "limit": bound + 1}, maximum=bound + 1)
        seen = set()
        for row in rows:
            key = (row["nct_id"], row["relationship_type"])
            if key in seen or key[0] not in result or key[1] not in types or type(row["count"]) is not int or row["count"] < 1:
                raise RetrievalError("Invalid evidence count response")
            seen.add(key)
            result[key[0]][key[1]] = row["count"]
        return result

    def _evidence(self, ids, types, limit, offset):
        if not ids:
            return []
        rows = self._run(queries.EVIDENCE_PAGE, {"nct_ids": ids, "relationship_types": types,
                         "limit": limit, "offset": offset}, maximum=limit)
        result, seen, ordering = [], set(), []
        for row in rows:
            nct, rel, entity_id = row["nct_id"], row["relationship_type"], row["evidence_id"]
            if nct not in ids or rel not in types:
                raise RetrievalError("Unexpected evidence association")
            category, label, id_property, table, fields = EVIDENCE_SPECS[rel]
            props = project(row["evidence_properties"], (*fields, "source_table", "dataset_version"))
            relationship = project(row["relationship_properties"], REL_FIELDS)
            if (row["evidence_labels"] != [label] or not entity_id or props.get(id_property) != entity_id
                    or props.get("dataset_version") != DATASET or relationship.get("dataset_version") != DATASET):
                raise RetrievalError("Evidence identity/dataset mismatch")
            if props.get("source_table") != table or relationship.get("source_table") != table:
                raise RetrievalError("Evidence source table mismatch")
            if rel in {"HAS_SUBMITTED_CONDITION", "HAS_BROWSE_CONDITION"}:
                if props.get("source_kind") != ("submitted" if rel == "HAS_SUBMITTED_CONDITION" else "browse"):
                    raise RetrievalError("Submitted/browse condition classification mismatch")
            if rel == "HAS_PLANNED_OUTCOME":
                if (props.get("nct_id") != nct or props.get("source_record_id") != relationship.get("source_record_id")
                        or props.get("evidence_safeguard") != "Registered planned outcome — not a clinical result."):
                    raise RetrievalError("Registered outcome linkage/safeguard mismatch")
                source_ids = [relationship.get("source_record_id", "")]
            else:
                source_ids = relationship.get("source_record_ids", "").split(";")
            if not source_ids or any(not re.fullmatch(r"\d+", value) for value in source_ids):
                raise RetrievalError("Missing/invalid source-record identifiers")
            key = (nct, rel, entity_id)
            if key in seen:
                raise RetrievalError("Duplicate evidence path")
            seen.add(key)
            ordering.append(key)
            result.append({"evidence_id": "|".join(key), "nct_id": nct,
                           "category": category, "node_id": entity_id, "node_label": label,
                           "properties": props,
                           "relationship": {"type": rel, "start_id": nct, "end_id": entity_id,
                                            "properties": relationship},
                           "source_references": [{"source_table": table, "source_record_id": source_id,
                                                  "nct_id": nct} for source_id in source_ids],
                           "missing_fields": sorted(key for key, value in props.items() if value == "")})
        if ordering != sorted(ordering):
            raise RetrievalError("Evidence page ordering is not deterministic")
        return result

    @staticmethod
    def _coverage(counts, evidence, types):
        returned = Counter(row["relationship"]["type"] for row in evidence)
        return {EVIDENCE_SPECS[rel][0]: {
            "total": counts[rel], "returned": returned[rel],
            "source_status": "AVAILABLE" if counts[rel] else "NO_LINKED_RECORD_IN_PINNED_GRAPH",
            "all_evidence_returned": counts[rel] == returned[rel],
        } for rel in types}

    def trial_profile(self, trial_id, *, limit=50, offset=0):
        self._ready()
        nct = nct_id(trial_id)
        page_bounds(limit, offset)
        result = self._base("trial_profile")
        metadata = self._trials([nct])
        if not metadata:
            return {**result, "status": "NOT_FOUND", "nct_id": nct, "trial": None,
                    "evidence": [], "coverage": {}, "pagination": pagination(0, 0, limit, offset),
                    "reason": "NCT ID is not in the pinned cohort membership"}
        types = sorted(EVIDENCE_SPECS)
        counts = self._counts([nct], types)[nct]
        evidence = self._evidence([nct], types, limit, offset)
        page = pagination(sum(counts.values()), len(evidence), limit, offset)
        coverage = self._coverage(counts, evidence, types)
        return {**result, **metadata[nct], "nct_id": nct,
                "status": "COMPLETE" if all(counts.values()) and page["all_evidence_returned"] else "PARTIAL",
                "coverage": coverage, "pagination": page, "evidence": evidence}

    def search_trials(self, submitted_condition, intervention, *, limit=5, offset=0, evidence_limit=50):
        self._ready()
        page_bounds(limit, offset, MAX_TRIALS)
        page_bounds(evidence_limit, 0)
        normalized = []
        for value in (submitted_condition, intervention):
            if not isinstance(value, str) or not value.strip() or len(value) > 200:
                raise RetrievalError("Condition/intervention must be nonblank text of at most 200 characters")
            normalized.append(" ".join(unicodedata.normalize("NFKC", value).split()).casefold())
        parameters = {"dataset_version": DATASET, "condition_normalized": normalized[0],
                      "intervention_normalized": normalized[1]}
        counts = self._run(queries.SEARCH_COUNT, parameters, maximum=1)
        if len(counts) != 1 or type(counts[0]["total"]) is not int or not 0 <= counts[0]["total"] <= len(self.contract.membership):
            raise RetrievalError("Invalid search count")
        total = counts[0]["total"]
        rows = self._run(queries.SEARCH_PAGE, {**parameters, "limit": limit, "offset": offset}, maximum=limit)
        ids = [row["nct_id"] for row in rows]
        if ids != sorted(set(ids)) or not set(ids) <= self.contract.membership:
            raise RetrievalError("Search membership/order mismatch")
        page = pagination(total, len(ids), limit, offset)
        profiles = [self.trial_profile(nct, limit=evidence_limit) for nct in ids]
        complete = page["all_evidence_returned"] and all(p["status"] == "COMPLETE" for p in profiles)
        return {**self._base("trial_search"), "status": "NOT_FOUND" if total == 0 else "COMPLETE" if complete else "PARTIAL",
                "parameters": parameters, "matching_rule": "Exact normalized submitted condition AND intervention; no synonym expansion",
                "pagination": page, "trial_profiles": profiles,
                "coverage": {"matching_trials": total, "returned_trials": len(ids),
                             "all_matching_trial_pages_returned": page["all_evidence_returned"],
                             "all_returned_profiles_complete": all(p["status"] == "COMPLETE" for p in profiles)}}

    def compare_planned_outcomes(self, trial_ids, *, limit=50, offset=0):
        self._ready()
        page_bounds(limit, offset)
        if not isinstance(trial_ids, (list, tuple)) or not 1 <= len(trial_ids) <= MAX_TRIALS:
            raise RetrievalError(f"Explicit subset of 1–{MAX_TRIALS} NCT IDs required")
        ids = sorted(nct_id(value) for value in trial_ids)
        if len(ids) != len(set(ids)):
            raise RetrievalError("Duplicate trial IDs are not allowed")
        metadata = self._trials(ids)
        known, unknown = sorted(metadata), sorted(set(ids) - set(metadata))
        types = ["HAS_PLANNED_OUTCOME"]
        counts = self._counts(known, types)
        evidence = self._evidence(known, types, limit, offset)
        page = pagination(sum(row[types[0]] for row in counts.values()), len(evidence), limit, offset)
        trials = []
        for nct in ids:
            records = [row for row in evidence if row["nct_id"] == nct]
            if nct in unknown:
                trials.append({"nct_id": nct, "status": "NOT_FOUND", "trial": None, "coverage": {}, "evidence": []})
                continue
            coverage = self._coverage(counts[nct], records, types)
            total = counts[nct][types[0]]
            trials.append({**metadata[nct], "nct_id": nct, "status": "COMPLETE" if total > 0 and len(records) == total else "PARTIAL",
                           "coverage": coverage, "evidence": records})
        measures = defaultdict(set)
        for record in evidence:
            measures[record["properties"].get("measure", "")].add(record["nct_id"])
        # Compare only literal measure strings: no invented clinical equivalence.
        comparison = {"status": "COMPLETE_FOR_RETURNED_SCOPE" if page["all_evidence_returned"] else "DEFERRED_UNTIL_ALL_PAGES",
                      "method": "Exact case-sensitive registered measure strings; no clinical equivalence inferred",
                      "shared_exact_measures": [{"measure": measure, "nct_ids": sorted(ncts)}
                                                for measure, ncts in sorted(measures.items()) if measure and len(ncts) > 1]
                                               if page["all_evidence_returned"] else []}
        complete = page["all_evidence_returned"] and all(t["status"] == "COMPLETE" for t in trials)
        return {**self._base("planned_outcome_comparison"), "status": "NOT_FOUND" if not known else "COMPLETE" if complete else "PARTIAL",
                "selected_nct_ids": ids, "not_found_nct_ids": unknown, "pagination": page,
                "trials": trials, "evidence": evidence, "comparison": comparison}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow", choices=("profile", "search", "compare"))
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--nct-id")
    parser.add_argument("--nct-ids", nargs="+")
    parser.add_argument("--condition")
    parser.add_argument("--intervention")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--trial-limit", type=int, default=5)
    args = parser.parse_args(argv)
    with FullCohortRetriever(load_config(args.env_file)) as retriever:
        retriever.verify_connection()
        if args.workflow == "profile":
            result = retriever.trial_profile(args.nct_id, limit=args.limit, offset=args.offset)
        elif args.workflow == "search":
            result = retriever.search_trials(args.condition, args.intervention, limit=args.trial_limit,
                                             offset=args.offset, evidence_limit=args.limit)
        else:
            result = retriever.compare_planned_outcomes(args.nct_ids, limit=args.limit, offset=args.offset)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        text = str(exc) if isinstance(exc, RetrievalError) else f"Retrieval failed ({type(exc).__name__}); private details suppressed"
        print(text, file=sys.stderr)
        raise SystemExit(1) from None
