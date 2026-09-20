#!/usr/bin/env python3
"""Build and validate the frozen HeartTrialTwin first-P1 cohort manifest.

Step 3 only: labels, submission dates, and temporal groups. This script does
not retrieve features, fit preprocessing, or train/evaluate any model.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path


DATASET_VERSION = "HTT-P1-AACT-20260905"
AACT_SNAPSHOT_DATE = "2026-09-05"
AACT_SNAPSHOT_FILE = "20260905_export_ctgov.zip"
EXPECTED_SOURCE_SHA256 = (
    "5a254575d8d5276d1176b53b38dad6600b46d6732441698e8e14668699d8ac43"
)

EXPECTED_GROUP_COUNTS = {
    "development": 1904,
    "validation": 464,
    "final_test": 456,
}

EXPECTED_OUTCOME_COUNTS = {
    "development": {
        "completed": 1505,
        "terminated": 281,
        "withdrawn": 118,
        "discontinued": 399,
    },
    "validation": {
        "completed": 356,
        "terminated": 66,
        "withdrawn": 42,
        "discontinued": 108,
    },
    "final_test": {
        "completed": 376,
        "terminated": 46,
        "withdrawn": 34,
        "discontinued": 80,
    },
}

STATUS_TO_TARGET = {
    "COMPLETED": 0,
    "TERMINATED": 1,
    "WITHDRAWN": 1,
}

SOURCE_GROUP_TO_MANIFEST_GROUP = {
    "Development (1999-2017)": "development",
    "Validation (2018-2020)": "validation",
    "Final test (2021-2024)": "final_test",
}

MANIFEST_FIELDS = [
    "nct_id",
    "source_overall_status",
    "discontinued",
    "study_first_submitted_date",
    "submission_year",
    "temporal_group",
    "dataset_version",
    "aact_snapshot_date",
    "aact_snapshot_file",
    "label_source_table",
    "label_rule",
    "temporal_source_field",
    "cohort_source_artifact",
    "cohort_source_sha256",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def expected_group(year: int) -> str | None:
    if 1999 <= year <= 2017:
        return "development"
    if 2018 <= year <= 2020:
        return "validation"
    if 2021 <= year <= 2024:
        return "final_test"
    return None


def check(name: str, condition: bool, observed, expected) -> dict:
    return {
        "check": name,
        "passed": bool(condition),
        "observed": observed,
        "expected": expected,
    }


def main() -> None:
    script_path = Path(__file__).resolve()
    output_dir = script_path.parent
    project_dir = output_dir.parent
    source_path = (
        project_dir
        / "step2_reconciliation"
        / "HeartTrialTwin_step2_cohort_reconciliation.csv"
    )
    manifest_path = (
        output_dir
        / "HeartTrialTwin_first_p1_cohort_manifest_HTT-P1-AACT-20260905.csv"
    )
    audit_path = (
        output_dir
        / "HeartTrialTwin_first_p1_cohort_manifest_HTT-P1-AACT-20260905.audit.json"
    )

    source_sha256 = sha256(source_path)
    if source_sha256 != EXPECTED_SOURCE_SHA256:
        raise RuntimeError(
            "Step-2 source checksum mismatch: "
            f"observed {source_sha256}, expected {EXPECTED_SOURCE_SHA256}"
        )

    manifest_rows = []
    with source_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["modeling_cohort_through_2024"] != "True":
                continue

            status = row["overall_status"]
            year = int(row["submission_year"])
            temporal_group = SOURCE_GROUP_TO_MANIFEST_GROUP[row["temporal_group"]]

            manifest_rows.append(
                {
                    "nct_id": row["nct_id"],
                    "source_overall_status": status,
                    "discontinued": STATUS_TO_TARGET[status],
                    "study_first_submitted_date": row[
                        "study_first_submitted_date"
                    ],
                    "submission_year": year,
                    "temporal_group": temporal_group,
                    "dataset_version": DATASET_VERSION,
                    "aact_snapshot_date": AACT_SNAPSHOT_DATE,
                    "aact_snapshot_file": AACT_SNAPSHOT_FILE,
                    "label_source_table": "ctgov.studies.overall_status",
                    "label_rule": (
                        "COMPLETED=0;TERMINATED|WITHDRAWN=1"
                    ),
                    "temporal_source_field": (
                        "ctgov.studies.study_first_submitted_date"
                    ),
                    "cohort_source_artifact": (
                        "step2_reconciliation/"
                        "HeartTrialTwin_step2_cohort_reconciliation.csv"
                    ),
                    "cohort_source_sha256": source_sha256,
                }
            )

    manifest_rows.sort(key=lambda row: row["nct_id"])

    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(manifest_rows)

    # Re-read the written artifact so validation covers the delivered bytes.
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        delivered_rows = list(csv.DictReader(handle))

    ids = [row["nct_id"] for row in delivered_rows]
    id_counts = Counter(ids)
    duplicate_ids = sorted(
        nct_id for nct_id, count in id_counts.items() if count > 1
    )
    missing_nct_rows = [i + 2 for i, row in enumerate(delivered_rows) if not row["nct_id"]]
    missing_date_rows = [
        row["nct_id"]
        for row in delivered_rows
        if not row["study_first_submitted_date"]
        or not row["submission_year"]
    ]

    parsed_dates = {}
    date_parse_errors = []
    for row in delivered_rows:
        try:
            parsed = date.fromisoformat(row["study_first_submitted_date"])
            parsed_dates[row["nct_id"]] = parsed
            if parsed.year != int(row["submission_year"]):
                date_parse_errors.append(row["nct_id"])
        except (TypeError, ValueError):
            date_parse_errors.append(row["nct_id"])

    invalid_status_rows = [
        row["nct_id"]
        for row in delivered_rows
        if row["source_overall_status"] not in STATUS_TO_TARGET
    ]
    target_mismatch_rows = [
        row["nct_id"]
        for row in delivered_rows
        if row["source_overall_status"] not in STATUS_TO_TARGET
        or int(row["discontinued"])
        != STATUS_TO_TARGET[row["source_overall_status"]]
    ]

    group_counts = Counter(row["temporal_group"] for row in delivered_rows)
    id_groups = defaultdict(set)
    for row in delivered_rows:
        id_groups[row["nct_id"]].add(row["temporal_group"])
    multi_group_ids = sorted(
        nct_id for nct_id, groups in id_groups.items() if len(groups) > 1
    )

    invalid_year_group_rows = [
        row["nct_id"]
        for row in delivered_rows
        if expected_group(int(row["submission_year"]))
        != row["temporal_group"]
    ]
    excluded_year_rows = [
        row["nct_id"]
        for row in delivered_rows
        if int(row["submission_year"]) in {2025, 2026}
        or int(row["submission_year"]) > 2024
    ]

    outcome_counts = {}
    for group in ("development", "validation", "final_test"):
        group_rows = [
            row for row in delivered_rows if row["temporal_group"] == group
        ]
        statuses = Counter(
            row["source_overall_status"] for row in group_rows
        )
        outcome_counts[group] = {
            "total": len(group_rows),
            "completed": statuses["COMPLETED"],
            "terminated": statuses["TERMINATED"],
            "withdrawn": statuses["WITHDRAWN"],
            "discontinued": sum(
                int(row["discontinued"]) for row in group_rows
            ),
        }

    total_discontinued = sum(
        int(row["discontinued"]) for row in delivered_rows
    )

    checks = [
        check("exactly_2824_rows", len(delivered_rows) == 2824, len(delivered_rows), 2824),
        check("one_row_per_nct_id", len(id_counts) == len(delivered_rows), len(id_counts), len(delivered_rows)),
        check("no_duplicate_nct_ids", not duplicate_ids, duplicate_ids, []),
        check("no_missing_nct_ids", not missing_nct_rows, missing_nct_rows, []),
        check(
            "no_missing_or_invalid_submission_dates_years",
            not missing_date_rows and not date_parse_errors,
            {"missing": missing_date_rows, "invalid_or_year_mismatch": date_parse_errors},
            {"missing": [], "invalid_or_year_mismatch": []},
        ),
        check("only_permitted_statuses", not invalid_status_rows, invalid_status_rows, []),
        check("target_agrees_with_status", not target_mismatch_rows, target_mismatch_rows, []),
        check("development_count", group_counts["development"] == 1904, group_counts["development"], 1904),
        check("validation_count", group_counts["validation"] == 464, group_counts["validation"], 464),
        check("final_test_count", group_counts["final_test"] == 456, group_counts["final_test"], 456),
        check("total_discontinued", total_discontinued == 587, total_discontinued, 587),
        check("no_nct_in_multiple_groups", not multi_group_ids, multi_group_ids, []),
        check("no_2025_2026_trials", not excluded_year_rows, excluded_year_rows, []),
        check(
            "year_to_temporal_group_mapping",
            not invalid_year_group_rows,
            invalid_year_group_rows,
            [],
        ),
        check(
            "group_counts_match_expected",
            dict(group_counts) == EXPECTED_GROUP_COUNTS,
            dict(group_counts),
            EXPECTED_GROUP_COUNTS,
        ),
        check(
            "group_outcome_counts_match_expected",
            all(
                {
                    key: outcome_counts[group][key]
                    for key in (
                        "completed",
                        "terminated",
                        "withdrawn",
                        "discontinued",
                    )
                }
                == EXPECTED_OUTCOME_COUNTS[group]
                for group in EXPECTED_OUTCOME_COUNTS
            ),
            outcome_counts,
            {
                group: {
                    "total": EXPECTED_GROUP_COUNTS[group],
                    **counts,
                }
                for group, counts in EXPECTED_OUTCOME_COUNTS.items()
            },
        ),
    ]

    if not all(item["passed"] for item in checks):
        failed = [item["check"] for item in checks if not item["passed"]]
        raise RuntimeError(f"Manifest validation failed: {failed}")

    manifest_sha256 = sha256(manifest_path)
    created_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    audit = {
        "dataset_version": DATASET_VERSION,
        "created_utc": created_utc,
        "manifest": {
            "path": manifest_path.name,
            "sha256": manifest_sha256,
            "rows": len(delivered_rows),
            "unique_nct_ids": len(id_counts),
        },
        "source": {
            "aact_snapshot_date": AACT_SNAPSHOT_DATE,
            "aact_snapshot_file": AACT_SNAPSHOT_FILE,
            "step2_artifact": str(source_path.relative_to(project_dir)),
            "step2_artifact_sha256": source_sha256,
        },
        "generation_code": {
            "path": script_path.name,
            "sha256": sha256(script_path),
        },
        "counts_by_temporal_group_and_outcome": outcome_counts,
        "overall_outcomes": {
            "completed": sum(
                row["source_overall_status"] == "COMPLETED"
                for row in delivered_rows
            ),
            "terminated": sum(
                row["source_overall_status"] == "TERMINATED"
                for row in delivered_rows
            ),
            "withdrawn": sum(
                row["source_overall_status"] == "WITHDRAWN"
                for row in delivered_rows
            ),
            "discontinued": total_discontinued,
        },
        "validation_checks": checks,
        "all_checks_passed": True,
    }
    audit_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
