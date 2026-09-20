#!/usr/bin/env python3
"""Outcome-blind ClinicalTrials.gov history retrieval feasibility pilot.

This script deliberately tests only the public record-history page. It does not
retry or attempt to bypass the access-controlled internal history API.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "step3_manifest" / "HeartTrialTwin_first_p1_cohort_manifest_HTT-P1-AACT-20260905.csv"
OUT_DIR = Path(__file__).resolve().parent
SEED = "HTT-HISTORY-PILOT-20260919"


def select_without_outcomes() -> pd.DataFrame:
    """Select records using only ID, submission date/year, and temporal group."""
    df = pd.read_csv(
        MANIFEST,
        usecols=[
            "nct_id",
            "study_first_submitted_date",
            "submission_year",
            "temporal_group",
        ],
    )
    df["study_first_submitted_date"] = pd.to_datetime(df["study_first_submitted_date"])

    selected: list[pd.DataFrame] = []
    legacy = (
        df[(df["temporal_group"] == "development") & (df["submission_year"] <= 2004)]
        .sort_values(["study_first_submitted_date", "nct_id"])
        .head(4)
        .copy()
    )
    legacy["selection_stratum"] = "development_legacy_1999_2004"
    selected.append(legacy)

    for stratum, temporal_group, lo, hi, count in [
        ("development_modern_2006_2011", "development", 2006, 2011, 4),
        ("development_modern_2012_2017", "development", 2012, 2017, 4),
        ("validation_2018_2020", "validation", 2018, 2020, 6),
    ]:
        candidates = df[
            (df["temporal_group"] == temporal_group)
            & df["submission_year"].between(lo, hi)
        ].copy()
        candidates["selection_hash"] = candidates["nct_id"].map(
            lambda value: hashlib.sha256(f"{SEED}|{value}".encode()).hexdigest()
        )
        chosen = candidates.sort_values("selection_hash").head(count).copy()
        chosen["selection_stratum"] = stratum
        selected.append(chosen.drop(columns="selection_hash"))

    result = pd.concat(selected, ignore_index=True)
    return result.sort_values(["temporal_group", "selection_stratum", "nct_id"])


def main() -> None:
    selected = select_without_outcomes()
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "HeartTrialTwin-CS5588-history-feasibility-pilot/1.0",
            "Accept": "text/html,application/xhtml+xml",
        }
    )

    rows: list[dict[str, object]] = []
    for record in selected.to_dict("records"):
        nct_id = record["nct_id"]
        url = f"https://clinicaltrials.gov/study/{nct_id}?tab=history&a=1"
        row: dict[str, object] = {
            **record,
            "study_first_submitted_date": record["study_first_submitted_date"].date().isoformat(),
            "requested_version": 1,
            "source_url": url,
            "http_status": "",
            "response_bytes": 0,
            "response_sha256": "",
            "record_payload_present": False,
            "programmatic_record_retrieved": False,
            "historically_eligible": False,
            "rejection_reason": "",
            "error": "",
        }
        try:
            response = session.get(url, timeout=20, allow_redirects=True)
            body = response.content
            text = response.text
            row["http_status"] = response.status_code
            row["response_bytes"] = len(body)
            row["response_sha256"] = hashlib.sha256(body).hexdigest()

            # A successful payload must identify both the selected trial and a
            # historical structured field. The current public HTML is an Angular
            # shell and therefore fails this check even when HTTP status is 200.
            payload_present = nct_id in text and any(
                marker in text
                for marker in (
                    "studyFirstSubmitDate",
                    "enrollmentInfo",
                    "protocolSection",
                    "version-content-panel",
                )
            )
            row["record_payload_present"] = payload_present
            row["programmatic_record_retrieved"] = response.ok and payload_present
            if not response.ok:
                row["rejection_reason"] = f"public history page returned HTTP {response.status_code}"
            elif not payload_present:
                row["rejection_reason"] = "HTTP 200 contained the client application shell, not the historical record payload"
            else:
                row["rejection_reason"] = "retrieved payload requires field-level historical eligibility review"
        except requests.RequestException as exc:
            row["rejection_reason"] = "public history page request failed"
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)

    output = OUT_DIR / "pilot_attempts.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    audit = {
        "pilot_id": "HTT-HISTORY-RETRIEVAL-PILOT-20260919",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "parent_dataset_version": "HTT-P1-AACT-20260905",
        "manifest_path": str(MANIFEST.relative_to(ROOT)),
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "selection_used_outcome_labels": False,
        "selection_seed": SEED,
        "selection_method": "four earliest 1999-2004 development records; lowest salted SHA-256 NCT IDs within two modern development strata and validation",
        "attempted": len(rows),
        "public_history_page_http_200": sum(row["http_status"] == 200 for row in rows),
        "programmatic_records_retrieved": sum(bool(row["programmatic_record_retrieved"]) for row in rows),
        "historically_eligible": sum(bool(row["historically_eligible"]) for row in rows),
        "known_internal_history_endpoint_result": "HTTP 403; not retried and no bypass attempted",
        "notes": [
            "The official browser UI can render history records, but the public HTML response contains only the client application shell.",
            "Response hashes in pilot_attempts.csv hash the HTML shell and are not historical-record content hashes.",
            "No current-snapshot value was substituted for a missing historical value.",
        ],
    }
    (OUT_DIR / "pilot_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
