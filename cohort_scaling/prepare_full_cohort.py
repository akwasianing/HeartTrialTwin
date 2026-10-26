#!/usr/bin/env python3
"""Offline full-cohort graph preparation; streams the pinned local ZIP only.

Reuses the pilot's extraction, identity normalization, CSV schemas and field
policy. Importer modules supply definitions only; no Neo4j driver is created.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import resource
import sys
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import prepare_pilot as pilot
import import_pilot as schema


VERSION = "HTT-KG-AACT-20260905-FULL2824-v1"
OUTPUT = pilot.ROOT / "artifacts/cohort_scaling" / VERSION
ARCHIVE_SHA256 = "215365a46dd8119ef4bdee62cd11a08910c9be0855edf246b92f31cdcc2d1023"
DATASET = pilot.DATASET
SPECS = {
    "conditions.txt": ("ConditionTerm", "condition_id", "name", "submitted", "relationships_trial_submitted_condition.csv"),
    "browse_conditions.txt": ("ConditionTerm", "condition_id", "mesh_term", "browse", "relationships_trial_browse_condition.csv"),
    "interventions.txt": ("Intervention", "intervention_id", "name", None, "relationships_trial_intervention.csv"),
    "sponsors.txt": ("Sponsor", "sponsor_id", "name", None, "relationships_trial_sponsor.csv"),
}


def membership_ids():
    if pilot.digest(pilot.MEMBERSHIP) != pilot.MEMBERSHIP_SHA:
        raise RuntimeError("Frozen cohort SHA-256 mismatch")
    with pilot.MEMBERSHIP.open(newline="", encoding="utf-8") as handle:
        values = [row["nct_id"] for row in csv.DictReader(handle)]
    if len(values) != 2824 or len(set(values)) != 2824 or not all(re.fullmatch(r"NCT\d{8}", value) for value in values):
        raise RuntimeError("Expected the exact frozen 2,824 unique NCT IDs")
    return sorted(values)


def protected_files():
    hashes = pilot.protected_files()
    for path in sorted(pilot.OUTPUT.rglob("*")):
        if path.is_file() and not path.name.startswith(".env"):
            hashes[str(path.relative_to(pilot.ROOT))] = pilot.digest(path)
    # Protect the validated pilot preparation/import implementations too.
    for name in ("prepare_pilot.py", "import_pilot.py"):
        path = Path(__file__).with_name(name)
        hashes[str(path.relative_to(pilot.ROOT))] = pilot.digest(path)
    return hashes


def source_rows(out, table):
    with (out / "source_cache" / (Path(table).stem + ".jsonl")).open(encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def entity_identity(table, row, reused):
    label, id_field, name_field, kind, _ = SPECS[table]
    parts = [kind] if kind else [reused.normalized(row["intervention_type"] if label == "Intervention" else row["agency_class"])]
    parts.append(reused.normalized(row[name_field]))
    return reused.stable_id(id_field.removesuffix("_id"), *parts) if parts[-1] else reused.stable_id(id_field.removesuffix("_id"), table, row["id"])


def included_source(table, row, reused):
    return table != "sponsors.txt" or reused.normalized(row["lead_or_collaborator"]) == "lead"


def emit_graph(out, ids, sources, archive_identity, reused):
    """Same pilot graph rules, with full membership and no evidence caps."""
    nodes = {spec.label: [] for spec in schema.NODE_SPECS}
    edges = {spec.filename: [] for spec in schema.RELATIONSHIP_SPECS}
    shared = {"dataset_version": DATASET}
    studies = {row["nct_id"]: row for row in sources["studies.txt"]}
    for nct in ids:
        row = studies.get(nct, {})
        nodes["Trial"].append({
            "trial_id:ID(Trial)": nct, "nct_id": nct,
            **{field: row.get(field, "") for field in ("brief_title", "study_type", "phase")},
            "source_table": "studies.txt", "source_record_id": nct if row else "",
            "source_evidence_status": "PRESENT" if row else "MISSING_SOURCE_RECORD", **shared, ":LABEL": "Trial",
        })
    for table, (label, id_field, name_field, kind, filename) in SPECS.items():
        entities, linked_sources = {}, defaultdict(list)
        for row in sources[table]:
            if not included_source(table, row, reused):
                continue
            entity_id = entity_identity(table, row, reused)
            props = {
                f"{id_field}:ID({label})": entity_id, "name": row[name_field],
                "normalized_name": reused.normalized(row[name_field]), "source_table": table,
                **shared, ":LABEL": label,
            }
            if kind:
                props["source_kind"] = kind
            else:
                field = "intervention_type" if label == "Intervention" else "agency_class"
                props[field] = row[field]
            entities.setdefault(entity_id, props)
            linked_sources[(row["nct_id"], entity_id)].append(row["id"])
        nodes[label].extend(entities.values())
        spec = next(item for item in schema.RELATIONSHIP_SPECS if item.filename == filename)
        edges[filename] = [{
            spec.start_header: nct, spec.end_header: entity_id, "source_table": table,
            "source_record_ids": ";".join(sorted(source_ids, key=reused.intish)),
            **shared, ":TYPE": spec.relationship_type,
        } for (nct, entity_id), source_ids in sorted(linked_sources.items())]
    for row in sources["design_outcomes.txt"]:
        outcome_id = "planned_outcome:" + row["id"]
        nodes["PlannedOutcome"].append({
            "planned_outcome_id:ID(PlannedOutcome)": outcome_id, "source_record_id": row["id"],
            **{field: row[field] for field in ("nct_id", "outcome_type", "measure", "time_frame", "population", "description")},
            "source_table": "design_outcomes.txt", "evidence_safeguard": pilot.SAFEGUARD,
            **shared, ":LABEL": "PlannedOutcome",
        })
        edges["relationships_trial_planned_outcome.csv"].append({
            ":START_ID(Trial)": row["nct_id"], ":END_ID(PlannedOutcome)": outcome_id,
            "source_table": "design_outcomes.txt", "source_record_id": row["id"],
            **shared, ":TYPE": "HAS_PLANNED_OUTCOME",
        })
    nodes["SourceDataset"] = [{
        "source_dataset_id:ID(SourceDataset)": DATASET, **shared, "graph_version": VERSION,
        "snapshot_date": "2026-09-05", "snapshot_file": "20260905_export_ctgov.zip",
        "snapshot_url": reused.SNAPSHOT_URL, "archive_md5": archive_identity["md5"],
        "archive_sha256": archive_identity["sha256"], "pinned_manifest_sha256": pilot.MEMBERSHIP_SHA,
        ":LABEL": "SourceDataset",
    }]
    for spec in schema.NODE_SPECS:
        rows = sorted(nodes[spec.label], key=lambda row: row[spec.id_header])
        pilot.write_csv(out / spec.filename, spec.header, rows)
        if spec.label == "SourceDataset":
            continue
        relationship = next(item for item in schema.RELATIONSHIP_SPECS if item.start_label == spec.label and item.end_label == "SourceDataset")
        edges[relationship.filename] = [{
            relationship.start_header: row[spec.id_header], relationship.end_header: DATASET,
            **shared, ":TYPE": relationship.relationship_type,
        } for row in rows]
    for spec in schema.RELATIONSHIP_SPECS:
        pilot.write_csv(out / spec.filename, spec.header, edges[spec.filename])


def validate_graph(out):
    ids = membership_ids()
    membership = pilot.read_csv(out / "cohort_membership.csv")
    if [row["nct_id"] for row in membership] != ids or any(row["graph_version"] != VERSION or row["dataset_version"] != DATASET for row in membership):
        raise RuntimeError("Full cohort membership/provenance mismatch")
    checks = {"exact_2824_unique_frozen_membership": True}
    nodes, counts, adjacency, all_nodes = {}, {}, defaultdict(set), set()
    for spec in schema.NODE_SPECS:
        rows = schema.reference.read_csv(out / spec.filename, spec.header)
        pilot.assert_safe_fields(rows)
        keys = [row[spec.id_header] for row in rows]
        if any(not value for value in keys) or len(keys) != len(set(keys)):
            raise RuntimeError(f"Duplicate/missing node ID: {spec.label}")
        if any(row[":LABEL"] != spec.label or row["dataset_version"] != DATASET for row in rows):
            raise RuntimeError("Node label/dataset mismatch")
        nodes[spec.label] = {row[spec.id_header]: row for row in rows}
        counts[spec.label] = len(rows)
        all_nodes.update((spec.label, key) for key in keys)
    if set(nodes["Trial"]) != set(ids) or set(nodes["SourceDataset"]) != {DATASET}:
        raise RuntimeError("Trial/source membership mismatch")
    source = nodes["SourceDataset"][DATASET]
    if any(source[field] != expected for field, expected in {
        "graph_version": VERSION, "snapshot_date": "2026-09-05", "archive_md5": pilot.EXPECTED_MD5,
        "archive_sha256": ARCHIVE_SHA256, "pinned_manifest_sha256": pilot.MEMBERSHIP_SHA,
        "snapshot_file": "20260905_export_ctgov.zip", "snapshot_url": pilot.load_reused_logic().SNAPSHOT_URL,
    }.items()):
        raise RuntimeError("SourceDataset provenance mismatch")
    rel_counts, triples, edges = Counter(), set(), {}
    for spec in schema.RELATIONSHIP_SPECS:
        rows = schema.reference.read_csv(out / spec.filename, spec.header)
        pilot.assert_safe_fields(rows)
        for row in rows:
            start, end = row[spec.start_header], row[spec.end_header]
            key = (spec.start_label, start, spec.relationship_type, spec.end_label, end)
            if start not in nodes[spec.start_label] or end not in nodes[spec.end_label]:
                raise RuntimeError("Invalid relationship endpoint")
            if key in triples or row[":TYPE"] != spec.relationship_type or row["dataset_version"] != DATASET:
                raise RuntimeError("Duplicate relationship/type/provenance mismatch")
            triples.add(key)
            adjacency[(spec.start_label, start)].add((spec.end_label, end))
            adjacency[(spec.end_label, end)].add((spec.start_label, start))
        rel_counts[spec.relationship_type] += len(rows)
        edges[spec.filename] = rows
    reached, pending = set(), [("SourceDataset", DATASET)]
    while pending:
        value = pending.pop()
        if value not in reached:
            reached.add(value)
            pending.extend(adjacency[value] - reached)
    if reached != all_nodes:
        raise RuntimeError("Nodes disconnected from dataset provenance")
    checks.update({"unique_node_ids": True, "unique_relationship_triples": True, "valid_endpoints_and_versions": True, "connected_via_provenance": True})
    coverage = pilot.read_csv(out / "source_coverage.csv")
    coverage_index = {(row["nct_id"], row["source_table"]): row for row in coverage}
    if len(coverage_index) != len(coverage) or len(coverage) != len(ids) * len(pilot.SOURCE_COLUMNS):
        raise RuntimeError("Coverage grid incomplete/duplicated")
    reused = pilot.load_reused_logic()
    source_counts, missing_ids, missing_fields = {}, {}, {}
    for table, columns in pilot.SOURCE_COLUMNS.items():
        raw = list(source_rows(out, table))
        pilot.assert_safe_fields(raw)
        keys = [row.get("id", row["nct_id"]) for row in raw]
        if len(keys) != len(set(keys)) or any(not key for key in keys) or any(set(row) != set(columns) or row["nct_id"] not in nodes["Trial"] for row in raw):
            raise RuntimeError("Safe source-cache schema/IDs mismatch")
        grouped = reused.rows_by_trial(raw)
        source_counts[table] = len(raw)
        missing_ids[table] = sorted(set(ids) - set(grouped))
        missing_fields[table] = {field: sum(not row[field].strip() for row in raw) for field in columns if field not in {"id", "nct_id"}}
        for nct in ids:
            records = grouped.get(nct, [])
            entry = coverage_index[(nct, table)]
            expected_fields = {field: sum(not row[field].strip() for row in records) for field in columns if field not in {"id", "nct_id"}}
            if int(entry["source_record_count"]) != len(records) or json.loads(entry["missing_field_counts_json"]) != expected_fields or (entry["evidence_status"] == "PRESENT") != bool(records):
                raise RuntimeError("Missing-evidence coverage differs from cache")
            if table == "sponsors.txt" and int(entry["lead_sponsor_count"]) != sum(included_source(table, row, reused) for row in records):
                raise RuntimeError("Lead sponsor coverage mismatch")
        if table in SPECS:
            label, _, name_field, _, filename = SPECS[table]
            expected_pairs = Counter((row["nct_id"], row["id"]) for row in raw if included_source(table, row, reused))
            actual_pairs = Counter((row[":START_ID(Trial)"], source_id) for row in edges[filename] for source_id in row["source_record_ids"].split(";"))
            if expected_pairs != actual_pairs:
                raise RuntimeError("Available source rows dropped or repeated in graph links")
            by_id = {row["id"]: row for row in raw}
            spec = next(item for item in schema.RELATIONSHIP_SPECS if item.filename == filename)
            for relationship in edges[filename]:
                entity_id = relationship[spec.end_header]
                entity = nodes[label][entity_id]
                for source_id in relationship["source_record_ids"].split(";"):
                    original = by_id[source_id]
                    if entity_identity(table, original, reused) != entity_id or reused.normalized(entity["name"]) != reused.normalized(original[name_field]) or relationship["source_table"] != table:
                        raise RuntimeError("Source-record/entity association mismatch")
        elif table == "design_outcomes.txt":
            outcomes = nodes["PlannedOutcome"]
            if set(outcomes) != {"planned_outcome:" + row["id"] for row in raw}:
                raise RuntimeError("Planned outcomes dropped or fabricated")
            for row in raw:
                item = outcomes["planned_outcome:" + row["id"]]
                if item["source_record_id"] != row["id"] or item["evidence_safeguard"] != pilot.SAFEGUARD or item["source_table"] != table or any(item[field] != row[field] for field in columns if field != "id"):
                    raise RuntimeError("Planned-outcome values/provenance changed")
            relationships = edges["relationships_trial_planned_outcome.csv"]
            if {(row[":START_ID(Trial)"], row["source_record_id"], row[":END_ID(PlannedOutcome)"]) for row in relationships} != {(row["nct_id"], row["id"], "planned_outcome:" + row["id"]) for row in raw}:
                raise RuntimeError("Planned-outcome relationship provenance mismatch")
        else:
            by_id = {row["nct_id"]: row for row in raw}
            for nct, node in nodes["Trial"].items():
                original = by_id.get(nct, {})
                if node["nct_id"] != nct or any(node[field] != original.get(field, "") for field in ("brief_title", "study_type", "phase")) or (node["source_evidence_status"] == "PRESENT") != bool(original):
                    raise RuntimeError("Trial values/source coverage mismatch")
    checks.update({"all_available_source_records_linked": True, "all_outcomes_preserved_without_cap": True, "outcome_values_and_source_ids_exact": True, "missing_evidence_and_fields_verified": True, "prohibited_fields_excluded": True})
    return {"checks": checks, "node_counts": counts, "relationship_counts": dict(sorted(rel_counts.items())), "total_nodes": sum(counts.values()), "total_relationships": len(triples), "source_record_counts": source_counts, "source_missing_trial_ids": missing_ids, "source_missing_field_counts": missing_fields}


def validate_saved(out=OUTPUT):
    manifest = json.loads((out / "full_cohort_manifest.json").read_text())
    if manifest["graph_version"] != VERSION or manifest["authoritative_dataset_version"] != DATASET:
        raise RuntimeError("Unexpected full-cohort manifest version")
    for name, expected in manifest["files_sha256"].items():
        if pilot.digest(out / name) != expected:
            raise RuntimeError(f"Output checksum mismatch: {name}")
    for line in (out / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        if pilot.digest(out / name) != expected:
            raise RuntimeError(f"SHA256SUMS mismatch: {name}")
    for name, expected in manifest["protected_source_hashes"].items():
        if pilot.digest(pilot.ROOT / name) != expected:
            raise RuntimeError(f"Protected baseline changed: {name}")
    result = validate_graph(out)
    if result != manifest["validation"]:
        raise RuntimeError("Full-cohort manifest validation results differ from saved data")
    return result


def prepare(archive_path, out=OUTPUT):
    if out.exists():
        raise RuntimeError("Output directory already exists; refusing overwrite")
    started = time.perf_counter()
    protected = protected_files()
    ids = membership_ids()  # All frozen IDs; no coverage/label/outcome selection.
    reused = pilot.load_reused_logic()
    if archive_path.stat().st_size != reused.EXPECTED_ARCHIVE_SIZE:
        raise RuntimeError("Pinned archive size mismatch")
    md5, sha = hashlib.md5(), hashlib.sha256()
    with archive_path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            md5.update(block); sha.update(block)
    if md5.hexdigest() != pilot.EXPECTED_MD5 or sha.hexdigest() != ARCHIVE_SHA256:
        raise RuntimeError("Pinned archive MD5/SHA-256 mismatch")
    archive_identity = {"filename": "20260905_export_ctgov.zip", "size_bytes": archive_path.stat().st_size, "md5": md5.hexdigest(), "sha256": sha.hexdigest(), "source_url": reused.SNAPSHOT_URL}
    print("Archive size, MD5 and SHA-256 verified; retaining all 2,824 frozen IDs", flush=True)
    step2 = json.loads((pilot.ROOT / "step2_reconciliation/HeartTrialTwin_step2_reconciliation_audit.json").read_text())
    sources, audit = {}, {}
    with zipfile.ZipFile(archive_path) as archive:
        for table in pilot.SOURCE_COLUMNS:
            if table in reused.EXPECTED_TABLES:
                rows, metadata = reused.scan_member(archive, table, set(ids))
                sources[table] = [{field: row[field] for field in pilot.SOURCE_COLUMNS[table]} for row in rows]
                del rows
            else:
                sources[table], metadata = pilot.scan_additional_member(archive, table, set(ids), step2["source"]["entries"][table])
            audit[table] = metadata
            rows = sources[table]
            source_ids = [row.get("id", row["nct_id"]) for row in rows]
            if len(source_ids) != len(set(source_ids)) or any(not value for value in source_ids):
                raise RuntimeError("Missing/duplicate source identifiers")
            rows.sort(key=lambda row: (row["nct_id"], reused.intish(row.get("id", ""))))
            print(f"{table}: {len(rows)} rows, {metadata['cohort_nct_coverage']}/2824 trials, CRC passed", flush=True)
    out.mkdir(parents=True)
    (out / "source_cache").mkdir()
    for table, rows in sources.items():
        pilot.assert_safe_fields(rows)
        with (out / "source_cache" / (Path(table).stem + ".jsonl")).open("x", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    pilot.write_csv(out / "cohort_membership.csv", ("nct_id", "dataset_version", "graph_version"), [{"nct_id": nct, "dataset_version": DATASET, "graph_version": VERSION} for nct in ids])
    emit_graph(out, ids, sources, archive_identity, reused)
    coverage = []
    for table, rows in sources.items():
        grouped = reused.rows_by_trial(rows)
        for nct in ids:
            records = grouped.get(nct, [])
            missing = {field: sum(not row[field].strip() for row in records) for field in pilot.SOURCE_COLUMNS[table] if field not in {"id", "nct_id"}}
            coverage.append({"nct_id": nct, "source_table": table, "source_record_count": len(records), "evidence_status": "PRESENT" if records else "NO_SOURCE_RECORD_FOUND_IN_PINNED_SNAPSHOT", "missing_field_counts_json": json.dumps(missing, sort_keys=True), "lead_sponsor_count": sum(included_source(table, row, reused) for row in records) if table == "sponsors.txt" else ""})
    pilot.write_csv(out / "source_coverage.csv", ("nct_id", "source_table", "source_record_count", "evidence_status", "missing_field_counts_json", "lead_sponsor_count"), coverage)
    del sources, coverage, grouped, rows, records
    validation = validate_graph(out)
    if protected != protected_files():
        raise RuntimeError("Protected five-trial/pilot artifacts changed")
    limitations = [
        "The frozen 2,824-trial membership is restricted to observed terminal outcomes; this is not all registered HF trials.",
        "Snapshot values may contain later amendments and are not asserted to be initial-registration predictors.",
        "Registered planned outcomes are planned measures, not observed clinical results.",
        "Missing fields stay blank; absent rows mean no record found in this pinned table, not proof no evidence ever existed.",
        "Only lead sponsors become graph relationships; collaborator rows remain in the safe source cache.",
        "Conservative normalization merges equivalent names/types; exact per-row values remain cached with original source IDs.",
        "Connectivity is through provenance links and does not assert clinical similarity among all trials.",
        "The five-trial and 50-trial importers/retrievers remain unchanged and cannot ingest this version without separate configuration.",
    ]
    coverage_lines = [f"# {VERSION} source coverage", "", "All 2,824 frozen IDs included; no source-availability filter. Snapshot: 2026-09-05.", "", "| Source table | Rows | Trials covered | Trials without rows |", "|---|---:|---:|---:|"]
    coverage_lines += [f"| {table} | {validation['source_record_counts'][table]} | {2824-len(validation['source_missing_trial_ids'][table])} | {len(validation['source_missing_trial_ids'][table])} |" for table in pilot.SOURCE_COLUMNS]
    coverage_lines += ["", "Per-trial gaps and blank-field counts are preserved in source_coverage.csv; all missing IDs and field totals are also in full_cohort_manifest.json.", "", "## Blank-field totals", ""]
    coverage_lines += [f"- {table}: " + ", ".join(f"{field}={count}" for field, count in values.items() if count) for table, values in validation["source_missing_field_counts"].items() if any(values.values())]
    (out / "COVERAGE_REPORT.md").write_text("\n".join(coverage_lines) + "\n", encoding="utf-8")
    lines = [f"# {VERSION} local validation", "", f"Dataset: {DATASET}; snapshot: 2026-09-05. All frozen IDs included in lexical order.", "", "## Node counts", ""]
    lines += [f"- {key}: {value}" for key, value in validation["node_counts"].items()]
    lines += [f"- Total: {validation['total_nodes']}", "", "## Relationship counts", ""]
    lines += [f"- {key}: {value}" for key, value in validation["relationship_counts"].items()]
    lines += [f"- Total: {validation['total_relationships']}", "", "## Checks", ""]
    lines += [f"- PASS — {name}" for name in validation["checks"]]
    lines += ["- PASS — archive size, MD5, SHA-256 and all six fully streamed ZIP member CRCs.", "- PASS — five-trial and 50-trial protected artifacts unchanged.", "", "## Limitations", ""] + ["- " + item for item in limitations]
    (out / "VALIDATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    manifest = {
        "schema_version": "HTT-FULL-COHORT-GRAPH-v1", "graph_version": VERSION,
        "authoritative_dataset_version": DATASET, "snapshot_date": "2026-09-05",
        "created_utc": datetime.now(timezone.utc).isoformat(), "membership": {"rule": "All frozen NCT IDs in ascending lexical order; no evidence/label filters", "count": len(ids), "path": "cohort_membership.csv", "frozen_source": str(pilot.MEMBERSHIP.relative_to(pilot.ROOT)), "frozen_source_sha256": pilot.MEMBERSHIP_SHA},
        "archive": {**archive_identity, "tables": audit}, "validation": validation,
        "feature_policy": {"source_columns": pilot.SOURCE_COLUMNS, "prohibited_columns": sorted(pilot.PROHIBITED), "planned_outcome_cap": None},
        "protected_source_hashes": protected,
        "code_sha256": {str(path.relative_to(pilot.ROOT)): pilot.digest(path) for path in (Path(__file__).resolve(), Path(pilot.__file__).resolve(), Path(schema.__file__).resolve(), pilot.ROOT / "artifacts/knowledge_graph/prepare_neo4j_import.py")},
        "runtime_seconds": round(time.perf_counter()-started, 3), "peak_process_rss_mib": round(peak / (1024**2 if sys.platform == "darwin" else 1024), 2),
        "limitations": limitations,
        "files_sha256": {str(path.relative_to(out)): pilot.digest(path) for path in sorted(out.rglob("*")) if path.is_file()},
    }
    (out / "full_cohort_manifest.json").write_text(json.dumps(manifest, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "SHA256SUMS").write_text("".join(f"{pilot.digest(path)}  {path.relative_to(out).as_posix()}\n" for path in sorted(out.rglob("*")) if path.is_file()), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if not args.validate_only:
        if args.archive is None:
            parser.error("--archive required for preparation")
        prepare(args.archive.resolve())
    result = validate_saved()
    print(json.dumps({"output_directory": str(OUTPUT), "node_counts": result["node_counts"], "relationship_counts": result["relationship_counts"], "total_nodes": result["total_nodes"], "total_relationships": result["total_relationships"], "source_record_counts": result["source_record_counts"], "missing_trial_counts": {key: len(values) for key, values in result["source_missing_trial_ids"].items()}, "checks": result["checks"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
