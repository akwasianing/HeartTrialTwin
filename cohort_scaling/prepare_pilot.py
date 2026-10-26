#!/usr/bin/env python3
"""Prepare/validate an isolated pilot from the local pinned AACT ZIP. No network.

Run: .venv-graphrag/bin/python cohort_scaling/prepare_pilot.py --archive PATH
Validate saved outputs: same command with --validate-only (no archive required).
The versioned output directory must not exist when preparing a new pilot.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import re
import time
import zipfile
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "HTT-KG-AACT-20260905-PILOT50-v1"
DATASET = "HTT-P1-AACT-20260905"
SEED = DATASET + "|pilot50-v1|"
OUTPUT = ROOT / "artifacts" / "cohort_scaling" / VERSION
MEMBERSHIP = ROOT / "step3_manifest" / "HeartTrialTwin_first_p1_cohort_manifest_HTT-P1-AACT-20260905.csv"
MEMBERSHIP_SHA = "5a2d6bbb0973a45988275efb4e9caff8400438edf4e3c560b1b7c0b1688fe7ab"
EXPECTED_MD5 = "99e62b3f8ae5838b36bc0c2277ad2714"
SAFEGUARD = "Registered planned outcome — not a clinical result."
SOURCE_COLUMNS = {
    "studies.txt": ["nct_id", "brief_title", "study_type", "phase"],
    "conditions.txt": ["id", "nct_id", "name"],
    "browse_conditions.txt": ["id", "nct_id", "mesh_term", "mesh_type"],
    "interventions.txt": ["id", "nct_id", "intervention_type", "name", "description"],
    "sponsors.txt": ["id", "nct_id", "agency_class", "lead_or_collaborator", "name"],
    "design_outcomes.txt": ["id", "nct_id", "outcome_type", "measure", "time_frame", "population", "description"],
}
PROHIBITED = {
    "enrollment", "enrollment_type", "overall_status", "terminal_status", "why_stopped",
    "termination_reason", "discontinued", "prediction", "prediction_score", "temporal_group",
    "submission_year", "start_date", "completion_date", "primary_completion_date",
    "study_first_submitted_date", "results_first_submitted_date",
}


def digest(path, algorithm="sha256"):
    result = hashlib.new(algorithm)
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def load_reused_logic():
    path = ROOT / "artifacts/knowledge_graph/prepare_neo4j_import.py"
    spec = importlib.util.spec_from_file_location("pinned_kg_preparation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def select_ids():
    if digest(MEMBERSHIP) != MEMBERSHIP_SHA:
        raise RuntimeError("Frozen membership SHA-256 mismatch")
    with MEMBERSHIP.open(newline="", encoding="utf-8") as handle:
        ids = [row["nct_id"] for row in csv.DictReader(handle)]
    if len(ids) != 2824 or len(set(ids)) != 2824 or not all(re.fullmatch(r"NCT\d{8}", value) for value in ids):
        raise RuntimeError("Frozen membership must contain exactly 2,824 unique valid IDs")
    return sorted(ids, key=lambda value: (hashlib.sha256((SEED + value).encode()).hexdigest(), value))[:50]


def write_csv(path, fields, rows):
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def protected_files():
    paths = [MEMBERSHIP]
    baseline = ROOT / "artifacts/knowledge_graph"
    paths.extend(p for p in baseline.iterdir() if p.suffix in {".csv", ".json", ".md", ".py"})
    for name in ("trial_documents.jsonl", "document_manifest.json", "index_manifest.json"):
        path = ROOT / "vector_rag/data" / name
        if path.is_file():
            paths.append(path)
    return {str(path.relative_to(ROOT)): digest(path) for path in sorted(paths)}


def scan_additional_member(archive, table, ids, expected):
    info = archive.getinfo(table)
    if f"{info.CRC:08x}" != expected["crc32"] or info.file_size != expected["uncompressed_bytes"]:
        raise RuntimeError(f"Pinned ZIP member identity mismatch: {table}")
    matched, total = [], 0
    csv.field_size_limit(100_000_000)
    with archive.open(info) as binary, io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as text:
        reader = csv.DictReader(text, delimiter="|")
        header = reader.fieldnames or []
        if not set(SOURCE_COLUMNS[table]).issubset(header):
            raise RuntimeError(f"Required source columns missing: {table}")
        for row in reader:
            total += 1
            if row["nct_id"] in ids:
                matched.append({field: row[field] for field in SOURCE_COLUMNS[table]})
    return matched, {
        "zip_member": info.filename, "header": header, "crc32": f"{info.CRC:08x}",
        "compressed_bytes": info.compress_size, "uncompressed_bytes": info.file_size,
        "total_rows": total, "cohort_rows": len(matched),
        "cohort_nct_coverage": len({row["nct_id"] for row in matched}),
        "crc_verified_by_full_member_read": True,
    }


def assert_safe_fields(rows):
    for row in rows:
        if set(row) & PROHIBITED:
            raise RuntimeError("Prohibited evidence columns detected")


def validate_graph(out):
    membership = read_csv(out / "pilot_membership.csv")
    ids = [row["nct_id"] for row in membership]
    checks = {"exactly_50_unique_pinned_trials": len(ids) == len(set(ids)) == 50 and ids == select_ids()}
    node_ids, node_counts, relationship_counts = {}, {}, Counter()
    adjacency, relationships = defaultdict(set), set()
    for path in sorted(out.glob("nodes_*.csv")):
        rows = read_csv(path)
        assert_safe_fields(rows)
        with path.open(newline="") as handle:
            header = next(csv.reader(handle))
        column = next(field for field in header if ":ID(" in field)
        label = column.split(":ID(")[1].rstrip(")")
        values = [row[column] for row in rows]
        if len(values) != len(set(values)) or any(not value for value in values):
            raise RuntimeError(f"Missing/duplicate node identifiers: {label}")
        if any(row["dataset_version"] != DATASET or row[":LABEL"] != label for row in rows):
            raise RuntimeError(f"Node provenance or label mismatch: {label}")
        node_ids[label] = set(values)
        node_counts[label] = len(rows)
    checks["trial_membership_exact"] = node_ids["Trial"] == set(ids)
    for path in sorted(out.glob("relationships_*.csv")):
        rows = read_csv(path)
        assert_safe_fields(rows)
        with path.open(newline="") as handle:
            header = next(csv.reader(handle))
        start_col = next(field for field in header if field.startswith(":START_ID"))
        end_col = next(field for field in header if field.startswith(":END_ID"))
        start_label, end_label = start_col.split("(")[1].rstrip(")"), end_col.split("(")[1].rstrip(")")
        for row in rows:
            start, end, kind = row[start_col], row[end_col], row[":TYPE"]
            if start not in node_ids[start_label] or end not in node_ids[end_label]:
                raise RuntimeError(f"Missing relationship endpoint: {path.name}")
            key = (start_label, start, kind, end_label, end)
            if key in relationships or row["dataset_version"] != DATASET:
                raise RuntimeError("Duplicate relationship or provenance mismatch")
            relationships.add(key)
            relationship_counts[kind] += 1
            adjacency[(start_label, start)].add((end_label, end))
            adjacency[(end_label, end)].add((start_label, start))
    reached, queue = set(), deque([("SourceDataset", DATASET)])
    while queue:
        value = queue.popleft()
        if value not in reached:
            reached.add(value)
            queue.extend(adjacency[value] - reached)
    checks["all_nodes_connected_via_provenance"] = len(reached) == sum(node_counts.values())
    raw_outcomes = [json.loads(line) for line in (out / "source_cache/design_outcomes.jsonl").read_text().splitlines()]
    outcomes = read_csv(out / "nodes_planned_outcome.csv")
    by_id = {row["source_record_id"]: row for row in outcomes}
    checks["all_available_outcomes_preserved_without_cap"] = len(outcomes) == len(raw_outcomes) and all(
        source["id"] in by_id and all(by_id[source["id"]][field] == source[field] for field in ("nct_id", "outcome_type", "measure", "time_frame", "population", "description"))
        for source in raw_outcomes
    )
    checks["planned_outcomes_labeled"] = all(row["evidence_safeguard"] == SAFEGUARD for row in outcomes)
    checks["every_outcome_has_exact_trial_link"] = {
        (row[":START_ID(Trial)"], row[":END_ID(PlannedOutcome)"])
        for row in read_csv(out / "relationships_trial_planned_outcome.csv")
    } == {(row["nct_id"], row["planned_outcome_id:ID(PlannedOutcome)"]) for row in outcomes}
    checks["node_ids_unique_and_relationship_endpoints_valid"] = True
    checks["relationship_triples_unique"] = True
    checks["prohibited_structured_fields_excluded"] = True
    checks["frozen_manifest_hash_verified"] = digest(MEMBERSHIP) == MEMBERSHIP_SHA
    if not all(checks.values()):
        raise RuntimeError(f"Pilot validation failed: {checks}")
    return {"checks": checks, "node_counts": node_counts, "relationship_counts": dict(sorted(relationship_counts.items())), "total_nodes": sum(node_counts.values()), "total_relationships": len(relationships)}


def prepare(archive_path, out):
    started = time.perf_counter()
    if out.exists():
        raise RuntimeError("Pilot directory already exists; use --validate-only or a new version, never overwrite")
    baseline_hashes = protected_files()
    selected = select_ids()  # Selection precedes and is independent of source coverage.
    ids = set(selected)
    reused = load_reused_logic()
    if archive_path.stat().st_size != reused.EXPECTED_ARCHIVE_SIZE:
        raise RuntimeError("Pinned archive size mismatch")
    md5, sha = hashlib.md5(), hashlib.sha256()
    with archive_path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            md5.update(block)
            sha.update(block)
    if md5.hexdigest() != EXPECTED_MD5:
        raise RuntimeError("Pinned archive MD5 mismatch")
    print("Archive size/MD5 verified; streaming six source members for the fixed 50 IDs", flush=True)
    step2 = json.loads((ROOT / "step2_reconciliation/HeartTrialTwin_step2_reconciliation_audit.json").read_text())
    sources, table_audit = {}, {}
    with zipfile.ZipFile(archive_path) as archive:
        for table in SOURCE_COLUMNS:
            if table in reused.EXPECTED_TABLES:
                rows, audit = reused.scan_member(archive, table, ids)
                sources[table] = [{field: row[field] for field in SOURCE_COLUMNS[table]} for row in rows]
            else:
                sources[table], audit = scan_additional_member(archive, table, ids, step2["source"]["entries"][table])
            table_audit[table] = audit
            keys = [row.get("id", row["nct_id"]) for row in sources[table]]
            if any(not key for key in keys) or len(keys) != len(set(keys)):
                raise RuntimeError(f"Missing/duplicate source record identifiers: {table}")
            sources[table].sort(key=lambda row: (row["nct_id"], reused.intish(row.get("id", ""))))
            print(f"{table}: {len(sources[table])} source rows / {audit['cohort_nct_coverage']} pilot trials; CRC passed", flush=True)
    out.mkdir(parents=True)
    (out / "source_cache").mkdir()
    for table, rows in sources.items():
        assert_safe_fields(rows)
        with (out / "source_cache" / (Path(table).stem + ".jsonl")).open("x", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    write_csv(out / "pilot_membership.csv", ["selection_rank", "nct_id", "selection_sha256", "dataset_version", "graph_version"], [
        {"selection_rank": rank, "nct_id": nct, "selection_sha256": hashlib.sha256((SEED + nct).encode()).hexdigest(), "dataset_version": DATASET, "graph_version": VERSION}
        for rank, nct in enumerate(selected, 1)
    ])
    grouped = {table: reused.rows_by_trial(rows) for table, rows in sources.items()}
    shared = {"dataset_version": DATASET}
    nodes, edges = {}, {}
    trial_fields = ["trial_id:ID(Trial)", "nct_id", "brief_title", "study_type", "phase", "source_table", "source_record_id", "source_evidence_status", "dataset_version", ":LABEL"]
    trials = []
    for nct in sorted(ids):
        row = next(iter(grouped["studies.txt"].get(nct, [])), {})
        trials.append({"trial_id:ID(Trial)": nct, "nct_id": nct, **{field: row.get(field, "") for field in ("brief_title", "study_type", "phase")}, "source_table": "studies.txt", "source_record_id": nct if row else "", "source_evidence_status": "PRESENT" if row else "MISSING_SOURCE_RECORD", **shared, ":LABEL": "Trial"})
    nodes["Trial"] = ("trial", "trial_id", trial_fields, trials)

    # Reuse conservative identities; all available entities are retained, including singletons.
    specs = [
        ("conditions.txt", "ConditionTerm", "condition_term", "condition_id", "name", ["submitted"]),
        ("browse_conditions.txt", "ConditionTerm", "condition_term", "condition_id", "mesh_term", ["browse"]),
        ("interventions.txt", "Intervention", "intervention", "intervention_id", "name", []),
        ("sponsors.txt", "Sponsor", "sponsor", "sponsor_id", "name", []),
    ]
    for table, label, filename, id_field, name_field, prefix in specs:
        entity_map, rel_map = {}, defaultdict(list)
        for row in sources[table]:
            if label == "Sponsor" and reused.normalized(row["lead_or_collaborator"]) != "lead":
                continue
            extra = [reused.normalized(row["intervention_type"])] if label == "Intervention" else [reused.normalized(row["agency_class"])] if label == "Sponsor" else prefix
            parts = [*extra, reused.normalized(row[name_field])]
            entity_id = reused.stable_id(id_field.removesuffix("_id"), *parts) if parts[-1] else reused.stable_id(id_field.removesuffix("_id"), table, row["id"])
            id_header = f"{id_field}:ID({label})"
            item = {id_header: entity_id, "name": row[name_field], "normalized_name": reused.normalized(row[name_field]), "source_table": table, **shared, ":LABEL": label}
            if label == "ConditionTerm":
                item["source_kind"] = prefix[0]
            elif label == "Intervention":
                item["intervention_type"] = row["intervention_type"]
            else:
                item["agency_class"] = row["agency_class"]
            entity_map.setdefault(entity_id, item)
            rel_map[(row["nct_id"], entity_id)].append(row["id"])
        rel_kind = {"conditions.txt": "HAS_SUBMITTED_CONDITION", "browse_conditions.txt": "HAS_BROWSE_CONDITION", "interventions.txt": "HAS_INTERVENTION", "sponsors.txt": "LEAD_SPONSORED_BY"}[table]
        suffix = {"conditions.txt": "submitted_condition", "browse_conditions.txt": "browse_condition", "interventions.txt": "intervention", "sponsors.txt": "sponsor"}[table]
        rel_fields = [":START_ID(Trial)", f":END_ID({label})", "source_table", "source_record_ids", "dataset_version", ":TYPE"]
        edges[f"trial_{suffix}"] = (rel_fields, [{":START_ID(Trial)": nct, f":END_ID({label})": target, "source_table": table, "source_record_ids": ";".join(sorted(source_ids, key=reused.intish)), **shared, ":TYPE": rel_kind} for (nct, target), source_ids in sorted(rel_map.items())])
        if label == "ConditionTerm":
            fields = [id_header, "name", "normalized_name", "source_table", "dataset_version", ":LABEL", "source_kind"]
        elif label == "Intervention":
            fields = [id_header, "name", "normalized_name", "source_table", "dataset_version", ":LABEL", "intervention_type"]
        else:
            fields = [id_header, "name", "normalized_name", "source_table", "dataset_version", ":LABEL", "agency_class"]
        if label in nodes:
            nodes[label][3].extend(entity_map.values())
        else:
            nodes[label] = (filename, id_field, fields, list(entity_map.values()))
    outcome_fields = ["planned_outcome_id:ID(PlannedOutcome)", "source_record_id", "nct_id", "outcome_type", "measure", "time_frame", "population", "description", "source_table", "evidence_safeguard", "dataset_version", ":LABEL"]
    outcomes = [{"planned_outcome_id:ID(PlannedOutcome)": "planned_outcome:" + row["id"], "source_record_id": row["id"], **{field: row[field] for field in ("nct_id", "outcome_type", "measure", "time_frame", "population", "description")}, "source_table": "design_outcomes.txt", "evidence_safeguard": SAFEGUARD, **shared, ":LABEL": "PlannedOutcome"} for row in sources["design_outcomes.txt"]]
    nodes["PlannedOutcome"] = ("planned_outcome", "planned_outcome_id", outcome_fields, outcomes)
    edges["trial_planned_outcome"] = ([":START_ID(Trial)", ":END_ID(PlannedOutcome)", "source_table", "source_record_id", "dataset_version", ":TYPE"], [{":START_ID(Trial)": row["nct_id"], ":END_ID(PlannedOutcome)": row["planned_outcome_id:ID(PlannedOutcome)"], "source_table": "design_outcomes.txt", "source_record_id": row["source_record_id"], **shared, ":TYPE": "HAS_PLANNED_OUTCOME"} for row in outcomes])
    source_fields = ["source_dataset_id:ID(SourceDataset)", "dataset_version", "graph_version", "snapshot_date", "snapshot_file", "snapshot_url", "archive_md5", "archive_sha256", "pinned_manifest_sha256", ":LABEL"]
    source = {"source_dataset_id:ID(SourceDataset)": DATASET, **shared, "graph_version": VERSION, "snapshot_date": "2026-09-05", "snapshot_file": archive_path.name, "snapshot_url": reused.SNAPSHOT_URL, "archive_md5": md5.hexdigest(), "archive_sha256": sha.hexdigest(), "pinned_manifest_sha256": MEMBERSHIP_SHA, ":LABEL": "SourceDataset"}
    nodes["SourceDataset"] = ("source_dataset", "source_dataset_id", source_fields, [source])
    for label, (filename, id_field, fields, rows) in nodes.items():
        id_header = f"{id_field}:ID({label})"
        rows.sort(key=lambda row: row[id_header])
        write_csv(out / f"nodes_{filename}.csv", fields, rows)
        if label == "SourceDataset":
            continue
        suffix = "trial_source_dataset" if label == "Trial" else filename + "_source_dataset"
        rel_fields = [f":START_ID({label})", ":END_ID(SourceDataset)", "dataset_version", ":TYPE"]
        edges[suffix] = (rel_fields, [{f":START_ID({label})": row[id_header], ":END_ID(SourceDataset)": DATASET, **shared, ":TYPE": "MEMBER_OF_DATASET" if label == "Trial" else "SOURCED_FROM"} for row in rows])
    for suffix, (fields, rows) in edges.items():
        write_csv(out / f"relationships_{suffix}.csv", fields, rows)
    coverage = []
    for nct in sorted(ids):
        for table in SOURCE_COLUMNS:
            rows = grouped[table].get(nct, [])
            missing_fields = {field: sum(not row.get(field, "").strip() for row in rows) for field in SOURCE_COLUMNS[table] if field not in {"id", "nct_id"}}
            coverage.append({"nct_id": nct, "source_table": table, "source_record_count": len(rows), "evidence_status": "PRESENT" if rows else "NO_SOURCE_RECORD_FOUND_IN_PINNED_SNAPSHOT", "missing_field_counts_json": json.dumps(missing_fields, sort_keys=True), "lead_sponsor_count": sum(reused.normalized(row.get("lead_or_collaborator")) == "lead" for row in rows) if table == "sponsors.txt" else ""})
    write_csv(out / "source_coverage.csv", ["nct_id", "source_table", "source_record_count", "evidence_status", "missing_field_counts_json", "lead_sponsor_count"], coverage)
    result = validate_graph(out)
    result["checks"]["existing_baselines_unchanged"] = baseline_hashes == protected_files()
    if not result["checks"]["existing_baselines_unchanged"]:
        raise RuntimeError("Protected baseline changed during preparation")
    missing = {table: sorted(ids - set(grouped[table])) for table in SOURCE_COLUMNS}
    limitations = [
        "Deterministic hash selection is illustrative, not a representative or clinically balanced sample.",
        "Pinned membership is restricted to observed terminal outcomes; labels are not exported as retrieval evidence.",
        "Snapshot values may contain amendments and are not asserted to be initial registration values.",
        "Registered planned outcomes are not observed clinical results. Time frames describe planned measurement windows.",
        "Only lead sponsors become Sponsor relationships; collaborator source rows remain in the safe source cache.",
        "Normalized entity display values use the first stable source record; exact source values/IDs remain in the cache.",
        "Missing fields remain blank; zero source records do not prove that evidence never existed.",
        "These versioned pilot CSVs require a separately configured importer; the existing five-trial importer has fixed counts/headers.",
    ]
    lines = [f"# {VERSION} local validation", "", f"Dataset: `{DATASET}`; snapshot: 2026-09-05.", "", "Selection: rank all 2,824 unique manifest NCT IDs by SHA-256(" + repr(SEED) + " + NCT ID), then NCT ID; retain the first 50. No source availability, outcomes, labels, or predictions enter selection.", "", "## Graph counts", ""]
    lines += [f"- {label}: {count}" for label, count in sorted(result["node_counts"].items())]
    lines += [f"- Total nodes: {result['total_nodes']}", f"- Total relationships: {result['total_relationships']}", "", "## Relationship counts", ""]
    lines += [f"- {kind}: {count}" for kind, count in result["relationship_counts"].items()]
    lines += ["", "## Checks", ""] + [f"- {'PASS' if value else 'FAIL'} — {key}" for key, value in result["checks"].items()]
    lines += ["- PASS — archive size/MD5 and six pinned member CRCs; every member fully streamed to verify its CRC.", "", "## Source coverage", ""]
    lines += [f"- {table}: {len(sources[table])} records; {50-len(missing[table])}/50 trials; missing IDs: {', '.join(missing[table]) or 'none'}." for table in SOURCE_COLUMNS]
    lines += ["", "## Limitations", ""] + ["- " + value for value in limitations]
    (out / "VALIDATION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = {
        "pilot_version": VERSION, "authoritative_dataset_version": DATASET,
        "created_utc": datetime.now(timezone.utc).isoformat(), "snapshot_date": "2026-09-05",
        "selection": {"algorithm": "ascending SHA-256(seed + nct_id), tie-break by NCT ID; first 50", "seed": SEED, "independent_of_source_coverage_labels_and_predictions": True, "selected_nct_ids": selected},
        "pinned_manifest": {"path": str(MEMBERSHIP.relative_to(ROOT)), "sha256": MEMBERSHIP_SHA, "rows": 2824},
        "archive": {"filename": archive_path.name, "size_bytes": archive_path.stat().st_size, "md5": md5.hexdigest(), "sha256": sha.hexdigest(), "source_url": reused.SNAPSHOT_URL, "tables": table_audit},
        "source_missing_trial_ids": missing, "source_record_counts": {table: len(rows) for table, rows in sources.items()},
        "validation": result, "limitations": limitations,
        "feature_policy": {"source_columns": SOURCE_COLUMNS, "prohibited_columns": sorted(PROHIBITED), "planned_outcome_cap": None},
        "code_sha256": {str(Path(__file__).resolve().relative_to(ROOT)): digest(__file__), "artifacts/knowledge_graph/prepare_neo4j_import.py": digest(ROOT / "artifacts/knowledge_graph/prepare_neo4j_import.py")},
        "protected_source_hashes": baseline_hashes, "runtime_seconds": round(time.perf_counter() - started, 3),
        "files_sha256": {str(path.relative_to(out)): digest(path) for path in sorted(out.rglob("*")) if path.is_file()},
    }
    (out / "pilot_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "SHA256SUMS").write_text("".join(f"{digest(path)}  {path.relative_to(out).as_posix()}\n" for path in sorted(out.rglob("*")) if path.is_file()), encoding="utf-8")
    return manifest


def validate_saved(out):
    manifest = json.loads((out / "pilot_manifest.json").read_text())
    for name, expected in manifest["files_sha256"].items():
        if digest(out / name) != expected:
            raise RuntimeError(f"Pilot output hash mismatch: {name}")
    for line in (out / "SHA256SUMS").read_text().splitlines():
        expected, name = line.split("  ", 1)
        if digest(out / name) != expected:
            raise RuntimeError(f"Checksum-list mismatch: {name}")
    for name, expected in manifest["protected_source_hashes"].items():
        if digest(ROOT / name) != expected:
            raise RuntimeError(f"Protected baseline hash mismatch: {name}")
    result = validate_graph(out)
    if any(result[key] != manifest["validation"][key] for key in ("node_counts", "relationship_counts", "total_nodes", "total_relationships")):
        raise RuntimeError("Saved manifest counts do not match CSVs")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        result = validate_saved(OUTPUT)
    else:
        if args.archive is None:
            parser.error("--archive is required for preparation")
        manifest = prepare(args.archive.resolve(), OUTPUT)
        result = validate_saved(OUTPUT)
        result["runtime_seconds"] = manifest["runtime_seconds"]
    print(json.dumps({"output_directory": str(OUTPUT), "result": result}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
