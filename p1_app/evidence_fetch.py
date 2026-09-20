#!/usr/bin/env python3
"""Build exact-NCT provenance from the frozen manifest; no network access."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = PROJECT_ROOT / "step3_manifest" / "HeartTrialTwin_first_p1_cohort_manifest_HTT-P1-AACT-20260905.csv"
ARTEFACTS = Path(__file__).resolve().parent / "artefacts"
EXPECTED_MANIFEST_SHA256 = "5a2d6bbb0973a45988275efb4e9caff8400438edf4e3c560b1b7c0b1688fe7ab"
MODEL_VERSION = "HTT-TEMPORAL-LR-v1"
PREDICTION_POINT = "Initial ClinicalTrials.gov submission, represented by study_first_submitted_date"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_evidence() -> Path:
    manifest_hash = sha256_file(MANIFEST)
    if manifest_hash != EXPECTED_MANIFEST_SHA256:
        raise RuntimeError("Frozen manifest checksum mismatch")

    fields = [
        "nct_id",
        "study_first_submitted_date",
        "submission_year",
        "temporal_group",
        "dataset_version",
        "aact_snapshot_date",
        "aact_snapshot_file",
        "temporal_source_field",
    ]
    data = pd.read_csv(MANIFEST, usecols=fields, dtype=str)
    if len(data) != 2824 or data.nct_id.nunique() != 2824:
        raise RuntimeError("Unexpected frozen-manifest membership")

    limitation = (
        "Historical multifeature records could not be retrieved programmatically. "
        "Only the immutable submission date and derived year are used; current snapshot "
        "design, enrollment, sponsor, title, clinical, and outcome fields are excluded."
    )
    cache: dict[str, dict] = {}
    for row in data.to_dict("records"):
        nct_id = row["nct_id"]
        cache[nct_id] = {
            "nct_id": nct_id,
            "study_first_submitted_date": row["study_first_submitted_date"],
            "submission_year": int(row["submission_year"]),
            "temporal_group": row["temporal_group"],
            "dataset_version": row["dataset_version"],
            "aact_snapshot_date": row["aact_snapshot_date"],
            "aact_snapshot_file": row["aact_snapshot_file"],
            "source_file": str(MANIFEST.relative_to(PROJECT_ROOT)),
            "source_file_sha256": manifest_hash,
            "source_field": row["temporal_source_field"],
            "derived_predictor": "submission_year = year(study_first_submitted_date)",
            "model_version": MODEL_VERSION,
            "prediction_point": PREDICTION_POINT,
            "historical_data_limitation": limitation,
        }

    ARTEFACTS.mkdir(exist_ok=True)
    output = ARTEFACTS / "evidence_cache.json"
    output.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")
    audit = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "records": len(cache),
        "exact_nct_ids": len(set(cache)),
        "source_file": str(MANIFEST.relative_to(PROJECT_ROOT)),
        "source_file_sha256": manifest_hash,
        "fields_included": list(next(iter(cache.values())).keys()),
        "outcome_fields_included": False,
        "network_access_used": False,
    }
    (ARTEFACTS / "evidence_audit.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Saved exact-NCT provenance for {len(cache)} trials")
    print("Outcome fields included: False")
    return output


if __name__ == "__main__":
    try:
        build_evidence()
    except Exception as exc:
        sys.exit(f"ABORT: {exc}")
