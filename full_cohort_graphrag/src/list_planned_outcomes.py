"""Explicit offline complete listing; never an Ollama retry, repair or fallback."""

from __future__ import annotations

import copy
import time
from datetime import datetime, timezone

from . import retrieve as api
from .generate_answer import (
    CATALOG_VERSION, MAX_QUESTION_CHARACTERS, GenerationInputError,
    build_fact_catalog, build_fact_id_catalog, classify_question, digest,
    validate_prepared,
)


SCHEMA_VERSION = "HTT-FULL-DETERMINISTIC-OUTCOMES-v1"
POLICY_VERSION = "HTT-FULL-COMPLETE-OUTCOME-LISTING-v1"
MAX_OUTCOMES = api.MAX_PAGE_SIZE  # 200; cannot authorize fetching another page.
MAX_ANSWER_BYTES = 50_000  # Complete listing UTF-8 bytes, including disclaimers.
REASONS = {
    "UNSUPPORTED_LISTING_QUESTION": "Only supported registered planned-outcome questions can use this entry point.",
    "SINGLE_TRIAL_LISTING_REQUIRED": "Name exactly one NCT ID and supply evidence scoped to that trial only.",
    "QUESTION_SCOPE_MISMATCH": "The requested trial does not match the supplied evidence scope.",
    "NOT_FOUND": "Requested trial evidence was not found in the pinned graph.",
    "PAGINATION_LIMITED": "Other evidence pages are outside the supplied response; no pages were fetched.",
    "MISSING_SOURCE_RECORDS": "The supplied evidence has missing source categories.",
    "INCOMPLETE_EVIDENCE": "The supplied evidence is incomplete.",
    "INCOMPLETE_RELEVANT_VALUES": "A registered planned outcome lacks a usable measure; no partial list is published.",
    "LISTING_SOURCE_SET_MISMATCH": "The catalog does not match the complete expected outcome evidence-ID set.",
    "LISTING_CITATION_MISMATCH": "An outcome catalog fact does not match its trial-bound source citation.",
    "LISTING_OUTPUT_LIMIT_EXCEEDED": "The complete listing exceeds the output policy; no partial list is published.",
}


def list_registered_planned_outcomes(question, prepared, *, contract=None,
                                   max_outcomes=MAX_OUTCOMES, max_answer_bytes=MAX_ANSWER_BYTES):
    """Return a complete, source-checked listing trace, or controlled abstention.

    Explicit opt-in, one named trial, validated prepared evidence only. Optional
    limits may lower, not raise, the hard caps. Limits apply to the full listing,
    not the fixed abstention notice or separately retained audit evidence.
    Invalid caller inputs raise GenerationInputError, as in the Ollama wrapper.
    """
    if not isinstance(question, str) or not question.strip() or len(question) > MAX_QUESTION_CHARACTERS:
        raise GenerationInputError("Question must be nonblank text of at most 2000 characters")
    if (type(max_outcomes) is not int or not 1 <= max_outcomes <= MAX_OUTCOMES
            or type(max_answer_bytes) is not int or not 1 <= max_answer_bytes <= MAX_ANSWER_BYTES):
        raise GenerationInputError("Listing limits must be positive integers within the documented hard caps")
    validate_prepared(prepared, contract or api.load_contract())
    bundle = copy.deepcopy(prepared)
    started = time.perf_counter()
    relevance = classify_question(question)
    trace = {
        "schema_version": SCHEMA_VERSION, "listing_policy_version": POLICY_VERSION,
        "answer_origin": "DETERMINISTIC_VERIFIED_EVIDENCE", "model_generated": False,
        "started_utc": datetime.now(timezone.utc).isoformat(), "question": question,
        "status": "ABSTAIN", "answer": "", "raw_model_output": None,
        "dataset_version": bundle["dataset_version"], "graph_version": bundle["graph_version"],
        "snapshot_date": bundle["snapshot_date"], "scope": bundle["scope"],
        "prepared_evidence_sha256": digest(bundle), "summary_sha256": bundle["summary_sha256"],
        "verified_evidence": bundle, "deterministic_evidence_summary": bundle["summary"],
        "source_references": bundle["citations"], "listed_outcomes": [],
        "generation": {"provider": None, "requested_model": None, "actual_model": None,
                       "attempts": 0, "maximum_attempts": 0, "latency_ms": None,
                       "prompt_eval_count": None, "eval_count": None},
        "validation": {"passed": False, "errors": [], "complete_source_set": False,
                       "expected_evidence_ids": [], "listed_evidence_ids": [],
                       "listed_fact_ids": [], "citation_ids": [],
                       "relevance": {**relevance, "status": "NOT_ESTABLISHED",
                                     "general_semantic_relevance_checked": False}},
        "limits": {"max_outcomes": max_outcomes, "max_answer_bytes": max_answer_bytes,
                   "required_answer_bytes": None},
        "safeguards": [api.PLANNED_SAFEGUARD, api.SNAPSHOT_SAFEGUARD],
    }

    def finish(errors, *, rows=None, answer=None):
        trace["validation"]["errors"] = errors
        if errors:
            trace["answer"] = "ABSTAIN: " + " ".join(REASONS[code] for code in errors) + " Verified evidence is retained separately."
        else:
            trace.update(status="COMPLETE_LISTING", answer=answer, listed_outcomes=rows)
            trace["validation"].update(passed=True, complete_source_set=True,
                listed_evidence_ids=[row["evidence_id"] for row in rows],
                listed_fact_ids=[row["fact_id"] for row in rows],
                citation_ids=sorted({key for row in rows for key in row["citation_ids"]}))
            trace["validation"]["relevance"]["status"] = "PASSED_FIELD_SCOPE_CHECKS"
        trace["completed_utc"] = datetime.now(timezone.utc).isoformat()
        trace["total_latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
        return trace

    if relevance["classification"] != "CLASSIFIED" or relevance["permitted_fields"] != ["planned outcome measure"]:
        return finish(["UNSUPPORTED_LISTING_QUESTION"])
    requested = relevance["requested_nct_ids"]
    if len(requested) != 1:
        return finish(["SINGLE_TRIAL_LISTING_REQUIRED"])
    nct = requested[0]
    if nct not in bundle["scope"]["selected_nct_ids"]:
        return finish(["QUESTION_SCOPE_MISMATCH"])
    if bundle["scope"]["selected_nct_ids"] != [nct] or len(bundle["trials"]) != 1:
        return finish(["SINGLE_TRIAL_LISTING_REQUIRED"])
    completeness = bundle["completeness"]
    errors = []
    if bundle["retrieval_status"] == "NOT_FOUND" or completeness["not_found_nct_ids"]:
        errors.append("NOT_FOUND")
    if completeness["pagination_limited"]:
        errors.append("PAGINATION_LIMITED")
    if completeness["missing_source_records"]:
        errors.append("MISSING_SOURCE_RECORDS")
    if not completeness["complete_evidence"] and not errors:
        errors.append("INCOMPLETE_EVIDENCE")
    if errors:
        return finish(errors)

    trial = bundle["trials"][0]
    records = trial["categories"].get("planned_outcomes", [])
    expected = {row["evidence_id"]: row for row in records}
    trace["validation"]["expected_evidence_ids"] = sorted(expected)
    coverage = trial["coverage"].get("planned_outcomes", {})
    if (not records or len(expected) != len(records) or coverage.get("total") != len(records)
            or not coverage.get("all_evidence_returned")):
        return finish(["LISTING_SOURCE_SET_MISMATCH"])
    if len(records) > max_outcomes:
        return finish(["LISTING_OUTPUT_LIMIT_EXCEEDED"])
    if any(not row["properties"].get("measure", "").strip() for row in records):
        return finish(["INCOMPLETE_RELEVANT_VALUES"])

    catalog = build_fact_catalog(bundle)
    indexed = build_fact_id_catalog(catalog)
    selected = [(key, entry) for key, entry in indexed.items()
                if entry["fact"]["nct_id"] == nct and entry["fact"]["field"] == "planned outcome measure"]
    ids = [entry["fact"]["evidence_id"] for _, entry in selected]
    if len(ids) != len(set(ids)) or len(ids) != len(records) or set(ids) != set(expected):
        return finish(["LISTING_SOURCE_SET_MISMATCH"])
    trace["fact_catalog"] = {"schema_version": CATALOG_VERSION, "sha256": digest(indexed), "entries": indexed}
    references = {ref["citation_id"]: ref for ref in bundle["citations"]}
    rows = []
    # Evidence-ID order is deterministic, independent of clinical meaning.
    for key, entry in sorted(selected, key=lambda item: item[1]["fact"]["evidence_id"]):
        fact = entry["fact"]
        record = expected[fact["evidence_id"]]
        props = record["properties"]
        if fact["value"] != props["measure"] or fact["citation_ids"] != record["citation_ids"]:
            return finish(["LISTING_CITATION_MISMATCH"])
        for citation_id in fact["citation_ids"]:
            ref = references.get(citation_id, {})
            if (ref.get("nct_id") != nct or ref.get("evidence_id") != record["evidence_id"]
                    or ref.get("source_table") != "design_outcomes.txt"
                    or ref.get("source_record_id") != props["source_record_id"]
                    or ref.get("relationship") != record["relationship"]
                    or any(ref.get(field) != bundle[field] for field in
                           ("dataset_version", "graph_version", "snapshot_date", "manifest_sha256"))):
                return finish(["LISTING_CITATION_MISMATCH"])
        rows.append({**copy.deepcopy(record), "fact_id": key, "sentence": entry["sentence"],
                     "missing_optional_values": [field for field in ("outcome_type", "time_frame")
                                                 if not props.get(field, "").strip()]})

    lines = ["Deterministically assembled from verified evidence — not model-generated.",
             f"{nct}: complete registered planned-outcome listing ({len(rows)} source records)."]
    for index, row in enumerate(rows, start=1):
        lines.append(f"{index}. {row['sentence']}")
        for field in row["missing_optional_values"]:
            lines.append(f"   {field}: unavailable in the supplied evidence.")
    lines.extend([api.PLANNED_SAFEGUARD, api.SNAPSHOT_SAFEGUARD,
                  f"Dataset: {bundle['dataset_version']}; graph: {bundle['graph_version']}; snapshot: {bundle['snapshot_date']}."])
    answer = "\n".join(lines)
    trace["limits"]["required_answer_bytes"] = len(answer.encode("utf-8"))
    if trace["limits"]["required_answer_bytes"] > max_answer_bytes:
        return finish(["LISTING_OUTPUT_LIMIT_EXCEEDED"])
    return finish([], rows=rows, answer=answer)
