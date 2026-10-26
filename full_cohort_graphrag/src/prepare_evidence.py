"""Offline preparation of one existing retrieval response; no queries or LLM.

prepare_evidence(response) returns a deterministic evidence bundle, not an
answer. It never fetches another page or treats a supplied page as a full result.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter

from . import retrieve as api


MAX_RECORDS = api.MAX_TRIALS * api.MAX_PAGE_SIZE
MAX_SOURCE_CHARACTERS = 2_000_000
MAX_CITATIONS = 10_000
DEFAULT_SUMMARY_CHARACTERS = 250_000
ALL_TYPES = tuple(sorted(api.EVIDENCE_SPECS))
OUTCOME_TYPES = ("HAS_PLANNED_OUTCOME",)


class EvidencePreparationError(ValueError):
    """Inconsistent or oversized evidence is rejected, never silently trimmed."""


def require(condition, message):
    if not condition:
        raise EvidencePreparationError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r"NCT\d{8}", value) is not None,
            "Invalid trial identifier in evidence")
    return value


def page_info(value, returned, maximum):
    require(isinstance(value, dict), "Missing pagination metadata")
    require(set(value) == {"total", "returned", "limit", "offset", "has_more", "next_offset", "all_evidence_returned"},
            "Unexpected pagination fields")
    for key in ("total", "returned", "limit", "offset"):
        require(type(value.get(key)) is int and value[key] >= 0, "Invalid pagination count")
    total, limit, offset = value["total"], value["limit"], value["offset"]
    require(1 <= limit <= maximum, "Pagination limit exceeds the retrieval contract")
    require(returned == value["returned"] == min(limit, max(0, total - offset)),
            "Pagination returned count does not match supplied evidence")
    more = offset + returned < total
    complete = offset == 0 and returned == total
    require(type(value.get("has_more")) is bool and value["has_more"] == more
            and type(value.get("all_evidence_returned")) is bool
            and value["all_evidence_returned"] == complete
            and value.get("next_offset") == (offset + returned if more else None),
            "Pagination completeness/cursor metadata is inconsistent")
    return copy.deepcopy(value)


class _Preparation:
    def __init__(self, contract, max_records, max_summary_characters):
        self.contract = contract
        self.max_records = max_records
        self.max_summary_characters = max_summary_characters
        self.records = 0
        self.source_characters = 0
        self.citations = {}
        self.seen = set()

    def strings(self, value, allowed):
        require(isinstance(value, dict) and set(value) <= set(allowed), "Unexpected evidence properties")
        require(all(isinstance(v, str) for v in value.values()), "Source properties must retain string values")
        self.source_characters += sum(len(v) for v in value.values())
        require(self.source_characters <= MAX_SOURCE_CHARACTERS, "Source text budget exceeded; request a smaller scope")
        return copy.deepcopy(value)

    def envelope(self, response):
        require(isinstance(response, dict), "Retrieval response must be an object")
        require(response.get("schema_version") == "HTT-FULL-STATIC-RETRIEVAL-v1", "Unsupported retrieval schema")
        require((response.get("dataset_version"), response.get("graph_version"),
                 response.get("snapshot_date"), response.get("manifest_sha256"))
                == (api.DATASET, api.GRAPH, api.SNAPSHOT, api.MANIFEST_SHA256),
                "Retrieval snapshot/version mismatch")
        require(response.get("source_dataset") == self.contract.source, "SourceDataset provenance mismatch")
        safeguards = response.get("safeguards", {})
        require(isinstance(safeguards, dict)
                and set(safeguards) == {"planned_outcomes", "snapshot", "read_only", "no_answer_generation"}
                and safeguards.get("planned_outcomes") == api.PLANNED_SAFEGUARD
                and safeguards.get("snapshot") == api.SNAPSHOT_SAFEGUARD
                and safeguards.get("read_only") is True
                and safeguards.get("no_answer_generation") is True, "Retrieval safeguards are missing")

    def cite(self, nct, table, record_id, evidence_id, relationship):
        identity = [api.GRAPH, nct, table, record_id, evidence_id]
        key = "cite:" + hashlib.sha256(canonical(identity).encode()).hexdigest()[:24]
        value = {"citation_id": key, "nct_id": nct, "source_table": table,
                 "source_record_id": record_id, "evidence_id": evidence_id,
                 "relationship": copy.deepcopy(relationship),
                 "dataset_version": api.DATASET, "graph_version": api.GRAPH,
                 "snapshot_date": api.SNAPSHOT, "manifest_sha256": api.MANIFEST_SHA256}
        require(key not in self.citations or self.citations[key] == value, "Conflicting citation identity")
        require(key in self.citations or len(self.citations) < MAX_CITATIONS,
                "Citation budget exceeded; request a smaller scope")
        self.citations[key] = value
        return key

    def record(self, row, nct, types):
        self.records += 1
        require(self.records <= self.max_records, "Evidence record budget exceeded; request a smaller scope")
        require(isinstance(row, dict), "Evidence record must be an object")
        relationship = row.get("relationship", {})
        require(isinstance(relationship, dict), "Evidence relationship must be an object")
        rel = relationship.get("type")
        require(rel in types, "Unexpected relationship in this workflow")
        category, label, id_key, table, fields = api.EVIDENCE_SPECS[rel]
        node = row.get("node_id")
        require(isinstance(node, str) and bool(node), "Missing evidence node identifier")
        evidence_id = f"{nct}|{rel}|{node}"
        require(row.get("nct_id") == nct and relationship.get("start_id") == nct
                and relationship.get("end_id") == node and row.get("evidence_id") == evidence_id,
                "Cross-trial evidence/path association mismatch")
        require(evidence_id not in self.seen, "Duplicate evidence path")
        self.seen.add(evidence_id)
        require(row.get("category") == category and row.get("node_label") == label,
                "Evidence category/label mismatch")
        props = self.strings(row.get("properties"), (*fields, "source_table", "dataset_version"))
        rel_props = self.strings(relationship.get("properties"), api.REL_FIELDS)
        require(props.get(id_key) == node and props.get("dataset_version") == api.DATASET
                and rel_props.get("dataset_version") == api.DATASET
                and props.get("source_table") == rel_props.get("source_table") == table,
                "Evidence identifier/source provenance mismatch")
        if rel in {"HAS_SUBMITTED_CONDITION", "HAS_BROWSE_CONDITION"}:
            require(props.get("source_kind") == ("submitted" if rel == "HAS_SUBMITTED_CONDITION" else "browse"),
                    "Submitted/browse classification mismatch")
        if rel == "HAS_PLANNED_OUTCOME":
            require(props.get("nct_id") == nct
                    and props.get("source_record_id") == rel_props.get("source_record_id")
                    and props.get("evidence_safeguard") == "Registered planned outcome — not a clinical result.",
                    "Planned-outcome trial/source/safeguard mismatch")
            ids = [rel_props.get("source_record_id", "")]
        else:
            ids = rel_props.get("source_record_ids", "").split(";")
        require(ids and len(ids) <= MAX_CITATIONS and all(re.fullmatch(r"\d+", value) for value in ids)
                and len(ids) == len(set(ids)), "Missing/duplicate source-record identifiers")
        references = [{"nct_id": nct, "source_table": table, "source_record_id": value} for value in ids]
        require(row.get("source_references") == references, "Source references disagree with trial/relationship provenance")
        missing = sorted(key for key, value in props.items() if value == "")
        require(row.get("missing_fields") == missing, "Missing-field flags disagree with source values")
        safe_relationship = {"type": rel, "start_id": nct, "end_id": node, "properties": rel_props}
        return {"evidence_id": evidence_id, "nct_id": nct, "category": category,
                "node_id": node, "node_label": label, "properties": props,
                "relationship": safe_relationship, "source_references": references,
                "missing_fields": missing,
                "absent_fields": sorted(set((*fields, "source_table", "dataset_version")) - set(props)),
                "citation_ids": [self.cite(nct, table, value, evidence_id, safe_relationship) for value in ids]}

    def trial(self, value, types):
        require(isinstance(value, dict), "Trial entry must be an object")
        nct = identifier(value.get("nct_id"))
        rows = value.get("evidence")
        require(isinstance(rows, list) and len(rows) <= api.MAX_PAGE_SIZE, "Trial evidence exceeds page bounds")
        status = value.get("status")
        if status == "NOT_FOUND":
            require(nct not in self.contract.membership and value.get("trial") is None
                    and rows == [] and value.get("coverage") == {}, "Inconsistent nonexistent-trial evidence")
            return {"nct_id": nct, "retrieval_status": status, "trial": None,
                    "dataset_relationship": None, "trial_citation_ids": [], "coverage": {},
                    "categories": {}, "state": {"not_found": True, "pagination_limited": False,
                    "missing_source_categories": [], "available_record_count": 0, "prepared_record_count": 0}}
        require(nct in self.contract.membership and status in {"COMPLETE", "PARTIAL"}, "Invalid trial membership/status")
        trial = self.strings(value.get("trial"), api.TRIAL_FIELDS)
        require(trial.get("nct_id") == trial.get("trial_id") == nct
                and trial.get("dataset_version") == api.DATASET and trial.get("source_table") == "studies.txt",
                "Trial metadata association mismatch")
        path = value.get("dataset_relationship")
        require(path == {"type": "MEMBER_OF_DATASET", "properties": {"dataset_version": api.DATASET},
                         "start_id": nct, "end_id": api.DATASET}, "Trial-to-dataset provenance mismatch")
        trial_refs = []
        if trial.get("source_evidence_status") == "PRESENT":
            require(trial.get("source_record_id") == nct, "Trial source-record association mismatch")
            trial_refs.append(self.cite(nct, "studies.txt", nct, None, path))
        else:
            require(trial.get("source_evidence_status") == "MISSING_SOURCE_RECORD"
                    and trial.get("source_record_id") == "", "Invalid trial source-evidence flags")
        records = [self.record(row, nct, types) for row in rows]
        records.sort(key=lambda row: row["evidence_id"])
        categories = {api.EVIDENCE_SPECS[rel][0]: [] for rel in types}
        for record in records:
            categories[record["category"]].append(record)
        coverage = value.get("coverage")
        require(isinstance(coverage, dict) and set(coverage) == set(categories), "Coverage categories disagree with workflow")
        missing, total = [], 0
        for category in categories:
            item = coverage[category]
            require(isinstance(item, dict) and set(item) == {"total", "returned", "source_status", "all_evidence_returned"}
                    and type(item.get("total")) is int and item["total"] >= 0,
                    "Invalid coverage total")
            returned = len(categories[category])
            require(type(item.get("returned")) is int and item["returned"] == returned <= item["total"]
                    and item.get("source_status") == ("AVAILABLE" if item["total"] else "NO_LINKED_RECORD_IN_PINNED_GRAPH")
                    and type(item.get("all_evidence_returned")) is bool
                    and item["all_evidence_returned"] == (returned == item["total"]), "Coverage completeness is inconsistent")
            total += item["total"]
            if not item["total"]:
                missing.append(category)
        page = value.get("pagination")
        if page is not None:
            page = page_info(page, len(rows), api.MAX_PAGE_SIZE)
            require(page["total"] == total, "Pagination total disagrees with category coverage")
            expected_status = "COMPLETE" if not missing and page["all_evidence_returned"] else "PARTIAL"
        else:
            expected_status = "COMPLETE" if not missing and len(rows) == total else "PARTIAL"
        require(status == expected_status, "Trial status falsely represents evidence completeness")
        if not trial_refs:
            missing.append("trial_source_record")
        return {"nct_id": nct, "retrieval_status": status, "trial": trial,
                "dataset_relationship": copy.deepcopy(path), "trial_citation_ids": trial_refs,
                "coverage": copy.deepcopy(coverage), "categories": categories,
                "state": {"not_found": False, "pagination_limited": len(rows) < total,
                          "missing_source_categories": sorted(missing),
                          "available_record_count": total, "prepared_record_count": len(rows)}}

    def summarize(self, workflow, trials, completeness, page):
        lines, size = [], 0
        def add(text):
            nonlocal size
            size += len(text) + 1
            require(size <= self.max_summary_characters, "Summary budget exceeded; request a smaller scope")
            lines.append(text)
        def display(properties, key):
            return json.dumps(properties[key], ensure_ascii=False) if key in properties else "<not supplied>"
        add("Verified retrieval evidence — deterministic summary, not an LLM answer.")
        add(f"Dataset: {api.DATASET}; graph: {api.GRAPH}; snapshot: {api.SNAPSHOT}.")
        add(api.PLANNED_SAFEGUARD)
        add(api.SNAPSHOT_SAFEGUARD)
        add(f"Workflow: {workflow}; pagination-limited: {completeness['pagination_limited']}; response records/trials: {page['returned']}/{page['total']}.")
        if completeness["pagination_limited"]:
            add("Only supplied pages are represented. Missing page content is not evidence of absent source records.")
        if not trials:
            add("No matching trial was returned in this search page; see matching-trial totals and pagination.")
        for entry in trials:
            nct = entry["nct_id"]
            if entry["state"]["not_found"]:
                add(f"{nct}: NOT_FOUND in the pinned cohort; no trial facts asserted.")
                continue
            trial = entry["trial"]
            add(f"{nct}: title={display(trial, 'brief_title')}; study_type={display(trial, 'study_type')}; phase={display(trial, 'phase')}. "
                + " ".join(f"[{ref}]" for ref in entry["trial_citation_ids"]))
            for category, records in entry["categories"].items():
                coverage = entry["coverage"][category]
                add(f"  {category}: {coverage['returned']} supplied / {coverage['total']} linked records.")
                if coverage["total"] == 0:
                    add("    No linked record found in the pinned graph; not proof the information never existed.")
                elif coverage["returned"] == 0:
                    add("    Records exist but are not included in this page.")
                for record in records:
                    props = record["properties"]
                    if category == "planned_outcomes":
                        text = f"Registered planned measure={display(props, 'measure')}; type={display(props, 'outcome_type')}; time_frame={display(props, 'time_frame')}"
                    else:
                        text = f"Registered name={display(props, 'name')}"
                        field_name = "intervention_type" if category == "interventions" else "agency_class" if category == "lead_sponsors" else "source_kind"
                        text += f"; {field_name}={display(props, field_name)}"
                    refs = "; ".join(f"{r['source_table']}#{r['source_record_id']}" for r in record["source_references"])
                    add(f"    {text}; sources={refs}. " + " ".join(f"[{ref}]" for ref in record["citation_ids"]))
        if workflow == "planned_outcome_comparison":
            add("Measures, types and time frames are shown per trial; no clinical equivalence or treatment effectiveness is inferred.")
        return "\n".join(lines) + "\n"


def prepare_evidence(response, *, contract=None, max_records=MAX_RECORDS,
                     max_summary_characters=DEFAULT_SUMMARY_CHARACTERS):
    """Prepare ONE retrieval response, without fetching/merging additional pages.

    Output: provenance envelope, scope/page metadata, separate completeness flags,
    trial-grouped typed records, structured citations, and deterministic summary.
    Inconsistencies or budgets raise EvidencePreparationError without partial output.
    """
    require(type(max_records) is int and 1 <= max_records <= MAX_RECORDS, "Invalid record budget")
    require(type(max_summary_characters) is int and 1 <= max_summary_characters <= 1_000_000, "Invalid summary budget")
    state = _Preparation(contract or api.load_contract(), max_records, max_summary_characters)
    state.envelope(response)
    workflow = response.get("workflow")
    require(workflow in {"trial_profile", "trial_search", "planned_outcome_comparison"}, "Unsupported workflow")
    scope_extra = {}
    if workflow == "trial_profile":
        trials = [state.trial(response, ALL_TYPES)]
        page = page_info(response.get("pagination"), trials[0]["state"]["prepared_record_count"], api.MAX_PAGE_SIZE)
        if trials[0]["state"]["not_found"]:
            require(page["total"] == 0, "Nonexistent trial has evidence counts")
        selected = [trials[0]["nct_id"]]
        expected_status = response["status"]
    elif workflow == "trial_search":
        parameters = response.get("parameters")
        require(isinstance(parameters, dict) and set(parameters) == {"dataset_version", "condition_normalized", "intervention_normalized"}
                and parameters.get("dataset_version") == api.DATASET
                and all(isinstance(parameters[key], str) and 1 <= len(parameters[key]) <= 200
                        for key in ("condition_normalized", "intervention_normalized")), "Invalid registered-entity search scope")
        require(response.get("matching_rule") == "Exact normalized submitted condition AND intervention; no synonym expansion",
                "Unsupported entity matching rule")
        scope_extra = {"search_parameters": copy.deepcopy(parameters), "matching_rule": response["matching_rule"]}
        profiles = response.get("trial_profiles")
        require(isinstance(profiles, list) and len(profiles) <= api.MAX_TRIALS, "Search trial bound exceeded")
        trials = []
        for profile in profiles:
            state.envelope(profile)
            require(profile.get("workflow") == "trial_profile", "Invalid search profile workflow")
            trials.append(state.trial(profile, ALL_TYPES))
        require(all(not trial["state"]["not_found"] for trial in trials), "Search returned a nonexistent trial")
        selected = [trial["nct_id"] for trial in trials]
        page = page_info(response.get("pagination"), len(trials), api.MAX_TRIALS)
        coverage = response.get("coverage", {})
        require(coverage == {"matching_trials": page["total"], "returned_trials": len(trials),
                             "all_matching_trial_pages_returned": page["all_evidence_returned"],
                             "all_returned_profiles_complete": all(t["retrieval_status"] == "COMPLETE" for t in trials)},
                "Search coverage disagrees with returned profiles")
        expected_status = "NOT_FOUND" if page["total"] == 0 else "COMPLETE" if page["all_evidence_returned"] and all(t["retrieval_status"] == "COMPLETE" for t in trials) else "PARTIAL"
    else:
        entries = response.get("trials")
        require(isinstance(entries, list) and 1 <= len(entries) <= api.MAX_TRIALS, "Comparison trial bound exceeded")
        trials = [state.trial(entry, OUTCOME_TYPES) for entry in entries]
        selected = response.get("selected_nct_ids")
        require(isinstance(selected, list) and sorted(selected) == sorted(t["nct_id"] for t in trials), "Comparison subset association mismatch")
        missing_ids = sorted(t["nct_id"] for t in trials if t["state"]["not_found"])
        require(response.get("not_found_nct_ids") == missing_ids, "Comparison nonexistent-trial flags disagree")
        flat = response.get("evidence")
        require(isinstance(flat, list) and len(flat) <= api.MAX_PAGE_SIZE, "Comparison evidence page bound exceeded")
        nested = [row for entry in entries for row in entry["evidence"]]
        require(sorted(canonical(row) for row in flat) == sorted(canonical(row) for row in nested),
                "Comparison top-level and per-trial evidence disagree")
        page = page_info(response.get("pagination"), len(flat), api.MAX_PAGE_SIZE)
        require(page["total"] == sum(t["state"]["available_record_count"] for t in trials), "Comparison coverage total mismatch")
        expected_status = "NOT_FOUND" if len(missing_ids) == len(trials) else "COMPLETE" if page["all_evidence_returned"] and all(t["retrieval_status"] == "COMPLETE" for t in trials) else "PARTIAL"
    require(len(selected) == len(set(selected)), "Duplicate trial entries")
    require(response.get("status") == expected_status, "Response status contradicts evidence scope")
    trials.sort(key=lambda entry: entry["nct_id"])
    not_found = [t["nct_id"] for t in trials if t["state"]["not_found"]]
    gaps = [{"nct_id": t["nct_id"], "categories": t["state"]["missing_source_categories"]}
            for t in trials if t["state"]["missing_source_categories"]]
    limited = ((page["total"] > 0 and not page["all_evidence_returned"])
               or any(t["state"]["pagination_limited"] for t in trials))
    completeness = {"prepared_all_supplied_evidence": True, "pagination_limited": limited,
                    "missing_source_records": gaps, "not_found_nct_ids": not_found,
                    "retrieval_scope_complete": not limited,
                    "source_categories_complete": bool(trials) and not gaps and not not_found,
                    "complete_evidence": response["status"] == "COMPLETE" and not limited and not gaps and not not_found,
                    "optional_blank_fields_preserved": True}
    summary = state.summarize(workflow, trials, completeness, page)
    return {"schema_version": "HTT-FULL-EVIDENCE-PREPARATION-v1", "workflow": workflow,
            "retrieval_status": response["status"], "dataset_version": api.DATASET,
            "graph_version": api.GRAPH, "snapshot_date": api.SNAPSHOT,
            "manifest_sha256": api.MANIFEST_SHA256, "source_dataset": copy.deepcopy(response["source_dataset"]),
            "scope": {"selected_nct_ids": sorted(selected), "pagination": page,
                      "pagination_unit": "trials" if workflow == "trial_search" else "evidence_paths", **scope_extra},
            "completeness": completeness, "trials": trials,
            "evidence_record_count": state.records,
            "citations": [state.citations[key] for key in sorted(state.citations)],
            "summary": summary, "summary_sha256": hashlib.sha256(summary.encode()).hexdigest(),
            "summary_field_policy": "Registered names/types; planned measures, outcome types and time frames. All supplied approved properties remain structured; descriptions/population are not repeated in prose.",
            "safeguards": copy.deepcopy(response["safeguards"]), "no_llm_answer": True}
