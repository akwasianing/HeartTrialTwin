#!/usr/bin/env python3
"""Isolated, offline community/retrieval experiment on checksum-pinned CSVs.

No driver, credentials, model, network, or production code changes are needed.
New output directories only; use --validate-only to check an existing run.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import itertools
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from full_cohort_graphrag.src import retrieve as api
from full_cohort_graphrag.src.prepare_evidence import prepare_evidence
from full_cohort_graphrag.src.list_planned_outcomes import list_registered_planned_outcomes

VERSION = "HTT-C4-COMMUNITY-PILOT-v1"
SOURCE = ROOT / "artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "output"
SEEDS = (20261027, 0, 1, 2)
GROUP_LIMIT, TRIALS_PER_GROUP = 3, 5
GENERIC = {"drug", "usual care", "standard care", "control", "treatment"}
REL_FILES = {
    "HAS_SUBMITTED_CONDITION": "relationships_trial_submitted_condition.csv",
    "HAS_BROWSE_CONDITION": "relationships_trial_browse_condition.csv",
    "HAS_INTERVENTION": "relationships_trial_intervention.csv",
    "LEAD_SPONSORED_BY": "relationships_trial_sponsor.csv",
    "HAS_PLANNED_OUTCOME": "relationships_trial_planned_outcome.csv",
}
NODE_FILES = {
    "ConditionTerm": "nodes_condition_term.csv", "Intervention": "nodes_intervention.csv",
    "Sponsor": "nodes_sponsor.csv", "PlannedOutcome": "nodes_planned_outcome.csv",
}
PROTECTED = (
    "reports/challenge4/ai_design/AI_DESIGN_REVIEW_v1.md",
    "reports/challenge4/ai_design/PROMPT_AND_RECOMMENDATIONS_v1.md",
    "artifacts/knowledge_graph/graph_import_manifest.json",
    "gnn_graphrag/protocols/HTT-GNN-ASSOC-PROTOCOL-v1/split_manifest.json",
    "gnn_graphrag/protocols/HTT-GNN-ASSOC-PROTOCOL-v2/split_manifest.json",
    "gnn_graphrag/feature_artifacts/HTT-GNN-ASSOC-FEATURES-v1/manifest.json",
    "gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/training/selected_model.pt",
    "full_cohort_graphrag/src/retrieve.py",
    "full_cohort_graphrag/src/prepare_evidence.py",
    "full_cohort_graphrag/src/list_planned_outcomes.py",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def normalized(text):
    """Lexical comparison only; no synonyms, time conversion or clinical mapping."""
    return " ".join(text.casefold().split())


def read_csv(name):
    with (SOURCE / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


class CsvEvidence:
    """Actual pinned local records projected into the existing evidence contract.

    This is an offline CSV adapter, not a mock/live Neo4j response. It preserves
    query ordering, field allowlists and provenance, then invokes the unchanged
    evidence validator and deterministic listing function.
    """
    def __init__(self):
        self.contract = api.load_contract(SOURCE)
        self.manifest = self.contract.manifest
        self.verified_hashes = {}
        for name, expected in self.manifest["files_sha256"].items():
            actual = sha(SOURCE / name)
            require(actual == expected, "Pinned source checksum mismatch: " + name)
            self.verified_hashes[name] = actual
        self.trials = {}
        for row in read_csv("nodes_trial.csv"):
            nct = row["trial_id:ID(Trial)"]
            require(nct not in self.trials, "Duplicate trial")
            self.trials[nct] = {"trial_id": nct, **{k: row[k] for k in api.TRIAL_FIELDS if k != "trial_id"}}
        require(set(self.trials) == set(self.contract.membership), "Source membership mismatch")
        self.nodes = {}
        for label, name in NODE_FILES.items():
            rows = read_csv(name)
            id_header = next(k for k in rows[0] if ":ID(" in k)
            id_property = id_header.split(":")[0]
            self.nodes[label] = {}
            for row in rows:
                node = row[id_header]
                require(node not in self.nodes[label], "Duplicate source node")
                self.nodes[label][node] = {id_property: node, **{k: v for k, v in row.items() if ":" not in k}}
        self.records = defaultdict(list)
        for rel, name in REL_FILES.items():
            category, label, id_key, table, fields = api.EVIDENCE_SPECS[rel]
            for row in read_csv(name):
                nct, node = row[":START_ID(Trial)"], row[f":END_ID({label})"]
                require(nct in self.trials and node in self.nodes[label], "Invalid endpoint")
                require(row[":TYPE"] == rel and row["dataset_version"] == api.DATASET, "Bad source relationship")
                props = api.project(self.nodes[label][node], (*fields, "source_table", "dataset_version"))
                rel_props = api.project(row, api.REL_FIELDS)
                ids = [row["source_record_id"]] if rel == "HAS_PLANNED_OUTCOME" else row["source_record_ids"].split(";")
                record = {"evidence_id": f"{nct}|{rel}|{node}", "nct_id": nct,
                    "category": category, "node_id": node, "node_label": label, "properties": props,
                    "relationship": {"type": rel, "start_id": nct, "end_id": node, "properties": rel_props},
                    "source_references": [{"nct_id": nct, "source_table": table, "source_record_id": v} for v in ids],
                    "missing_fields": sorted(k for k, v in props.items() if v == "")}
                self.records[nct].append(record)
        for nct, records in self.records.items():
            records.sort(key=lambda r: (r["relationship"]["type"], r["node_id"]))
            require(len(records) == len({r["evidence_id"] for r in records}), "Duplicate evidence")
        memberships = read_csv("relationships_trial_source_dataset.csv")
        require(len(memberships) == 2824 and {r[":START_ID(Trial)"] for r in memberships} == self.contract.membership,
                "Invalid dataset membership links")
        require(all(r[":END_ID(SourceDataset)"] == api.DATASET and r[":TYPE"] == "MEMBER_OF_DATASET"
                    and r["dataset_version"] == api.DATASET for r in memberships), "Invalid dataset provenance")

    def profile(self, nct, *, limit=200):
        nct = api.nct_id(nct)
        api.page_bounds(limit, 0)
        base = {"schema_version": "HTT-FULL-STATIC-RETRIEVAL-v1", "workflow": "trial_profile",
            "dataset_version": api.DATASET, "graph_version": api.GRAPH, "snapshot_date": api.SNAPSHOT,
            "manifest_sha256": api.MANIFEST_SHA256, "source_dataset": self.contract.source,
            "access_mode": "OFFLINE_PINNED_CSV_NOT_LIVE_NEO4J",
            "safeguards": {"planned_outcomes": api.PLANNED_SAFEGUARD, "snapshot": api.SNAPSHOT_SAFEGUARD,
                           "read_only": True, "no_answer_generation": True}}
        if nct not in self.trials:
            return {**base, "status": "NOT_FOUND", "nct_id": nct, "trial": None,
                    "evidence": [], "coverage": {}, "pagination": api.pagination(0, 0, limit, 0)}
        all_records, page = self.records[nct], self.records[nct][:limit]
        counts = Counter(r["relationship"]["type"] for r in all_records)
        coverage = api.FullCohortRetriever._coverage(counts, page, sorted(api.EVIDENCE_SPECS))
        complete = all(counts[rel] for rel in api.EVIDENCE_SPECS) and len(page) == len(all_records)
        return {**base, "nct_id": nct, "trial": self.trials[nct], "evidence": page,
                "status": "COMPLETE" if complete else "PARTIAL", "coverage": coverage,
                "pagination": api.pagination(len(all_records), len(page), limit, 0),
                "dataset_relationship": {"type": "MEMBER_OF_DATASET", "start_id": nct,
                    "end_id": api.DATASET, "properties": {"dataset_version": api.DATASET}}}

    def prepared(self, nct, *, limit=200):
        return prepare_evidence(self.profile(nct, limit=limit), contract=self.contract)


def select_pilot(source):
    candidates = defaultdict(set)
    for nct in sorted(source.trials):
        rows = source.records[nct]
        has_hf = any(r["category"] == "submitted_conditions" and r["properties"]["normalized_name"] == "heart failure" for r in rows)
        if not has_hf:
            continue
        for row in rows:
            if row["category"] != "interventions":
                continue
            p = row["properties"]
            name = p["normalized_name"]
            if p["intervention_type"] == "DRUG" and name and "placebo" not in name and name not in GENERIC:
                candidates[row["node_id"]].add(nct)
    names = source.nodes["Intervention"]
    ordered = sorted((k for k, ids in candidates.items() if len(ids) >= TRIALS_PER_GROUP),
                     key=lambda k: (-len(candidates[k]), names[k]["normalized_name"], k))
    require(len(ordered) >= GROUP_LIMIT, "Insufficient qualifying groups; no substitute rule")
    groups = []
    for index, node in enumerate(ordered[:GROUP_LIMIT], 1):
        groups.append({"community_id": f"C{index:02}", "method": "CONSTRUCTED_EXACT_RULE_NOT_DETECTED",
            "submitted_condition_normalized": "heart failure", "intervention_id": node,
            "intervention_name": names[node]["name"], "intervention_normalized": names[node]["normalized_name"],
            "intervention_type": "DRUG", "qualifying_full_cohort_trials": len(candidates[node]),
            "member_nct_ids": sorted(candidates[node])[:TRIALS_PER_GROUP],
            "omitted_full_cohort_nct_ids": sorted(candidates[node])[TRIALS_PER_GROUP:]})
    ids = sorted({n for g in groups for n in g["member_nct_ids"]})
    require(len(ids) <= GROUP_LIMIT * TRIALS_PER_GROUP, "Pilot bound exceeded")
    return groups, ids


def membership_evidence(source, group, nct):
    records = source.prepared(nct)["trials"][0]["categories"]
    condition = [r for r in records["submitted_conditions"] if r["properties"]["normalized_name"] == "heart failure"]
    intervention = [r for r in records["interventions"] if r["node_id"] == group["intervention_id"]]
    require(condition and intervention, "Unsupported community membership")
    return {"community_id": group["community_id"], "nct_id": nct,
            "source_evidence_ids": sorted(r["evidence_id"] for r in condition + intervention),
            "citation_ids": sorted({v for r in condition + intervention for v in r["citation_ids"]})}


def projection(groups):
    edges = {}
    for group in groups:
        for a, b in itertools.combinations(group["member_nct_ids"], 2):
            edges.setdefault((a, b), []).append(group["community_id"])
    return [{"start_nct_id": a, "end_nct_id": b, "weight": len(values),
             "supporting_community_ids": values, "edge_kind": "DERIVED_SIMILARITY_NOT_REGISTERED_RELATIONSHIP"}
            for (a, b), values in sorted(edges.items())]


def detect(groups, ids):
    import networkx as nx
    graph = nx.Graph()
    graph.add_nodes_from(ids)
    edges = projection(groups)
    graph.add_weighted_edges_from((r["start_nct_id"], r["end_nct_id"], r["weight"]) for r in edges)
    baseline = sorted(sorted(g["member_nct_ids"]) for g in groups)
    runs = []
    for seed in SEEDS:
        clusters = sorted(sorted(v) for v in nx.community.asyn_lpa_communities(graph, weight="weight", seed=seed))
        runs.append({"seed": seed, "communities": clusters, "same_as_rule_groups": clusters == baseline})
    return {"algorithm": "NetworkX asynchronous Label Propagation", "networkx_version": nx.__version__,
            "nodes": graph.number_of_nodes(), "edges": graph.number_of_edges(), "runs": runs,
            "leiden_status": "NOT_RUN_NOT_INSTALLED", "baseline": baseline,
            "limitation": "Rule-selected cliques predefine disconnected components; agreement is a construction sanity check, not independent community validity or retrieval improvement."}


def listing(source, nct, *, limit=200, question=None):
    prepared = source.prepared(nct, limit=limit)
    result = list_registered_planned_outcomes(question or f"What planned outcomes were registered for {nct}?",
                                             prepared, contract=source.contract)
    # Preserve source-bound records and validation; omit only redundant catalogs.
    keep = ("status", "answer", "answer_origin", "model_generated", "listed_outcomes", "validation",
            "source_references", "generation", "safeguards", "prepared_evidence_sha256")
    return {k: result[k] for k in keep}


def alternative_audits(prepared):
    sponsors, endpoints = defaultdict(set), defaultdict(set)
    skipped = []
    for nct, item in sorted(prepared.items()):
        categories = item["trials"][0]["categories"]
        for row in categories["lead_sponsors"]:
            sponsors[row["node_id"]].add(nct)
        for row in categories["planned_outcomes"]:
            p = row["properties"]
            if not p["time_frame"].strip():
                skipped.append({"nct_id": nct, "evidence_id": row["evidence_id"], "reason": "BLANK_TIME_FRAME_NO_SPECIFICATION_MATCH"})
                continue
            key = (normalized(p["measure"]), p["outcome_type"], normalized(p["time_frame"]))
            endpoints[key].add(nct)
    return {"sponsor_rule_cohorts": [{"sponsor_id": k, "member_nct_ids": sorted(v)} for k, v in sorted(sponsors.items())],
            "strict_endpoint_cohorts": [{"normalized_measure": k[0], "outcome_type": k[1], "normalized_time_frame": k[2],
                                          "member_nct_ids": sorted(v)} for k, v in sorted(endpoints.items())],
            "endpoint_rows_excluded_from_strict_matching": skipped,
            "policy": "Case/whitespace only; no semantic, clinical or temporal equivalence inferred. All source outcomes remain in evidence."}


def comparisons(source, groups, prepared):
    seed = "NCT00206232"
    group = next(g for g in groups if seed in g["member_nct_ids"])
    ids = group["member_nct_ids"]
    exact = listing(source, seed)
    community = {n: listing(source, n) for n in ids}
    require(exact["status"] == "COMPLETE_LISTING", "Seed listing failed")
    primary = []
    skipped = []
    for nct, result in community.items():
        if result["status"] != "COMPLETE_LISTING":
            skipped.append({"nct_id": nct, "reasons": result["validation"]["errors"]})
        for record in result["listed_outcomes"]:
            if record["properties"]["outcome_type"] == "primary":
                primary.append(record)
    stats = []
    for g in groups:
        records = [r for n in g["member_nct_ids"] for r in prepared[n]["trials"][0]["categories"]["planned_outcomes"]]
        stats.append({"community_id": g["community_id"], "intervention": g["intervention_name"],
            "trial_count": len(g["member_nct_ids"]), "planned_outcome_records": len(records),
            "records_by_type": dict(sorted(Counter(r["properties"]["outcome_type"] for r in records).items())),
            "distinct_trials_by_type": {t: len({r["nct_id"] for r in records if r["properties"]["outcome_type"] == t})
                                         for t in ("primary", "secondary", "other")},
            "blank_time_frame_records": sum(not r["properties"]["time_frame"].strip() for r in records),
            "missing_outcome_trial_ids": [n for n in g["member_nct_ids"] if not prepared[n]["trials"][0]["categories"]["planned_outcomes"]]})
    return {"execution_mode": "EXECUTED_OFFLINE_PINNED_CSV_NOT_LIVE_NEO4J", "model_attempts": 0,
        "questions": [
            {"id": "P1", "question": f"What planned outcomes were registered for {seed}?",
             "exact_trial_result": {"nct_ids": [seed], "listing": exact},
             "community_aware_result": {"nct_ids": [seed], "listing": exact,
                 "routing": "EXACT_NCT_SCOPE_PRESERVED_NO_AUTOMATIC_EXPANSION"}},
            {"id": "P2", "question": f"Within the pilot, which trials share the registered intervention and submitted condition of {seed}, and what primary planned measures did they register?",
             "exact_trial_result": {"nct_ids": [seed], "status": "INSUFFICIENT_SCOPE_FOR_GROUP_QUESTION",
                 "meaning": "Exact lookup supplies seed facts, not a community membership query."},
             "community_aware_result": {"community_id": group["community_id"], "nct_ids": ids,
                 "status": "COMPLETE_FOR_DECLARED_PILOT_SCOPE" if not skipped else "PARTIAL_FOR_DECLARED_PILOT_SCOPE",
                 "primary_outcome_records": primary, "per_trial_listings": community, "skipped": skipped,
                 "omitted_full_cohort_nct_ids": group["omitted_full_cohort_nct_ids"]}},
            {"id": "P3", "question": "Across the three pilot groups, how many distinct trials register primary, secondary or other planned outcomes, and what time-frame information is missing?",
             "exact_trial_result": {"nct_ids": [seed], "status": "INSUFFICIENT_SCOPE_FOR_GROUP_QUESTION"},
             "community_aware_result": {"status": "COMPLETE_FOR_DECLARED_PILOT_SCOPE", "groups": stats,
                 "supporting_evidence_ids": sorted(r["evidence_id"] for p in prepared.values() for r in p["trials"][0]["categories"]["planned_outcomes"])}}
        ], "controls": [
            {"id": "NEGATIVE_UNKNOWN", "nct_id": "NCT99999999", "result": listing(source, "NCT99999999")},
            {"id": "NEGATIVE_MISSING_SOURCE", "nct_id": "NCT00000475", "outside_pilot": True, "result": listing(source, "NCT00000475")},
            {"id": "NEGATIVE_EFFECTIVENESS", "result": listing(source, seed, question=f"Did spironolactone improve survival in {seed}?")},
            {"id": "NEGATIVE_PAGINATION", "nct_id": seed, "result": listing(source, seed, limit=5)}
        ], "safeguards": [api.PLANNED_SAFEGUARD, api.SNAPSHOT_SAFEGUARD],
        "comparison_limitation": "Different query scopes, not a relevance/accuracy benchmark. Existing search_trials can already find registered entity matches; communities cache/expose an auditable scope, not a newly proven retrieval capability."}


class Figure:
    """Same data drawing commands produce a PNG and an editable SVG asset."""
    def __init__(self, width, height):
        from PIL import Image, ImageDraw
        self.im = Image.new("RGB", (width, height), "white")
        self.draw = ImageDraw.Draw(self.im)
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>']
    def line(self, xy, color="#9CA3AF", width=2, dashed=False):
        self.svg.append(f'<line x1="{xy[0]}" y1="{xy[1]}" x2="{xy[2]}" y2="{xy[3]}" stroke="{color}" stroke-width="{width}"'+(' stroke-dasharray="9 9"' if dashed else '')+'/>')
        if not dashed:
            self.draw.line(xy, fill=color, width=width)
        else:
            dx, dy = xy[2]-xy[0], xy[3]-xy[1]
            length = math.hypot(dx, dy)
            for i in range(0, int(length), 18):
                a, b = i/length, min(i+9, length)/length
                self.draw.line((xy[0]+a*dx, xy[1]+a*dy, xy[0]+b*dx, xy[1]+b*dy), fill=color, width=width)
    def rect(self, xy, fill, outline=None):
        self.draw.rectangle(xy, fill=fill, outline=outline, width=2)
        self.svg.append(f'<rect x="{xy[0]}" y="{xy[1]}" width="{xy[2]-xy[0]}" height="{xy[3]-xy[1]}" fill="{fill}" stroke="{outline or fill}" stroke-width="2"/>')
    def text(self, xy, value, *, size=30, color="#182B49", anchor="left"):
        from PIL import ImageFont
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", size)
        # Pillow uses top anchoring; SVG uses a matching approximate baseline.
        self.draw.text(xy, value, font=font, fill=color, anchor="mt" if anchor == "middle" else "lt")
        self.svg.append(f'<text x="{xy[0]}" y="{xy[1]+size*.82}" font-family="Arial, sans-serif" font-size="{size}" fill="{color}" text-anchor="'+('middle' if anchor == 'middle' else 'start')+'">'+escape(value)+'</text>')
    def save(self, base):
        self.im.save(str(base)+".png")
        Path(str(base)+".svg").write_text("\n".join(self.svg)+"\n</svg>\n", encoding="utf-8")


def figures(groups, results, output):
    colors = ("#007F86", "#5E52A3", "#C46B22")
    f = Figure(2400, 1420)
    f.text((80, 60), "HeartTrialTwin: three rule-defined trial communities", size=52)
    f.text((80, 135), "Actual pinned CSV records | 15 trials | NOT Leiden-detected communities", size=31)
    hf = (1200, 280)
    positions = {}
    for index, group in enumerate(groups):
        cx, cy = 410+index*790, 780
        for j, nct in enumerate(group["member_nct_ids"]):
            angle = -math.pi/2+j*2*math.pi/5
            positions[nct] = (cx+270*math.cos(angle), cy+235*math.sin(angle))
    for point in positions.values():
        f.line((*hf, *point), "#D5DBE3", 2)
    for index, group in enumerate(groups):
        cx, cy = 410+index*790, 780
        for a, b in itertools.combinations(group["member_nct_ids"], 2):
            f.line((*positions[a], *positions[b]), "#B7BDD0", 2, dashed=True)
        for nct in group["member_nct_ids"]:
            f.line((cx, cy, *positions[nct]), colors[index], 4)
        f.text((cx, 395), group["community_id"]+" / "+group["intervention_name"], size=36, anchor="middle", color=colors[index])
        f.text((cx, 449), f"5 shown of {group['qualifying_full_cohort_trials']} qualifying trials", size=26, anchor="middle")
        f.rect((cx-135, cy-40, cx+135, cy+50), "#EFF7F7", colors[index])
        f.text((cx, cy-22), "Registered DRUG", size=26, anchor="middle")
        f.text((cx, cy+14), "source intervention", size=24, anchor="middle")
    for nct, (x, y) in positions.items():
        f.rect((x-130, y-28, x+130, y+36), "#FFFFFF", "#354965")
        f.text((x, y-13), nct, size=29, anchor="middle")
    f.rect((hf[0]-310, hf[1]-39, hf[0]+310, hf[1]+43), "#F1F4F8", "#A8B4C2")
    f.text((hf[0], hf[1]-18), 'Submitted condition: "Heart Failure"', size=30, anchor="middle")
    f.line((100, 1150, 230, 1150), "#007F86", 5); f.text((255, 1130), "Solid colored: verified intervention association", size=29)
    f.line((1230, 1150, 1360, 1150), "#AAB5C5", 3); f.text((1385, 1130), "Solid gray: verified submitted condition", size=29)
    f.line((100, 1215, 230, 1215), "#B7BDD0", 3, dashed=True); f.text((255, 1195), "Dashed: derived co-membership; not a registered trial-to-trial link", size=29)
    f.text((80, 1295), "HTT-P1-AACT-20260905 | Snapshot 2026-09-05 | Groups use exact source labels; no clinical equivalence inferred.", size=27)
    f.text((80, 1340), api.PLANNED_SAFEGUARD, size=29)
    f.save(output/"community_graph")

    stats = results["questions"][2]["community_aware_result"]["groups"]
    f = Figure(2200, 1240)
    f.text((80, 60), "What the pilot trials planned to measure", size=52)
    f.text((80, 135), "Distinct trials with a registered outcome of each type (not clinical results)", size=32)
    for j, kind in enumerate(("primary", "secondary", "other")):
        x0 = 120+j*700
        f.text((x0, 265), kind.capitalize()+" outcomes", size=36)
        for k in range(6):
            x = x0+k*100
            f.line((x, 335, x, 805), "#E6EAF0", 2)
            f.text((x, 824), str(k), size=25, anchor="middle")
        for index, row in enumerate(stats):
            y = 370+index*145
            count = row["distinct_trials_by_type"][kind]
            f.rect((x0, y, x0+count*100, y+65), colors[index])
            f.text((x0+count*100+15, y+14), str(count)+"/5", size=29)
            f.text((x0, y-36), row["intervention"], size=27)
    f.text((100, 930), "Outcome records / blank time frames (all preserved):", size=32)
    for index, row in enumerate(stats):
        f.text((100, 990+index*50), f"{row['community_id']} {row['intervention']}: {row['planned_outcome_records']} records; {row['blank_time_frame_records']} blank time frames.", size=29)
    f.text((100, 1170), "Snapshot 2026-09-05 | Same trial may register multiple types; bars are not mutually exclusive.", size=27)
    f.save(output/"planned_outcome_chart")


def validate_output(output):
    manifest = json.loads((output/"pilot_manifest.json").read_text())
    require(manifest["source_manifest_sha256"] == api.MANIFEST_SHA256, "Output/source identity mismatch")
    for name, expected in manifest["output_sha256"].items():
        require(sha(output/name) == expected, "Output checksum mismatch: "+name)
    groups = json.loads((output/"communities.json").read_text())["communities"]
    memberships = json.loads((output/"membership_evidence.json").read_text())
    sources = json.loads((output/"trial_evidence.json").read_text())
    ids = sorted({n for g in groups for n in g["member_nct_ids"]})
    require(ids == sorted(sources) and len(memberships) == 15, "Output membership mismatch")
    all_citations = {c["citation_id"]: c for p in sources.values() for c in p["citations"]}
    for row in memberships:
        require(set(row["citation_ids"]) <= set(all_citations), "Missing membership citation")
        require(all(all_citations[c]["nct_id"] == row["nct_id"] for c in row["citation_ids"]), "Cross-trial citation")
    outcomes = [r for p in sources.values() for r in p["trials"][0]["categories"]["planned_outcomes"]]
    require(len(outcomes) == len({r["evidence_id"] for r in outcomes}) == manifest["counts"]["planned_outcome_records"], "Outcome evidence mismatch")
    require(all(hashlib.sha256(Path(ROOT/name).read_bytes()).hexdigest() == value for name, value in manifest["protected_sha256"].items()), "Protected artifact changed")
    return {"status": "PASS", "output_files_verified": len(manifest["output_sha256"]),
            "trial_count": len(ids), "planned_outcome_records": len(outcomes), "membership_citations_valid": True}


def run(output):
    require(not output.exists(), "Output exists; use --validate-only, not regeneration")
    started = time.perf_counter()
    protected = {name: sha(ROOT/name) for name in PROTECTED}
    source = CsvEvidence()
    groups, ids = select_pilot(source)
    prepared = {n: source.prepared(n) for n in ids}
    members = [membership_evidence(source, g, n) for g in groups for n in g["member_nct_ids"]]
    algorithm = detect(groups, ids)
    results = comparisons(source, groups, prepared)
    alternatives = alternative_audits(prepared)
    require(protected == {n: sha(ROOT/n) for n in protected}, "Protected file modified")
    output.mkdir(parents=True)
    write_json(output/"communities.json", {"version": VERSION, "communities": groups, "pilot_nct_ids": ids,
        "selection": {"condition": "Exact normalized submitted heart failure", "intervention_type": "DRUG",
            "excluded": "Contains placebo or exact generic names in the script; no synonym/class mapping",
            "ordering": "Group size descending, intervention normalized name, stable ID; first five lexicographic NCT IDs per group",
            "outcome_availability_used": False, "prediction_or_terminal_status_used": False,
            "scope": "15-trial bounded convenience demonstration; not a representative or full-cohort community census"}})
    write_json(output/"membership_evidence.json", members)
    write_json(output/"trial_evidence.json", prepared)
    write_json(output/"derived_edges.json", projection(groups))
    write_json(output/"label_propagation_comparison.json", algorithm)
    write_json(output/"alternative_groupings.json", alternatives)
    write_json(output/"retrieval_comparison.json", results)
    figures(groups, results, output)
    stats = results["questions"][2]["community_aware_result"]["groups"]
    sources = {"source_manifest_sha256": api.MANIFEST_SHA256, "source_file_sha256": source.verified_hashes,
        "original_source_relationships": [r for row in members for r in row["source_evidence_ids"]],
        "evidence_access": "Local pinned CSV only; no Neo4j/Ollama call", "code_sha256": sha(__file__)}
    write_json(output/"source_provenance.json", sources)
    manifest = {"version": VERSION, "dataset_version": api.DATASET, "graph_version": api.GRAPH,
        "snapshot_date": api.SNAPSHOT, "source_manifest_sha256": api.MANIFEST_SHA256,
        "source_checksums_passed": len(source.verified_hashes), "protected_sha256": protected,
        "counts": {"trials": len(ids), "rule_communities": len(groups),
            "planned_outcome_records": sum(s["planned_outcome_records"] for s in stats),
            "derived_projection_edges": len(projection(groups)), "membership_proof_records": len(members)},
        "generation": {"model_attempts": 0, "embedding_generation": False},
        "environment": {"python": sys.version.split()[0], "networkx": importlib.metadata.version("networkx"),
                        "pillow": importlib.metadata.version("pillow")},
        "output_sha256": {p.name: sha(p) for p in sorted(output.iterdir()) if p.is_file()},
        "measured_runtime_seconds": round(time.perf_counter()-started, 6),
        "limitations": ["Offline source retrieval, not live Neo4j", "Rule-selected cliques make detection agreement circular",
            "Not a benchmark of retrieval accuracy", "No inferred clinical efficacy or endpoint equivalence",
            "No semantic outcome communities, Leiden execution, global LLM synthesis or Streamlit implementation"]}
    write_json(output/"pilot_manifest.json", manifest)
    print(json.dumps(validate_output(output), sort_keys=True))
    print(json.dumps({"runtime_seconds": manifest["measured_runtime_seconds"], "counts": manifest["counts"],
                      "output": str(output)}, sort_keys=True))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--validate-only", action="store_true")
    args = p.parse_args()
    output = args.output.resolve()
    require(output.is_relative_to(Path(__file__).resolve().parent), "Outputs must remain inside isolated pilot directory")
    if args.validate_only:
        CsvEvidence()  # Reverify the pinned source without writing or contacting a service.
        print(json.dumps(validate_output(output), sort_keys=True))
    else:
        run(output)


if __name__ == "__main__":
    main()
