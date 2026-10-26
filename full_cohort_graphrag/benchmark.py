#!/usr/bin/env python3
"""Manual, read-only latency benchmark; running this module contacts local Neo4j.

Run from the repository root:
  .venv-graphrag/bin/python -B -m full_cohort_graphrag.benchmark

Uses the existing retrieval API unchanged. No LLM, ingestion, warmup, concurrent
queries, or automatic page traversal. Evidence limits are recorded explicitly.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .src import retrieve


RUNS = 3
DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent / "results"
CASES = (
    ("trial_profile", "trial_profile", {"trial_id": "NCT00206232", "limit": 50, "offset": 0}),
    ("high_volume_profile", "trial_profile", {"trial_id": "NCT05256303", "limit": 200, "offset": 0}),
    ("condition_intervention_search", "search_trials", {
        "submitted_condition": "heart failure", "intervention": "spironolactone",
        "limit": 20, "offset": 0, "evidence_limit": 50,
    }),
    ("planned_outcome_comparison", "compare_planned_outcomes", {
        "trial_ids": ["NCT00206232", "NCT00391846"], "limit": 50, "offset": 0,
    }),
)


def safe_error(exc):
    # Never serialize raw driver errors, configuration objects or credentials.
    return {"type": type(exc).__name__, "message": str(exc) if isinstance(exc, retrieve.RetrievalError)
            else "Operation failed; private exception details suppressed."}


def evidence_summary(result):
    profiles = result.get("trial_profiles")
    records = ([row for profile in profiles for row in profile["evidence"]]
               if profiles is not None else result["evidence"])
    page = result["pagination"]
    summary = {
        "returned_evidence_records": len(records),
        "unique_evidence_identifiers": len({row["evidence_id"] for row in records}),
        "returned_planned_outcomes": sum(row["category"] == "planned_outcomes" for row in records),
        "pagination": page,
    }
    if profiles is not None:
        summary.update(
            matching_trials=page["total"], returned_trial_profiles=len(profiles),
            total_evidence_in_returned_trials=sum(p["pagination"]["total"] for p in profiles),
            profiles_with_more_evidence=[p["nct_id"] for p in profiles if p["pagination"]["has_more"]],
            all_evidence_returned=page["all_evidence_returned"] and all(p["pagination"]["all_evidence_returned"] for p in profiles),
            profile_status_counts=dict(Counter(p["status"] for p in profiles)),
        )
    else:
        summary["all_evidence_returned"] = page["all_evidence_returned"]
    return summary


def run_workflows(retriever):
    """The caller verifies graph identity once before these timed API calls."""
    reports = []
    for name, method, arguments in CASES:
        runs = []
        for number in range(1, RUNS + 1):
            started = time.perf_counter()
            try:
                result = getattr(retriever, method)(**arguments)
                elapsed = time.perf_counter() - started
                record = {"run": number, "elapsed_seconds": elapsed, "status": result["status"],
                          "error": None, "evidence_counts": evidence_summary(result)}
            except Exception as exc:
                record = {"run": number, "elapsed_seconds": time.perf_counter() - started,
                          "status": "ERROR", "error": safe_error(exc), "evidence_counts": None}
            runs.append(record)
        latencies = [run["elapsed_seconds"] for run in runs]
        successes = [run["elapsed_seconds"] for run in runs if run["error"] is None]
        reports.append({
            "workflow": name, "method": method, "arguments": arguments, "runs": runs,
            "status_counts": dict(Counter(run["status"] for run in runs)),
            "successful_runs": len(successes), "failed_runs": RUNS - len(successes),
            "median_elapsed_seconds": statistics.median(latencies),
            "max_elapsed_seconds": max(latencies),
            "successful_run_median_seconds": statistics.median(successes) if successes else None,
            "successful_run_max_seconds": max(successes) if successes else None,
        })
    return reports


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path,
                        default=Path(__file__).resolve().parent / ".env")
    parser.add_argument("--output", type=Path, help="New JSON path; existing files are never overwritten")
    args = parser.parse_args(argv)
    timestamp = datetime.now(timezone.utc)
    output = args.output or DEFAULT_RESULTS_DIR / ("retrieval_latency_" + timestamp.strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    if output.exists():
        parser.error("Output file already exists; refusing overwrite")
    report = {
        "schema_version": "HTT-FULL-RETRIEVAL-LATENCY-v1", "created_utc": timestamp.isoformat(),
        "database": retrieve.DATABASE, "dataset_version": retrieve.DATASET,
        "graph_version": retrieve.GRAPH, "snapshot_date": retrieve.SNAPSHOT,
        "manifest_sha256": retrieve.MANIFEST_SHA256, "runs_per_workflow": RUNS,
        "timing_policy": "perf_counter wall time for retrieval API calls, including result materialization and validation; initialization and report serialization excluded",
        "execution_policy": "One verified connection; four workflows in listed order, three consecutive attempts each; sequential; no warmup or wrapper retries",
        "limitations": [
            "Three repetitions are descriptive, not a statistical performance guarantee.",
            "Caches are not reset; first-use and warmed timings can differ.",
            "Median/max cover all attempts, including errors; success-only summaries are also provided.",
            "NOT_FOUND and PARTIAL are valid retrieval statuses, not exceptions.",
            "Only configured pages are measured; no automatic traversal. Search evidence is limited to 50 records per returned trial.",
            "Existing driver read-retry and per-query timeout behavior is unchanged; no whole-workflow deadline is added.",
        ],
        "workflows": [],
    }
    started = time.perf_counter()
    try:
        with retrieve.FullCohortRetriever(retrieve.load_config(args.env_file)) as retriever:
            report["verification"] = retriever.verify_connection()
            report["initialization_seconds"] = time.perf_counter() - started
            report["workflows"] = run_workflows(retriever)
        report["status"] = "FINISHED_WITH_ERRORS" if any(w["failed_runs"] for w in report["workflows"]) else "FINISHED"
    except Exception as exc:
        report.update(status="STOPPED", error=safe_error(exc),
                      initialization_seconds=time.perf_counter() - started)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    print(json.dumps({"report_path": str(output), **report}, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if report["status"] == "FINISHED" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "STOPPED", "error": safe_error(exc)}), file=sys.stderr)
        raise SystemExit(1) from None
