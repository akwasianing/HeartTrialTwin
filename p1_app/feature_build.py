#!/usr/bin/env python3
"""Build the leakage-controlled one-feature table for the temporal baseline."""

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
DATASET_VERSION = "HTT-P1-AACT-20260905"
FEATURES = ["submission_year"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_features() -> Path:
    manifest_hash = sha256_file(MANIFEST)
    if manifest_hash != EXPECTED_MANIFEST_SHA256:
        raise RuntimeError(
            f"Frozen manifest checksum mismatch: {manifest_hash} != {EXPECTED_MANIFEST_SHA256}"
        )

    usecols = [
        "nct_id",
        "study_first_submitted_date",
        "submission_year",
        "temporal_group",
        "dataset_version",
        "discontinued",
    ]
    source = pd.read_csv(MANIFEST, usecols=usecols)
    source["study_first_submitted_date"] = pd.to_datetime(
        source["study_first_submitted_date"], errors="raise"
    )

    checks = {
        "row_count_2824": len(source) == 2824,
        "unique_nct_ids_2824": source["nct_id"].nunique() == 2824,
        "no_missing_nct_id": source["nct_id"].notna().all(),
        "no_missing_submission_date": source["study_first_submitted_date"].notna().all(),
        "no_missing_submission_year": source["submission_year"].notna().all(),
        "year_matches_date": (
            source["submission_year"] == source["study_first_submitted_date"].dt.year
        ).all(),
        "expected_temporal_groups": set(source["temporal_group"])
        == {"development", "validation", "final_test"},
        "dataset_version_exact": (source["dataset_version"] == DATASET_VERSION).all(),
    }
    checks = {name: bool(value) for name, value in checks.items()}
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise RuntimeError(f"Feature-build integrity failure: {failed}")

    # Final-test labels are explicitly masked so downstream code cannot evaluate
    # or tune against them accidentally.
    source["label_available"] = source["temporal_group"].isin(["development", "validation"])
    source["discontinued"] = source["discontinued"].astype("Int64")
    source.loc[source["temporal_group"] == "final_test", "discontinued"] = pd.NA

    output_cols = [
        "nct_id",
        "study_first_submitted_date",
        "submission_year",
        "temporal_group",
        "dataset_version",
        "label_available",
        "discontinued",
    ]
    features = source[output_cols].sort_values("nct_id").reset_index(drop=True)

    split_counts = features.groupby("temporal_group", observed=True).size().to_dict()
    expected_splits = {"development": 1904, "final_test": 456, "validation": 464}
    if split_counts != expected_splits:
        raise RuntimeError(f"Unexpected split counts: {split_counts}")
    if features.loc[features.temporal_group == "final_test", "discontinued"].notna().any():
        raise RuntimeError("Final-test outcomes were not masked")

    ARTEFACTS.mkdir(exist_ok=True)
    output = ARTEFACTS / "features.parquet"
    features.to_parquet(output, index=False)

    audit = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset_version": DATASET_VERSION,
        "manifest_path": str(MANIFEST.relative_to(PROJECT_ROOT)),
        "manifest_sha256": manifest_hash,
        "approved_predictors": FEATURES,
        "rows": len(features),
        "split_rows": split_counts,
        "final_test_labels_masked": True,
        "validation_checks": checks,
        "excluded_current_snapshot_features": [
            "phase",
            "enrollment",
            "start_date",
            "brief_title",
            "sponsor",
            "study_design",
            "eligibility",
        ],
    }
    (ARTEFACTS / "feature_build_audit.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Built {len(features)} rows with predictor: {FEATURES[0]}")
    print(f"Final-test labels masked: {audit['final_test_labels_masked']}")
    print(f"Saved {output}")
    return output


if __name__ == "__main__":
    try:
        build_features()
    except Exception as exc:
        sys.exit(f"ABORT: {exc}")
