#!/usr/bin/env python3
"""Offline, pre-split full-cohort extraction. No embeddings or model execution."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

try:
    from . import extract_graph as prototype
except ImportError:  # Direct script invocation.
    import extract_graph as prototype


ROOT = Path(__file__).resolve().parents[2]
VERSION = "HTT-GNN-FULL2824-EXTRACT-v1"
GRAPH_VERSION = "HTT-KG-AACT-20260905-FULL2824-v1"
DATASET_VERSION = "HTT-P1-AACT-20260905"
SNAPSHOT_DATE = "2026-09-05"
MANIFEST_SHA256 = "3ef82624d131b36abc1eb9ad4e89b3439fed9f9600b92262c21bbcbfe6cf8757"
DEFAULT_SOURCE = ROOT / "artifacts/cohort_scaling" / GRAPH_VERSION
DEFAULT_OUTPUT = ROOT / "gnn_graphrag/data" / VERSION
NODE_ORDER = prototype.NODE_LABEL_ORDER
RELATIONSHIP_ORDER = prototype.RELATIONSHIP_TYPE_ORDER
PROVENANCE_TYPES = prototype.PROVENANCE_RELATIONSHIP_TYPES
FEATURE_FIELDS = {**prototype.FEATURE_FIELDS, "Trial": ("brief_title", "study_type", "phase")}
NCT_TOKEN = re.compile(r"\bNCT\d{8}\b", re.IGNORECASE)
TRAINING_WARNING = (
    "PRE_SPLIT_NOT_LEAKAGE_SAFE: withheld target associations and their computational "
    "reverse edges must be removed before embeddings or message passing are computed."
)

# These are the actual full-cohort schemas, not the five-trial input headers.
NODE_HEADERS = {
    "Trial": ("trial_id:ID(Trial)", "nct_id", "brief_title", "study_type", "phase", "source_table", "source_record_id", "source_evidence_status", "dataset_version", ":LABEL"),
    "ConditionTerm": ("condition_id:ID(ConditionTerm)", "name", "normalized_name", "source_table", "dataset_version", ":LABEL", "source_kind"),
    "Intervention": ("intervention_id:ID(Intervention)", "name", "normalized_name", "source_table", "dataset_version", ":LABEL", "intervention_type"),
    "Sponsor": ("sponsor_id:ID(Sponsor)", "name", "normalized_name", "source_table", "dataset_version", ":LABEL", "agency_class"),
    "PlannedOutcome": ("planned_outcome_id:ID(PlannedOutcome)", "source_record_id", "nct_id", "outcome_type", "measure", "time_frame", "population", "description", "source_table", "evidence_safeguard", "dataset_version", ":LABEL"),
    "SourceDataset": ("source_dataset_id:ID(SourceDataset)", "dataset_version", "graph_version", "snapshot_date", "snapshot_file", "snapshot_url", "archive_md5", "archive_sha256", "pinned_manifest_sha256", ":LABEL"),
}
NODE_SPECS = tuple(prototype.NodeSpec(s.filename, s.label, s.id_header, NODE_HEADERS[s.label])
                   for s in prototype.NODE_SPECS)
RELATIONSHIP_SPECS = tuple(prototype.RelationshipSpec(
    {"relationships_condition_source_dataset.csv": "relationships_condition_term_source_dataset.csv",
     "relationships_outcome_source_dataset.csv": "relationships_planned_outcome_source_dataset.csv"}.get(s.filename, s.filename),
    s.relationship_type, s.source_label, s.target_label, s.source_header, s.target_header,
    (s.source_header, s.target_header, "source_table", "source_record_ids", "dataset_version", ":TYPE")
    if s.relationship_type in {"HAS_SUBMITTED_CONDITION", "HAS_BROWSE_CONDITION"} else s.header,
) for s in prototype.RELATIONSHIP_SPECS)
NODE_SPEC_BY_LABEL = {s.label: s for s in NODE_SPECS}
REL_SPEC_BY_FILE = {s.filename: s for s in RELATIONSHIP_SPECS}
SOURCE_TABLES = {
    "Trial": "studies.txt", "Intervention": "interventions.txt",
    "Sponsor": "sponsors.txt", "PlannedOutcome": "design_outcomes.txt",
}


class FullExtractionError(ValueError):
    """The pinned source or extraction contract was violated."""


def require(condition, message):
    if not condition:
        raise FullExtractionError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def read_csv(path, header):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames == list(header), f"Unexpected CSV schema: {Path(path).name}")
        rows = list(reader)
    require(all(set(row) == set(header) and all(isinstance(v, str) for v in row.values())
                for row in rows), f"Malformed CSV record: {Path(path).name}")
    return rows


def feature_text(label, properties):
    """Reuse approved formatting; identifiers remain only in linkage metadata.

    NCT tokens embedded in an approved title/measure are also redacted. Original
    source values, including those tokens and all blanks, remain in metadata.
    """
    require(label in FEATURE_FIELDS, "Unknown feature label")
    allowed = {key: properties.get(key, "") for key in FEATURE_FIELDS[label]}
    return " ".join(NCT_TOKEN.sub("", prototype.canonical_feature_text(label, allowed)).split())


@dataclass(frozen=True)
class FullGraph:
    manifest: dict
    source_hashes: dict
    membership: tuple
    nodes: tuple
    relationships: tuple


def validate_graph(graph):
    """Validate schemas, exact membership, provenance, counts and associations."""
    manifest = graph.manifest
    require((manifest.get("schema_version"), manifest.get("authoritative_dataset_version"),
             manifest.get("graph_version"), manifest.get("snapshot_date")) ==
            ("HTT-FULL-COHORT-GRAPH-v1", DATASET_VERSION, GRAPH_VERSION, SNAPSHOT_DATE),
            "Source manifest identity mismatch")
    expected = manifest["validation"]
    ids = graph.membership
    require(len(ids) == len(set(ids)) == manifest["membership"]["count"] == 2824
            and list(ids) == sorted(ids) and all(re.fullmatch(r"NCT\d{8}", n) for n in ids),
            "Invalid frozen membership")
    nodes = {}
    for node in graph.nodes:
        require(node.label in NODE_SPEC_BY_LABEL, "Unknown node label")
        spec = NODE_SPEC_BY_LABEL[node.label]
        props = node.properties
        require(set(props) == set(spec.header) and node.source_file == spec.filename,
                "Unexpected node property schema")
        require(node.node_id and node.node_id == props[spec.id_header] and node.node_id not in nodes,
                "Missing or duplicate node identifier")
        require(props[":LABEL"] == node.label and props["dataset_version"] == DATASET_VERSION,
                "Node label/version mismatch")
        if node.label == "Trial":
            require(props["nct_id"] == node.node_id and props["source_table"] == "studies.txt"
                    and props["source_evidence_status"] in {"PRESENT", "MISSING_SOURCE_RECORD"},
                    "Trial provenance mismatch")
            require(props["source_record_id"] == (node.node_id if props["source_evidence_status"] == "PRESENT" else ""),
                    "Trial source identifier mismatch")
        elif node.label == "ConditionTerm":
            table = {"submitted": "conditions.txt", "browse": "browse_conditions.txt"}.get(props["source_kind"])
            require(table is not None and props["source_table"] == table, "Condition source classification mismatch")
        elif node.label in SOURCE_TABLES:
            require(props["source_table"] == SOURCE_TABLES[node.label], "Node source table mismatch")
        if node.label == "PlannedOutcome":
            require(props["nct_id"] in ids and re.fullmatch(r"\d+", props["source_record_id"])
                    and node.node_id == "planned_outcome:" + props["source_record_id"]
                    and props["evidence_safeguard"] == prototype.PLANNED_OUTCOME_SAFEGUARD,
                    "Planned outcome identity/provenance mismatch")
        nodes[node.node_id] = node
    require({n.node_id for n in graph.nodes if n.label == "Trial"} == set(ids), "Trial membership mismatch")
    require(dict(Counter(n.label for n in graph.nodes)) == expected["node_counts"]
            and len(nodes) == expected["total_nodes"] == 28777, "Node count mismatch")
    source = [n for n in graph.nodes if n.label == "SourceDataset"]
    require(len(source) == 1 and source[0].node_id == DATASET_VERSION, "Invalid SourceDataset")
    archive = manifest["archive"]
    source_values = {"dataset_version": DATASET_VERSION, "graph_version": GRAPH_VERSION,
        "snapshot_date": SNAPSHOT_DATE, "snapshot_file": archive["filename"],
        "snapshot_url": archive["source_url"], "archive_md5": archive["md5"],
        "archive_sha256": archive["sha256"], "pinned_manifest_sha256": manifest["membership"]["frozen_source_sha256"]}
    require(all(source[0].properties[k] == v for k, v in source_values.items()), "SourceDataset provenance mismatch")

    triples, outcome_links, provenance_nodes = set(), set(), set()
    for rel in graph.relationships:
        require(rel.source_file in REL_SPEC_BY_FILE, "Unknown relationship file")
        spec = REL_SPEC_BY_FILE[rel.source_file]
        props = rel.properties
        require((rel.relationship_type, rel.source_label, rel.target_label) ==
                (spec.relationship_type, spec.source_label, spec.target_label)
                and set(props) == set(spec.header) - {spec.source_header, spec.target_header, ":TYPE"},
                "Unexpected relationship schema/type")
        require(rel.source_id in nodes and rel.target_id in nodes, "Invalid relationship endpoint")
        require(nodes[rel.source_id].label == rel.source_label and nodes[rel.target_id].label == rel.target_label,
                "Relationship endpoint label mismatch")
        key = (rel.source_id, rel.relationship_type, rel.target_id)
        require(key not in triples and props["dataset_version"] == DATASET_VERSION,
                "Duplicate relationship or version mismatch")
        triples.add(key)
        if rel.relationship_type in PROVENANCE_TYPES:
            require(rel.target_id == DATASET_VERSION and rel.source_id not in provenance_nodes,
                    "Provenance relationship mismatch")
            provenance_nodes.add(rel.source_id)
        else:
            require(props.get("source_table") == nodes[rel.target_id].properties["source_table"],
                    "Relationship source table mismatch")
            if rel.relationship_type == "HAS_SUBMITTED_CONDITION":
                require(nodes[rel.target_id].properties["source_kind"] == "submitted", "Submitted condition mismatch")
            if rel.relationship_type == "HAS_BROWSE_CONDITION":
                require(nodes[rel.target_id].properties["source_kind"] == "browse", "Browse condition mismatch")
            if "source_record_ids" in props:
                values = props["source_record_ids"].split(";")
                require(len(set(values)) == len(values) and all(re.fullmatch(r"\d+", v) for v in values),
                        "Invalid relationship source-record identifiers")
            if rel.relationship_type == "HAS_PLANNED_OUTCOME":
                target = nodes[rel.target_id].properties
                require(target["nct_id"] == rel.source_id and target["source_record_id"] == props["source_record_id"]
                        and rel.target_id not in outcome_links, "Planned outcome trial/source association mismatch")
                outcome_links.add(rel.target_id)
    require(dict(Counter(r.relationship_type for r in graph.relationships)) == expected["relationship_counts"]
            and len(triples) == expected["total_relationships"] == 79125, "Relationship count mismatch")
    require(provenance_nodes == set(nodes) - {DATASET_VERSION}, "Missing source provenance relationships")
    require(outcome_links == {n.node_id for n in graph.nodes if n.label == "PlannedOutcome"}, "Missing outcome relationships")
    require(sum(r.relationship_type not in PROVENANCE_TYPES for r in graph.relationships) == 50349,
            "Semantic relationship count mismatch")


def load_verified_full_graph(source_dir=DEFAULT_SOURCE):
    directory = Path(source_dir)
    path = directory / "full_cohort_manifest.json"
    require(path.is_file() and sha256(path) == MANIFEST_SHA256, "Source manifest SHA-256 mismatch")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    hashes = manifest["files_sha256"]
    required = {s.filename for s in NODE_SPECS} | {s.filename for s in RELATIONSHIP_SPECS} | {"cohort_membership.csv"}
    require(required <= set(hashes), "Missing required source checksums")
    for name, expected in hashes.items():
        relative = Path(name)
        require(not relative.is_absolute() and ".." not in relative.parts, "Unsafe source file path")
        candidate = directory / relative
        require(candidate.is_file() and sha256(candidate) == expected, f"Source SHA-256 mismatch: {name}")
    frozen = manifest["membership"]["frozen_source"]
    require(not Path(frozen).is_absolute() and ".." not in Path(frozen).parts, "Unsafe frozen source path")
    require(sha256(ROOT / frozen) == manifest["membership"]["frozen_source_sha256"], "Original frozen manifest SHA-256 mismatch")
    require(manifest["membership"]["path"] == "cohort_membership.csv", "Unexpected membership path")
    rows = read_csv(directory / "cohort_membership.csv", ("nct_id", "dataset_version", "graph_version"))
    require(all(row["dataset_version"] == DATASET_VERSION and row["graph_version"] == GRAPH_VERSION for row in rows),
            "Membership version mismatch")
    nodes, relationships = [], []
    for spec in NODE_SPECS:
        for row in read_csv(directory / spec.filename, spec.header):
            nodes.append(prototype.SourceNode(row[spec.id_header], spec.label, spec.filename, row))
    for spec in RELATIONSHIP_SPECS:
        for row in read_csv(directory / spec.filename, spec.header):
            require(row[":TYPE"] == spec.relationship_type, "Relationship type mismatch")
            props = {k: v for k, v in row.items() if k not in (spec.source_header, spec.target_header, ":TYPE")}
            relationships.append(prototype.SourceRelationship(row[spec.source_header], row[spec.target_header],
                spec.relationship_type, spec.source_label, spec.target_label, spec.filename, props))
    graph = FullGraph(manifest, dict(hashes), tuple(row["nct_id"] for row in rows), tuple(nodes), tuple(relationships))
    validate_graph(graph)
    return graph


NODE_OUTPUT_FIELDS = ("node_index", "node_id", "node_label", "source_file", "dataset_version",
    "graph_version", "snapshot_date", "properties_json", "missing_feature_fields_json", "feature_text", "feature_text_sha256")
REL_OUTPUT_FIELDS = ("relationship_index", "source_node_index", "source_node_id", "source_node_label",
    "target_node_index", "target_node_id", "target_node_label", "relationship_type", "source_file", "properties_json")
MESSAGE_FIELDS = ("message_edge_index", "source_node_index", "source_node_label", "target_node_index",
    "target_node_label", "relationship_type", "message_direction", "original_relationship_index")


def write_csv(path, fields, rows):
    count = 0
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def extract_full_cohort(source_dir=DEFAULT_SOURCE, output_dir=DEFAULT_OUTPUT):
    output = Path(output_dir)
    # Fail before opening source files if an existing result could be overwritten.
    require(not output.exists(), "Output directory already exists; use a new versioned destination")
    source = Path(source_dir).resolve()
    require(not output.resolve().is_relative_to(source), "Output must be separate from pinned source artifacts")
    graph = load_verified_full_graph(source)
    label_order = {label: i for i, label in enumerate(NODE_ORDER)}
    nodes = sorted(graph.nodes, key=lambda n: (label_order[n.label], n.node_id))
    indices = {node.node_id: index for index, node in enumerate(nodes)}
    types = {kind: i for i, kind in enumerate(RELATIONSHIP_ORDER)}
    relationships = sorted(graph.relationships, key=lambda r: (types[r.relationship_type],
        indices[r.source_id], indices[r.target_id], r.source_file, canonical(r.properties)))
    missing = {label: Counter() for label in NODE_ORDER}
    redacted_count = 0

    def node_rows():
        nonlocal redacted_count
        for node in nodes:
            absent = [k for k in FEATURE_FIELDS[node.label] if not node.properties.get(k, "").strip()]
            missing[node.label].update(absent)
            raw_text = prototype.canonical_feature_text(node.label,
                {k: node.properties.get(k, "") for k in FEATURE_FIELDS[node.label]})
            redacted_count += len(NCT_TOKEN.findall(raw_text))
            text = feature_text(node.label, node.properties)
            spec = NODE_SPEC_BY_LABEL[node.label]
            properties = {k: v for k, v in node.properties.items() if k not in (spec.id_header, ":LABEL")}
            yield {"node_index": indices[node.node_id], "node_id": node.node_id, "node_label": node.label,
                "source_file": node.source_file, "dataset_version": DATASET_VERSION,
                "graph_version": GRAPH_VERSION, "snapshot_date": SNAPSHOT_DATE,
                "properties_json": canonical(properties), "missing_feature_fields_json": canonical(absent),
                "feature_text": text, "feature_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}

    def relationship_rows():
        for i, rel in enumerate(relationships):
            yield {"relationship_index": i, "source_node_index": indices[rel.source_id],
                "source_node_id": rel.source_id, "source_node_label": rel.source_label,
                "target_node_index": indices[rel.target_id], "target_node_id": rel.target_id,
                "target_node_label": rel.target_label, "relationship_type": rel.relationship_type,
                "source_file": rel.source_file, "properties_json": canonical(rel.properties)}

    def message_rows():
        index = 0
        seen = set()
        for original_index, rel in enumerate(relationships):
            if rel.relationship_type in PROVENANCE_TYPES:
                continue
            for direction, s, t, sl, tl in (
                ("forward", rel.source_id, rel.target_id, rel.source_label, rel.target_label),
                ("reverse", rel.target_id, rel.source_id, rel.target_label, rel.source_label)):
                key = (indices[s], indices[t], rel.relationship_type)
                require(key not in seen, "Duplicate computational message edge")
                seen.add(key)
                yield {"message_edge_index": index, "source_node_index": indices[s], "source_node_label": sl,
                    "target_node_index": indices[t], "target_node_label": tl, "relationship_type": rel.relationship_type,
                    "message_direction": direction, "original_relationship_index": original_index}
                index += 1

    output.mkdir(parents=True, exist_ok=False)
    # Stream output rows; no all-edge message tensor or feature matrix is built.
    outputs = {}
    for name, fields, rows in (("nodes.csv", NODE_OUTPUT_FIELDS, node_rows()),
        ("relationships.csv", REL_OUTPUT_FIELDS, relationship_rows()),
        ("message_edges_semantic.csv", MESSAGE_FIELDS, message_rows())):
        count = write_csv(output / name, fields, rows)
        outputs[name] = {"row_count": count, "sha256": sha256(output / name)}
    require(outputs["message_edges_semantic.csv"]["row_count"] == 100698, "Computational edge count mismatch")
    validation = graph.manifest["validation"]
    manifest = {
        "extraction_version": VERSION, "deterministic": True, "created_utc": None,
        "implementation_sha256": sha256(Path(__file__)), "prototype_helper_sha256": sha256(Path(prototype.__file__)),
        "source": {"dataset_version": DATASET_VERSION, "graph_version": GRAPH_VERSION, "snapshot_date": SNAPSHOT_DATE,
            "manifest_sha256": MANIFEST_SHA256, "archive": {k: graph.manifest["archive"][k]
                for k in ("filename", "source_url", "md5", "sha256")},
            "frozen_membership_sha256": graph.manifest["membership"]["frozen_source_sha256"],
            "all_manifest_listed_file_sha256": graph.source_hashes},
        "counts": {"nodes_total": len(nodes), "nodes_by_label": validation["node_counts"],
            "original_relationships_total": len(relationships), "original_relationships_by_type": validation["relationship_counts"],
            "semantic_original_relationships": 50349, "provenance_original_relationships": 28776,
            "semantic_forward_message_edges": 50349, "semantic_reverse_message_edges": 50349,
            "semantic_message_edges_total": 100698},
        "ordering": {"node_labels": list(NODE_ORDER), "within_label": "ascending stable import identifier",
            "relationship_types": list(RELATIONSHIP_ORDER), "within_type": "source index, target index, filename, canonical properties JSON",
            "message_order": "original relationship order; forward then reverse; provenance excluded",
            "indices": "zero-based contiguous; independent of clinical meaning"},
        "feature_policy": {"approved_fields_by_label": FEATURE_FIELDS,
            "prohibited_fields": sorted(set(prototype.PROHIBITED_FEATURE_FIELDS) | set(graph.manifest["feature_policy"]["prohibited_columns"])),
            "nct_identifiers": "linkage metadata only; NCT tokens redacted from all feature text",
            "redacted_feature_text_nct_tokens": redacted_count, "llm_generated": False,
            "missing_values": "original blank strings retained in properties_json; no imputation; blank feature values omitted",
            "planned_outcome_safeguard": prototype.PLANNED_OUTCOME_SAFEGUARD,
            "snapshot_safeguard": "September 2026 values may include amendments; original-registration availability is not asserted."},
        "missingness": {"blank_feature_fields_by_label": {k: dict(sorted(v.items())) for k, v in missing.items()},
            "source_missing_trial_ids": validation["source_missing_trial_ids"],
            "source_missing_field_counts": validation["source_missing_field_counts"]},
        "message_passing_policy": {"excluded_relationship_types": sorted(PROVENANCE_TYPES),
            "original_provenance_preserved": True, "reverse_edges_are_computational_only": True,
            "duplicate_typed_edges": False, "isolated_source_dataset_retained": True},
        "training_readiness": {"status": "PRE_SPLIT_NOT_LEAKAGE_SAFE", "warning": TRAINING_WARNING,
            "target_associations_present": True, "splits_created": False, "embeddings_computed": False,
            "message_passing_performed": False, "training_performed": False},
        "validation": {"source_checksums_passed": True, "source_files_verified": len(graph.source_hashes),
            "frozen_manifest_checksum_passed": True, "membership_exact": True, "schemas_exact": True,
            "unique_identifiers": True, "valid_endpoints": True, "source_bound_outcome_links": True,
            "counts_match": True, "all_original_relationships_preserved": True},
        "outputs": outputs,
    }
    (output / "extraction_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    names = sorted([*outputs, "extraction_manifest.json"])
    (output / "SHA256SUMS").write_text("".join(f"{sha256(output / name)}  {name}\n" for name in names), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        manifest = extract_full_cohort(args.source_dir, args.output_dir)
    except (FullExtractionError, OSError, ValueError) as exc:
        parser.exit(1, f"Extraction failed; no fallback or overwrite: {exc}\n")
    print(json.dumps({"output_dir": str(args.output_dir), "counts": manifest["counts"],
        "training_readiness": manifest["training_readiness"]["status"]}, indent=2))


if __name__ == "__main__":
    main()
