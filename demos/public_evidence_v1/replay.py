"""Standard-library replay of three already-public, checksum-pinned traces.

No project imports, database/model calls, credentials, or third-party packages.
Trust anchors bind to reviewed public main b57afc6, not a mutable local manifest.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = Path("full_cohort_graphrag/semantic_v1/demo_v2/validation/HTT-DEMO-v2-SMOKE-v1")
PUBLIC_COMMIT = "b57afc6f0bfd24f3821c19bba9221c2b8ec8d471"
NCT = "NCT00206232"
DATASET = "HTT-P1-AACT-20260905"
GRAPH = "HTT-KG-AACT-20260905-FULL2824-v1"
SNAPSHOT = "2026-09-05"
GRAPH_MANIFEST = "3ef82624d131b36abc1eb9ad4e89b3439fed9f9600b92262c21bbcbfe6cf8757"
MANIFEST_SHA256 = "37cb033b70248493f2df16de163a831a18042f15c5eae5eb8dee663754c92bb0"
FILES = {
    "01_sponsor.json": "e16ff47e33f5b3063706e0bf974eeea43dfdc2843c0dbb74474cd0b077f1f7b5",
    "02_intervention.json": "02d28e838c7138ed7a7f4224a6d8202f4b38bead92d1848ebdda22974f09a73f",
    "03_outcomes.json": "c48966909d1eda95481709d8188a67c154b0a7a663fb5e23527599c508c4eeab",
}
SPECS = {
    "sponsor": ("01_sponsor.json", "lead_sponsors", "LEAD_SPONSORED_BY", "sponsors.txt", "name", 1),
    "intervention": ("02_intervention.json", "interventions", "HAS_INTERVENTION", "interventions.txt", "name", 1),
    "outcomes": ("03_outcomes.json", "planned_outcomes", "HAS_PLANNED_OUTCOME", "design_outcomes.txt", "measure", 7),
}
NOTICE = "Saved-evidence replay — not live GraphRAG, model generation, or prospective prediction."
PLANNED = "Registered planned outcomes are not observed clinical results."
AMENDMENTS = "September 5, 2026 snapshot values may include amendments; original-registration availability is not asserted."


class IntegrityError(ValueError):
    """Fail closed; never publish facts after source/association failure."""


def require(value, message):
    if not value:
        raise IntegrityError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(value):
    return hashlib.sha256(value).hexdigest()


def read_pinned(path, expected):
    try:
        require(path.is_file() and path.stat().st_size <= 2_000_000, "Missing/oversized public evidence")
        raw = path.read_bytes()
        require(sha(raw) == expected, "Public evidence checksum mismatch")
        return json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IntegrityError("Public evidence cannot be read") from exc


def identity(value):
    require((value.get("dataset_version"), value.get("graph_version"), value.get("snapshot_date"))
            == (DATASET, GRAPH, SNAPSHOT), "Snapshot identity mismatch")


def validate_records(prepared, raw, kind):
    """Check ownership and actual record/citation equality, not text matching."""
    _, category, relationship_type, source_table, field, expected = SPECS[kind]
    identity(prepared)
    require(prepared["manifest_sha256"] == GRAPH_MANIFEST, "Graph manifest mismatch")
    require(prepared["completeness"]["complete_evidence"] is True
            and not prepared["completeness"]["pagination_limited"]
            and not prepared["completeness"]["missing_source_records"], "Incomplete saved evidence")
    trials = prepared["trials"]
    require(len(trials) == 1 and trials[0]["nct_id"] == NCT, "Wrong prepared trial")
    require(raw["status"] == "COMPLETE" and raw["nct_id"] == NCT
            and raw["pagination"]["all_evidence_returned"] is True
            and raw["pagination"]["total"] == raw["pagination"]["returned"] == 14,
            "Incomplete retrieval trace")
    records = trials[0]["categories"][category]
    require(len(records) == expected, "Incomplete evidence listing")
    require(len({r["evidence_id"] for r in records}) == expected, "Duplicate source evidence")
    citations = {r["citation_id"]: r for r in prepared["citations"]}
    raw_records = {r["evidence_id"]: r for r in raw["evidence"]}
    verified = []
    for record in records:
        props, rel = record["properties"], record["relationship"]
        eid = f"{NCT}|{relationship_type}|{record['node_id']}"
        require(record["nct_id"] == NCT and record["evidence_id"] == eid
                and record["category"] == category, "Evidence ownership mismatch")
        require(rel["start_id"] == NCT and rel["end_id"] == record["node_id"]
                and rel["type"] == relationship_type, "Relationship ownership mismatch")
        require(props["dataset_version"] == rel["properties"]["dataset_version"] == DATASET
                and props["source_table"] == source_table and props.get(field), "Missing source value")
        original = raw_records.get(eid)
        require(original is not None and all(original[k] == record[k] for k in
                ["nct_id", "node_id", "node_label", "properties", "relationship", "source_references"]),
                "Prepared record differs from raw retrieval")
        refs = record["source_references"]
        require(refs and len(refs) == len(record["citation_ids"]), "Missing citation binding")
        bound = []
        for ref, cid in zip(refs, record["citation_ids"]):
            require(ref["nct_id"] == NCT and ref["source_table"] == source_table
                    and ref["source_record_id"], "Source reference mismatch")
            sid = ref["source_record_id"]
            ids = rel["properties"].get("source_record_ids", rel["properties"].get("source_record_id", "")).split(";")
            require(sid in ids, "Relationship source record mismatch")
            expected_cid = "cite:" + sha(canonical([GRAPH, NCT, source_table, sid, eid]).encode())[:24]
            cite = citations.get(cid)
            require(cid == expected_cid and cite is not None, "Invalid citation identifier")
            identity(cite)
            require(cite["nct_id"] == NCT and cite["evidence_id"] == eid and cite["source_record_id"] == sid
                    and cite["source_table"] == source_table and cite["relationship"] == rel
                    and cite["manifest_sha256"] == GRAPH_MANIFEST, "Citation association mismatch")
            bound.append(copy.deepcopy(cite))
        verified.append({"kind": kind, "nct_id": NCT, "evidence_id": eid, "node_id": record["node_id"],
                         "value": props[field], "outcome_type": props.get("outcome_type"),
                         "time_frame": props.get("time_frame"), "relationship": copy.deepcopy(rel),
                         "citations": bound})
    return sorted(verified, key=lambda r: r["evidence_id"])


def load_evidence(root=ROOT):
    """Read only three published traces and their existing checksum manifest."""
    folder = Path(root) / SOURCE
    manifest = read_pinned(folder / "manifest.json", MANIFEST_SHA256)
    require(all(manifest["files_sha256"][k] == v for k, v in FILES.items()), "Published pins mismatch")
    result = {}
    for kind, (name, *_rest) in SPECS.items():
        trace = read_pinned(folder / name, FILES[name])
        identity(trace)
        require(trace["selected_nct_ids"] == [NCT] and trace["model_attempts"] == 0, "Wrong trace scope")
        require(trace["status"] == ("COMPLETE_LISTING" if kind == "outcomes" else "GROUNDED"), "Unverified trace")
        require(len(trace["trial_results"]) == 1, "Unexpected trace trials")
        trial = trace["trial_results"][0]
        answer, prepared = trial["answer_trace"], trial["prepared_evidence"]
        require(answer["validation"]["passed"] is True and answer["model_generated"] is False,
                "Saved validation did not pass")
        require(sha(canonical(prepared).encode()) == answer["prepared_evidence_sha256"], "Prepared evidence hash mismatch")
        records = validate_records(prepared, trial["raw_retrieval"], kind)
        audited = trace["independent_audit"]["checked_facts"]
        require(trace["independent_audit"]["citation_validity"] == "PASS"
                and {f["evidence_id"] for f in audited} == {r["evidence_id"] for r in records}, "Audit source set mismatch")
        if kind == "outcomes":
            listed = answer["listed_outcomes"]
            require(answer["validation"]["complete_source_set"] is True and len(listed) == 7
                    and {r["evidence_id"] for r in listed} == {r["evidence_id"] for r in records},
                    "Incomplete saved planned-outcome listing")
            catalog = answer["fact_catalog"]["entries"]
        for record in records:
            fact = next(f for f in audited if f["evidence_id"] == record["evidence_id"])
            require(fact["nct_id"] == NCT and fact["value"] == record["value"]
                    and fact["citation_ids"] == [c["citation_id"] for c in record["citations"]], "Audit fact mismatch")
            if kind == "outcomes":
                saved = next(r for r in listed if r["evidence_id"] == record["evidence_id"])
                require(saved["properties"] == next(r for r in prepared["trials"][0]["categories"]["planned_outcomes"]
                                                   if r["evidence_id"] == record["evidence_id"])["properties"], "Outcome values changed")
                entry = catalog[saved["fact_id"]]
                require(entry["fact"] == fact and entry["sentence"] == saved["sentence"], "Catalog fact binding mismatch")
                record["sentence"] = saved["sentence"]
            else:
                lines = [line for line in answer["answer"].splitlines() if line.startswith(f"For {NCT},")]
                require(len(lines) == 1 and f'"{record["value"]}"' in lines[0]
                        and all(f'[{c["citation_id"]}]' in lines[0] for c in record["citations"]), "Saved sentence mismatch")
                record["sentence"] = lines[0]
        result[kind] = records
    return {"schema_version": "HTT-PUBLIC-EVIDENCE-REPLAY-v1", "mode": "SAVED_EVIDENCE_REPLAY",
            "nct_id": NCT, "dataset_version": DATASET, "graph_version": GRAPH, "snapshot_date": SNAPSHOT,
            "graph_manifest_sha256": GRAPH_MANIFEST, "notice": NOTICE, "safeguards": [PLANNED, AMENDMENTS, "Research only; not clinical advice."],
            "source_commit": PUBLIC_COMMIT, "source_directory": str(SOURCE),
            "source_manifest_sha256": MANIFEST_SHA256, "source_trace_sha256": dict(FILES), "records": result}


def replay(question=None, *, field=None, nct_id=NCT, root=ROOT):
    try:
        evidence = load_evidence(root)
        if question is not None:
            if not isinstance(question, str) or len(question) > 500:
                return {"status": "ABSTAIN", "reason": "Unsupported request", "records": []}
            q = " ".join(question.strip().split())
            templates = {
                "sponsor": r"Who is the registered lead sponsor for (NCT\d{8})\?",
                "intervention": r"What intervention is registered for (NCT\d{8})\?",
                "outcomes": r"What planned outcomes were registered for (NCT\d{8})\?",
            }
            matched = [(k, re.fullmatch(v, q, re.IGNORECASE)) for k, v in templates.items()]
            hit = next(((k, m) for k, m in matched if m), None)
            if hit is None:
                return {"status": "ABSTAIN", "reason": "Only three declared registered-information templates are supported; no effectiveness/results claims.", "notice": NOTICE, "records": []}
            field, match = hit
            nct_id = match.group(1).upper()
        if not isinstance(nct_id, str) or re.fullmatch(r"NCT\d{8}", nct_id) is None:
            return {"status": "INVALID_INPUT", "reason": "Use a valid NCT identifier", "records": []}
        if nct_id != NCT:
            return {"status": "NOT_FOUND", "reason": "This replay contains only NCT00206232; no statement about other trials is implied.", "records": []}
        if field not in SPECS:
            return {"status": "ABSTAIN", "reason": "Unsupported evidence field", "records": []}
        records = evidence["records"][field]
        return {**{k: v for k, v in evidence.items() if k != "records"}, "status": "COMPLETE_LISTING" if field == "outcomes" else "VERIFIED_REPLAY",
                "field": field, "records": records, "record_count": len(records), "model_attempts": 0,
                "answer": "\n".join([NOTICE, *(r["sentence"] for r in records), PLANNED, AMENDMENTS, "Research only; not clinical advice."])}
    except (IntegrityError, KeyError, TypeError, IndexError, StopIteration) as exc:
        # No paths, configuration or raw exception text enters public responses.
        return {"status": "INTEGRITY_ERROR", "reason": "Public evidence is missing, tampered, incomplete, or incorrectly associated; no answer published.", "records": []}


def main():
    parser = argparse.ArgumentParser(description=NOTICE)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--field", choices=list(SPECS))
    choice.add_argument("--question")
    parser.add_argument("--nct-id", default=NCT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = replay(args.question, field=args.field, nct_id=args.nct_id)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result.get("answer", result["status"] + ": " + result.get("reason", "")))
    return 2 if result["status"] == "INTEGRITY_ERROR" else 0


if __name__ == "__main__": sys.exit(main())
