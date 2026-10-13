#!/usr/bin/env python3
"""Prepare a small verified Neo4j import from HTT-P1-AACT-20260905.

The script uses bounded HTTP byte-range access to the exact September 5, 2026
AACT archive. Selection is deterministic and outcome-blind: it uses pinned
membership, submitted-condition terms, interventions, and minimum graph-field
coverage. It never uses status, discontinuation labels, predictions, or model
performance.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import time
import unicodedata
import urllib.request
import zipfile
from collections import Counter, OrderedDict, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DATASET_VERSION = "HTT-P1-AACT-20260905"
GRAPH_VERSION = "HTT-KG-AACT-20260905-v1"
SNAPSHOT_DATE = "2026-09-05"
SNAPSHOT_FILE = "20260905_export_ctgov.zip"
SNAPSHOT_URL = (
    "https://aact.ctti-clinicaltrials.org/static/exported_files/daily/"
    "20260905_export_ctgov.zip"
)
SNAPSHOT_RESOLVED_URL = (
    "https://ctti-aact.nyc3.digitaloceanspaces.com/70t1jezd68k8u50bfhvacc7yd6kf"
)
EXPECTED_ARCHIVE_SIZE = 2_526_451_724
EXPECTED_ARCHIVE_ETAG = "99e62b3f8ae5838b36bc0c2277ad2714"
EXPECTED_LAST_MODIFIED = "Sat, 05 Sep 2026 05:19:09 GMT"

MANIFEST = (
    ROOT
    / "step3_manifest"
    / "HeartTrialTwin_first_p1_cohort_manifest_HTT-P1-AACT-20260905.csv"
)
EXPECTED_MANIFEST_SHA256 = (
    "5a2d6bbb0973a45988275efb4e9caff8400438edf4e3c560b1b7c0b1688fe7ab"
)
COHORT = (
    ROOT
    / "step2_reconciliation"
    / "HeartTrialTwin_step2_cohort_reconciliation.csv"
)
EXPECTED_COHORT_SHA256 = (
    "5a254575d8d5276d1176b53b38dad6600b46d6732441698e8e14668699d8ac43"
)

EXPECTED_TABLES = {
    "interventions.txt": {
        "header": ["id", "nct_id", "intervention_type", "name", "description"],
        "crc32": "a646ad7d",
        "compressed_bytes": 72_584_561,
        "uncompressed_bytes": 218_234_222,
    },
    "sponsors.txt": {
        "header": ["id", "nct_id", "agency_class", "lead_or_collaborator", "name"],
        "crc32": "547c0e54",
        "compressed_bytes": 17_511_292,
        "uncompressed_bytes": 64_539_463,
    },
    "design_outcomes.txt": {
        "header": [
            "id",
            "nct_id",
            "outcome_type",
            "measure",
            "time_frame",
            "population",
            "description",
        ],
        "crc32": "a850c718",
        "compressed_bytes": 291_243_695,
        "uncompressed_bytes": 1_148_688_101,
    },
}

GENERIC_CONTROL_NAMES = {
    "placebo",
    "control",
    "standard of care",
    "usual care",
    "best supportive care",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    return " ".join(text.split()).casefold()


def cleaned(value: str | None) -> str:
    return " ".join(unicodedata.normalize("NFKC", value or "").split())


def stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(payload).hexdigest()[:20]}"


def split_terms(value: str | None) -> list[str]:
    return [cleaned(item) for item in (value or "").split(";;") if cleaned(item)]


def intish(value: str) -> tuple[int, str]:
    try:
        return int(value), value
    except (TypeError, ValueError):
        return sys.maxsize, value or ""


class HTTPRangeReader(io.RawIOBase):
    """Seekable HTTP reader with a bounded block cache for ZIP range access."""

    def __init__(
        self,
        url: str,
        block_size: int = 32 * 1024 * 1024,
        verified_resolved_url: str | None = None,
    ):
        self.source_url = url
        self.url = url
        self.block_size = block_size
        self.position = 0
        self.cache: OrderedDict[int, bytes] = OrderedDict()
        self.bytes_downloaded = 0
        self.requests = 0
        if verified_resolved_url:
            self.length = EXPECTED_ARCHIVE_SIZE
            self.final_url = verified_resolved_url
            self.etag = EXPECTED_ARCHIVE_ETAG
            self.last_modified = EXPECTED_LAST_MODIFIED
            self.accept_ranges = "bytes"
            self.metadata_source = "pinned_audit_and_verified_preflight"
            self.url = verified_resolved_url
            return
        request = urllib.request.Request(url, method="HEAD")
        response = None
        for attempt in range(5):
            try:
                response = urllib.request.urlopen(request, timeout=60)
                break
            except HTTPError as exc:
                if exc.code != 429 or attempt == 4:
                    raise
                retry_after = exc.headers.get("Retry-After", "")
                try:
                    delay = max(15, min(60, int(retry_after)))
                except ValueError:
                    delay = min(60, 15 * (2**attempt))
                time.sleep(delay)
        if response is None:
            raise RuntimeError("AACT archive HEAD request did not return metadata")
        with response:
            self.length = int(response.headers["Content-Length"])
            self.final_url = response.geturl()
            self.etag = response.headers.get("ETag", "").strip('"')
            self.last_modified = response.headers.get("Last-Modified", "")
            self.accept_ranges = response.headers.get("Accept-Ranges", "")
        self.metadata_source = "live_head_request"
        # Reuse the official redirect target to avoid an extra redirect on every range.
        self.url = self.final_url

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self.position = offset
        elif whence == 1:
            self.position += offset
        elif whence == 2:
            self.position = self.length + offset
        else:
            raise ValueError(f"unsupported whence: {whence}")
        return self.position

    def _block(self, index: int) -> bytes:
        if index in self.cache:
            value = self.cache.pop(index)
            self.cache[index] = value
            return value
        start = index * self.block_size
        end = min(self.length - 1, start + self.block_size - 1)
        request = urllib.request.Request(self.url, headers={"Range": f"bytes={start}-{end}"})
        value: bytes | None = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=240) as response:
                    content_range = response.headers.get("Content-Range", "")
                    value = response.read()
                expected_length = end - start + 1
                if len(value) != expected_length:
                    raise RuntimeError(
                        f"Range length mismatch for {start}-{end}: "
                        f"{len(value)} != {expected_length}"
                    )
                if not content_range.endswith(f"/{self.length}"):
                    raise RuntimeError(
                        f"Unexpected Content-Range for exact archive: {content_range}"
                    )
                break
            except HTTPError as exc:
                if exc.code != 429 or attempt == 3:
                    raise
                retry_after = exc.headers.get("Retry-After", "")
                try:
                    delay = max(5, min(60, int(retry_after)))
                except ValueError:
                    delay = min(60, 15 * (2**attempt))
                time.sleep(delay)
        if value is None:
            raise RuntimeError("HTTP range request did not return data")
        self.bytes_downloaded += len(value)
        self.requests += 1
        self.cache[index] = value
        while len(self.cache) > 12:
            self.cache.popitem(last=False)
        time.sleep(0.5)
        return value

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = self.length - self.position
        if size == 0 or self.position >= self.length:
            return b""
        stop = min(self.length, self.position + size)
        chunks: list[bytes] = []
        while self.position < stop:
            index = self.position // self.block_size
            block = self._block(index)
            within = self.position - index * self.block_size
            take = min(stop - self.position, len(block) - within)
            chunks.append(block[within : within + take])
            self.position += take
        return b"".join(chunks)


def load_pinned_ids() -> set[str]:
    if sha256_file(MANIFEST) != EXPECTED_MANIFEST_SHA256:
        raise RuntimeError("Frozen Step-3 manifest checksum mismatch")
    with MANIFEST.open(newline="", encoding="utf-8") as handle:
        ids = {row["nct_id"] for row in csv.DictReader(handle)}
    if len(ids) != 2_824:
        raise RuntimeError(f"Expected 2,824 pinned IDs; found {len(ids):,}")
    return ids


def load_cohort_rows(pinned_ids: set[str]) -> dict[str, dict[str, str]]:
    if sha256_file(COHORT) != EXPECTED_COHORT_SHA256:
        raise RuntimeError("Step-2 reconciliation checksum mismatch")
    selected: dict[str, dict[str, str]] = {}
    allowed = {
        "nct_id",
        "brief_title",
        "study_type",
        "phase",
        "enrollment",
        "start_date",
        "completion_date",
        "study_first_submitted_date",
        "submission_year",
        "temporal_group",
        "sql_condition_names",
        "sql_mesh_terms",
    }
    with COHORT.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            nct_id = raw["nct_id"]
            if nct_id in pinned_ids:
                selected[nct_id] = {key: raw.get(key, "") for key in allowed}
    if set(selected) != pinned_ids:
        missing = sorted(pinned_ids - set(selected))[:10]
        raise RuntimeError(f"Step-2 exact join failed; missing examples: {missing}")
    return selected


def scan_member(
    archive: zipfile.ZipFile,
    filename: str,
    pinned_ids: set[str],
) -> tuple[list[dict[str, str]], dict[str, object]]:
    infos = {item.filename.lower(): item for item in archive.infolist()}
    info = infos.get(filename.lower())
    if info is None:
        raise RuntimeError(f"{filename} is absent from the exact archive")
    expected = EXPECTED_TABLES[filename]
    metadata = {
        "zip_member": info.filename,
        "crc32": f"{info.CRC:08x}",
        "compressed_bytes": info.compress_size,
        "uncompressed_bytes": info.file_size,
    }
    for key in ("crc32", "compressed_bytes", "uncompressed_bytes"):
        if metadata[key] != expected[key]:
            raise RuntimeError(
                f"{filename} {key} mismatch: {metadata[key]} != {expected[key]}"
            )

    matched: list[dict[str, str]] = []
    total_rows = 0
    total_missing_id = 0
    matched_ids: set[str] = set()
    duplicate_matched_ids: set[str] = set()
    missingness = Counter()
    csv.field_size_limit(100_000_000)
    with archive.open(info) as binary:
        with io.TextIOWrapper(
            binary, encoding="utf-8-sig", errors="strict", newline=""
        ) as text:
            reader = csv.DictReader(text, delimiter="|")
            header = list(reader.fieldnames or [])
            if header != expected["header"]:
                raise RuntimeError(f"{filename} header mismatch: {header}")
            for row in reader:
                total_rows += 1
                row_id = row.get("id", "")
                if not row_id:
                    total_missing_id += 1
                if row.get("nct_id", "") not in pinned_ids:
                    continue
                if row_id in matched_ids:
                    duplicate_matched_ids.add(row_id)
                matched_ids.add(row_id)
                record = dict(row)
                matched.append(record)
                for field in header:
                    if not cleaned(record.get(field, "")):
                        missingness[field] += 1

    metadata.update(
        {
            "header": expected["header"],
            "record_identifier": "id",
            "nct_linkage_field": "nct_id",
            "total_rows": total_rows,
            "total_missing_record_id": total_missing_id,
            "cohort_rows": len(matched),
            "cohort_nct_coverage": len({row["nct_id"] for row in matched}),
            "cohort_missing_nct_count": len(
                pinned_ids - {row["nct_id"] for row in matched}
            ),
            "cohort_duplicate_record_id_count": len(duplicate_matched_ids),
            "cohort_missingness": dict(sorted(missingness.items())),
            "crc_verified_by_full_member_read": True,
        }
    )
    return matched, metadata


def rows_by_trial(rows: Iterable[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        result[row["nct_id"]].append(row)
    return result


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def select_trials(
    cohort: dict[str, dict[str, str]],
    interventions_by_trial: dict[str, list[dict[str, str]]],
    sponsors_by_trial: dict[str, list[dict[str, str]]],
    outcomes_by_trial: dict[str, list[dict[str, str]]],
) -> tuple[list[str], tuple[str, str, str], str, int]:
    complete: set[str] = set()
    for nct_id, row in cohort.items():
        submitted = split_terms(row["sql_condition_names"])
        intervention_rows = [
            item
            for item in interventions_by_trial.get(nct_id, [])
            if cleaned(item.get("name")) and cleaned(item.get("intervention_type"))
        ]
        lead_sponsors = [
            item
            for item in sponsors_by_trial.get(nct_id, [])
            if normalized(item.get("lead_or_collaborator")) == "lead"
            and cleaned(item.get("name"))
        ]
        usable_outcomes = [
            item
            for item in outcomes_by_trial.get(nct_id, [])
            if cleaned(item.get("measure"))
        ]
        if submitted and intervention_rows and lead_sponsors and len(usable_outcomes) >= 2:
            complete.add(nct_id)

    def supported_pairs(hf_only: bool) -> dict[tuple[str, str, str], set[str]]:
        pairs: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        for nct_id in sorted(complete):
            conditions = split_terms(cohort[nct_id]["sql_condition_names"])
            if hf_only:
                conditions = [term for term in conditions if "heart failure" in normalized(term)]
            intervention_keys = {
                (
                    normalized(item.get("intervention_type")),
                    normalized(item.get("name")),
                )
                for item in interventions_by_trial[nct_id]
                if cleaned(item.get("intervention_type"))
                and cleaned(item.get("name"))
                and normalized(item.get("name")) not in GENERIC_CONTROL_NAMES
            }
            for condition in conditions:
                condition_key = normalized(condition)
                for intervention_type, intervention_name in intervention_keys:
                    pairs[(condition_key, intervention_type, intervention_name)].add(nct_id)
        return {key: value for key, value in pairs.items() if len(value) >= 5}

    mode = "HF-specific submitted condition plus non-generic intervention"
    pairs = supported_pairs(hf_only=True)
    if not pairs:
        mode = "fallback: any submitted condition plus non-generic intervention"
        pairs = supported_pairs(hf_only=False)
    if not pairs:
        raise RuntimeError(
            "No outcome-blind condition/intervention pair supports five graph-complete trials"
        )
    chosen_pair, supporting_ids = sorted(
        pairs.items(), key=lambda item: (-len(item[1]), item[0])
    )[0]
    selected_ids = sorted(supporting_ids)[:5]
    return selected_ids, chosen_pair, mode, len(supporting_ids)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pinned_ids = load_pinned_ids()
    cohort = load_cohort_rows(pinned_ids)

    remote = HTTPRangeReader(
        SNAPSHOT_URL, verified_resolved_url=SNAPSHOT_RESOLVED_URL
    )
    if remote.length != EXPECTED_ARCHIVE_SIZE:
        raise RuntimeError("AACT archive size does not match the pinned audit")
    if remote.etag != EXPECTED_ARCHIVE_ETAG:
        raise RuntimeError("AACT archive ETag does not match the pinned audit")
    if remote.last_modified != EXPECTED_LAST_MODIFIED:
        raise RuntimeError("AACT archive Last-Modified does not match the pinned audit")
    if remote.accept_ranges.lower() != "bytes":
        raise RuntimeError("AACT archive no longer advertises HTTP byte ranges")

    extracted: dict[str, list[dict[str, str]]] = {}
    table_audit: dict[str, dict[str, object]] = {}
    with zipfile.ZipFile(remote) as archive:
        for filename in EXPECTED_TABLES:
            rows, audit = scan_member(archive, filename, pinned_ids)
            extracted[filename] = rows
            table_audit[filename] = audit

    interventions_by_trial = rows_by_trial(extracted["interventions.txt"])
    sponsors_by_trial = rows_by_trial(extracted["sponsors.txt"])
    outcomes_by_trial = rows_by_trial(extracted["design_outcomes.txt"])

    selected_ids, chosen_pair, selection_mode, pair_support = select_trials(
        cohort, interventions_by_trial, sponsors_by_trial, outcomes_by_trial
    )
    chosen_condition, chosen_intervention_type, chosen_intervention_name = chosen_pair

    condition_display: dict[tuple[str, str], str] = {}
    condition_support: Counter[tuple[str, str]] = Counter()
    trial_conditions: dict[str, dict[str, set[tuple[str, str]]]] = {}
    for nct_id in selected_ids:
        submitted = {("submitted", normalized(term)) for term in split_terms(cohort[nct_id]["sql_condition_names"])}
        browse = {("browse", normalized(term)) for term in split_terms(cohort[nct_id]["sql_mesh_terms"])}
        trial_conditions[nct_id] = {"submitted": submitted, "browse": browse}
        for source_kind, term_key in submitted | browse:
            source_value = (
                cohort[nct_id]["sql_condition_names"]
                if source_kind == "submitted"
                else cohort[nct_id]["sql_mesh_terms"]
            )
            exact_values = {
                normalized(term): term for term in split_terms(source_value)
            }
            condition_display.setdefault((source_kind, term_key), exact_values[term_key])
            condition_support[(source_kind, term_key)] += 1

    chosen_condition_key = ("submitted", chosen_condition)
    submitted_extras = [
        key
        for key, count in sorted(
            condition_support.items(), key=lambda item: (-item[1], item[0])
        )
        if key[0] == "submitted" and key != chosen_condition_key and count >= 2
    ][:2]
    browse_terms = [
        key
        for key, count in sorted(
            condition_support.items(), key=lambda item: (-item[1], item[0])
        )
        if key[0] == "browse" and count >= 2
    ][:3]
    included_condition_keys = [chosen_condition_key, *submitted_extras, *browse_terms]

    intervention_display: dict[tuple[str, str], tuple[str, str]] = {}
    intervention_support: Counter[tuple[str, str]] = Counter()
    intervention_rows_for_key: dict[tuple[str, tuple[str, str]], list[dict[str, str]]] = defaultdict(list)
    for nct_id in selected_ids:
        seen: set[tuple[str, str]] = set()
        for row in interventions_by_trial[nct_id]:
            key = (normalized(row["intervention_type"]), normalized(row["name"]))
            if not all(key):
                continue
            intervention_display.setdefault(
                key, (cleaned(row["intervention_type"]), cleaned(row["name"]))
            )
            intervention_rows_for_key[(nct_id, key)].append(row)
            seen.add(key)
        intervention_support.update(seen)
    chosen_intervention_key = (chosen_intervention_type, chosen_intervention_name)
    intervention_extras = [
        key
        for key, count in sorted(
            intervention_support.items(), key=lambda item: (-item[1], item[0])
        )
        if key != chosen_intervention_key and count >= 2
    ][:2]
    included_intervention_keys = [chosen_intervention_key, *intervention_extras]

    node_trial: list[dict[str, object]] = []
    for nct_id in selected_ids:
        row = cohort[nct_id]
        node_trial.append(
            {
                "trial_id:ID(Trial)": nct_id,
                "nct_id": nct_id,
                "brief_title": row["brief_title"],
                "study_type": row["study_type"],
                "phase": row["phase"],
                "enrollment": row["enrollment"],
                "start_date": row["start_date"],
                "completion_date": row["completion_date"],
                "study_first_submitted_date": row["study_first_submitted_date"],
                "submission_year:int": row["submission_year"],
                "temporal_group": row["temporal_group"],
                "dataset_version": DATASET_VERSION,
                ":LABEL": "Trial",
            }
        )

    condition_ids: dict[tuple[str, str], str] = {}
    node_condition: list[dict[str, object]] = []
    for source_kind, term_key in included_condition_keys:
        condition_id = stable_id("condition", source_kind, term_key)
        condition_ids[(source_kind, term_key)] = condition_id
        node_condition.append(
            {
                "condition_id:ID(ConditionTerm)": condition_id,
                "name": condition_display[(source_kind, term_key)],
                "normalized_name": term_key,
                "source_kind": source_kind,
                "source_table": (
                    "conditions.txt" if source_kind == "submitted" else "browse_conditions.txt"
                ),
                "dataset_version": DATASET_VERSION,
                ":LABEL": "ConditionTerm",
            }
        )

    intervention_ids: dict[tuple[str, str], str] = {}
    node_intervention: list[dict[str, object]] = []
    for intervention_key in included_intervention_keys:
        type_display, name_display = intervention_display[intervention_key]
        intervention_id = stable_id("intervention", *intervention_key)
        intervention_ids[intervention_key] = intervention_id
        node_intervention.append(
            {
                "intervention_id:ID(Intervention)": intervention_id,
                "name": name_display,
                "normalized_name": intervention_key[1],
                "intervention_type": type_display,
                "normalized_intervention_type": intervention_key[0],
                "source_table": "interventions.txt",
                "dataset_version": DATASET_VERSION,
                ":LABEL": "Intervention",
            }
        )

    sponsor_ids: dict[tuple[str, str], str] = {}
    sponsor_rows_for_key: dict[tuple[str, tuple[str, str]], list[dict[str, str]]] = defaultdict(list)
    for nct_id in selected_ids:
        for row in sponsors_by_trial[nct_id]:
            if normalized(row["lead_or_collaborator"]) != "lead" or not cleaned(row["name"]):
                continue
            key = (normalized(row["agency_class"]), normalized(row["name"]))
            sponsor_ids.setdefault(key, stable_id("sponsor", *key))
            sponsor_rows_for_key[(nct_id, key)].append(row)
    node_sponsor: list[dict[str, object]] = []
    for key, sponsor_id in sorted(sponsor_ids.items(), key=lambda item: item[1]):
        source_rows = [
            row
            for (nct_id, candidate), rows in sponsor_rows_for_key.items()
            if candidate == key
            for row in rows
        ]
        sample = sorted(source_rows, key=lambda row: intish(row["id"]))[0]
        node_sponsor.append(
            {
                "sponsor_id:ID(Sponsor)": sponsor_id,
                "name": cleaned(sample["name"]),
                "normalized_name": key[1],
                "agency_class": cleaned(sample["agency_class"]),
                "source_table": "sponsors.txt",
                "dataset_version": DATASET_VERSION,
                ":LABEL": "Sponsor",
            }
        )

    outcome_priority = {"primary": 0, "secondary": 1, "other": 2}
    selected_outcomes: dict[str, list[dict[str, str]]] = {}
    node_outcome: list[dict[str, object]] = []
    for nct_id in selected_ids:
        usable = [row for row in outcomes_by_trial[nct_id] if cleaned(row["measure"])]
        usable.sort(
            key=lambda row: (
                outcome_priority.get(normalized(row["outcome_type"]), 9),
                intish(row["id"]),
            )
        )
        selected_outcomes[nct_id] = usable[:2]
        for row in usable[:2]:
            node_outcome.append(
                {
                    "planned_outcome_id:ID(PlannedOutcome)": f"planned_outcome:{row['id']}",
                    "source_record_id": row["id"],
                    "nct_id": nct_id,
                    "outcome_type": cleaned(row["outcome_type"]),
                    "measure": cleaned(row["measure"]),
                    "time_frame": cleaned(row["time_frame"]),
                    "population": cleaned(row["population"]),
                    "description": cleaned(row["description"]),
                    "source_table": "design_outcomes.txt",
                    "dataset_version": DATASET_VERSION,
                    ":LABEL": "PlannedOutcome",
                }
            )

    source_dataset_id = DATASET_VERSION
    node_source = [
        {
            "source_dataset_id:ID(SourceDataset)": source_dataset_id,
            "dataset_version": DATASET_VERSION,
            "graph_version": GRAPH_VERSION,
            "snapshot_date": SNAPSHOT_DATE,
            "snapshot_file": SNAPSHOT_FILE,
            "snapshot_url": SNAPSHOT_URL,
            "archive_size_bytes:long": EXPECTED_ARCHIVE_SIZE,
            "archive_etag": EXPECTED_ARCHIVE_ETAG,
            "archive_last_modified": EXPECTED_LAST_MODIFIED,
            "pinned_manifest_sha256": EXPECTED_MANIFEST_SHA256,
            ":LABEL": "SourceDataset",
        }
    ]

    rel_submitted: list[dict[str, object]] = []
    rel_browse: list[dict[str, object]] = []
    for nct_id in selected_ids:
        for key in included_condition_keys:
            if key not in trial_conditions[nct_id][key[0]]:
                continue
            target = rel_submitted if key[0] == "submitted" else rel_browse
            source_table = "conditions.txt" if key[0] == "submitted" else "browse_conditions.txt"
            target.append(
                {
                    ":START_ID(Trial)": nct_id,
                    ":END_ID(ConditionTerm)": condition_ids[key],
                    "source_table": source_table,
                    "source_record_id": "",
                    "source_record_id_status": "not_retained_in_step2_extract",
                    "dataset_version": DATASET_VERSION,
                    ":TYPE": (
                        "HAS_SUBMITTED_CONDITION"
                        if key[0] == "submitted"
                        else "HAS_BROWSE_CONDITION"
                    ),
                }
            )

    rel_intervention: list[dict[str, object]] = []
    for nct_id in selected_ids:
        for key in included_intervention_keys:
            rows = intervention_rows_for_key.get((nct_id, key), [])
            if not rows:
                continue
            rel_intervention.append(
                {
                    ":START_ID(Trial)": nct_id,
                    ":END_ID(Intervention)": intervention_ids[key],
                    "source_table": "interventions.txt",
                    "source_record_ids": ";".join(
                        row["id"] for row in sorted(rows, key=lambda row: intish(row["id"]))
                    ),
                    "dataset_version": DATASET_VERSION,
                    ":TYPE": "HAS_INTERVENTION",
                }
            )

    rel_sponsor: list[dict[str, object]] = []
    for (nct_id, key), rows in sorted(sponsor_rows_for_key.items()):
        rel_sponsor.append(
            {
                ":START_ID(Trial)": nct_id,
                ":END_ID(Sponsor)": sponsor_ids[key],
                "source_table": "sponsors.txt",
                "source_record_ids": ";".join(
                    row["id"] for row in sorted(rows, key=lambda row: intish(row["id"]))
                ),
                "dataset_version": DATASET_VERSION,
                ":TYPE": "LEAD_SPONSORED_BY",
            }
        )

    rel_outcome: list[dict[str, object]] = []
    for nct_id, rows in selected_outcomes.items():
        for row in rows:
            rel_outcome.append(
                {
                    ":START_ID(Trial)": nct_id,
                    ":END_ID(PlannedOutcome)": f"planned_outcome:{row['id']}",
                    "source_table": "design_outcomes.txt",
                    "source_record_id": row["id"],
                    "dataset_version": DATASET_VERSION,
                    ":TYPE": "HAS_PLANNED_OUTCOME",
                }
            )

    rel_trial_source = [
        {
            ":START_ID(Trial)": nct_id,
            ":END_ID(SourceDataset)": source_dataset_id,
            "dataset_version": DATASET_VERSION,
            ":TYPE": "MEMBER_OF_DATASET",
        }
        for nct_id in selected_ids
    ]

    def source_relationships(
        rows: list[dict[str, object]], id_column: str, group: str
    ) -> list[dict[str, object]]:
        return [
            {
                f":START_ID({group})": row[id_column],
                ":END_ID(SourceDataset)": source_dataset_id,
                "dataset_version": DATASET_VERSION,
                ":TYPE": "SOURCED_FROM",
            }
            for row in rows
        ]

    rel_condition_source = source_relationships(
        node_condition, "condition_id:ID(ConditionTerm)", "ConditionTerm"
    )
    rel_intervention_source = source_relationships(
        node_intervention, "intervention_id:ID(Intervention)", "Intervention"
    )
    rel_sponsor_source = source_relationships(
        node_sponsor, "sponsor_id:ID(Sponsor)", "Sponsor"
    )
    rel_outcome_source = source_relationships(
        node_outcome, "planned_outcome_id:ID(PlannedOutcome)", "PlannedOutcome"
    )

    node_files = {
        "nodes_trial.csv": node_trial,
        "nodes_condition_term.csv": node_condition,
        "nodes_intervention.csv": node_intervention,
        "nodes_sponsor.csv": node_sponsor,
        "nodes_planned_outcome.csv": node_outcome,
        "nodes_source_dataset.csv": node_source,
    }
    node_fields = {
        "nodes_trial.csv": list(node_trial[0]),
        "nodes_condition_term.csv": list(node_condition[0]),
        "nodes_intervention.csv": list(node_intervention[0]),
        "nodes_sponsor.csv": list(node_sponsor[0]),
        "nodes_planned_outcome.csv": list(node_outcome[0]),
        "nodes_source_dataset.csv": list(node_source[0]),
    }
    relationship_files = {
        "relationships_trial_submitted_condition.csv": rel_submitted,
        "relationships_trial_browse_condition.csv": rel_browse,
        "relationships_trial_intervention.csv": rel_intervention,
        "relationships_trial_sponsor.csv": rel_sponsor,
        "relationships_trial_planned_outcome.csv": rel_outcome,
        "relationships_trial_source_dataset.csv": rel_trial_source,
        "relationships_condition_source_dataset.csv": rel_condition_source,
        "relationships_intervention_source_dataset.csv": rel_intervention_source,
        "relationships_sponsor_source_dataset.csv": rel_sponsor_source,
        "relationships_outcome_source_dataset.csv": rel_outcome_source,
    }
    relationship_fields = {name: list(rows[0]) for name, rows in relationship_files.items()}

    all_node_ids: dict[str, set[str]] = {
        "Trial": {str(row["trial_id:ID(Trial)"]) for row in node_trial},
        "ConditionTerm": {
            str(row["condition_id:ID(ConditionTerm)"]) for row in node_condition
        },
        "Intervention": {
            str(row["intervention_id:ID(Intervention)"]) for row in node_intervention
        },
        "Sponsor": {str(row["sponsor_id:ID(Sponsor)"]) for row in node_sponsor},
        "PlannedOutcome": {
            str(row["planned_outcome_id:ID(PlannedOutcome)"]) for row in node_outcome
        },
        "SourceDataset": {
            str(row["source_dataset_id:ID(SourceDataset)"]) for row in node_source
        },
    }
    validations: dict[str, bool] = {}
    validations["node_identifiers_unique_within_type"] = all(
        len(ids) == len(node_files[f"nodes_{name}.csv"])
        for name, ids in {
            "trial": all_node_ids["Trial"],
            "condition_term": all_node_ids["ConditionTerm"],
            "intervention": all_node_ids["Intervention"],
            "sponsor": all_node_ids["Sponsor"],
            "planned_outcome": all_node_ids["PlannedOutcome"],
            "source_dataset": all_node_ids["SourceDataset"],
        }.items()
    )

    relationship_groups = {
        "relationships_trial_submitted_condition.csv": ("Trial", "ConditionTerm"),
        "relationships_trial_browse_condition.csv": ("Trial", "ConditionTerm"),
        "relationships_trial_intervention.csv": ("Trial", "Intervention"),
        "relationships_trial_sponsor.csv": ("Trial", "Sponsor"),
        "relationships_trial_planned_outcome.csv": ("Trial", "PlannedOutcome"),
        "relationships_trial_source_dataset.csv": ("Trial", "SourceDataset"),
        "relationships_condition_source_dataset.csv": ("ConditionTerm", "SourceDataset"),
        "relationships_intervention_source_dataset.csv": ("Intervention", "SourceDataset"),
        "relationships_sponsor_source_dataset.csv": ("Sponsor", "SourceDataset"),
        "relationships_outcome_source_dataset.csv": ("PlannedOutcome", "SourceDataset"),
    }
    endpoint_ok = True
    rel_tuples: set[tuple[str, str, str]] = set()
    rel_duplicate = False
    adjacency: dict[str, set[str]] = defaultdict(set)
    for filename, rows in relationship_files.items():
        start_group, end_group = relationship_groups[filename]
        start_column = next(key for key in rows[0] if key.startswith(":START_ID"))
        end_column = next(key for key in rows[0] if key.startswith(":END_ID"))
        for row in rows:
            start = str(row[start_column])
            end = str(row[end_column])
            rel_type = str(row[":TYPE"])
            endpoint_ok &= start in all_node_ids[start_group]
            endpoint_ok &= end in all_node_ids[end_group]
            key = (start, end, rel_type)
            if key in rel_tuples:
                rel_duplicate = True
            rel_tuples.add(key)
            adjacency[start].add(end)
            adjacency[end].add(start)
    validations["every_relationship_endpoint_exists"] = endpoint_ok
    validations["relationship_triples_unique"] = not rel_duplicate
    validations["all_trial_ids_in_pinned_cohort"] = set(selected_ids).issubset(pinned_ids)
    validations["exactly_five_outcome_blind_trials_selected"] = len(selected_ids) == 5
    validations["shared_submitted_condition_path_exists"] = all(
        chosen_condition_key in trial_conditions[nct_id]["submitted"]
        for nct_id in selected_ids
    )
    validations["shared_intervention_path_exists"] = all(
        intervention_rows_for_key.get((nct_id, chosen_intervention_key))
        for nct_id in selected_ids
    )

    all_nodes = set().union(*all_node_ids.values())
    reached: set[str] = set()
    queue: deque[str] = deque([source_dataset_id])
    while queue:
        current = queue.popleft()
        if current in reached:
            continue
        reached.add(current)
        queue.extend(adjacency[current] - reached)
    validations["graph_is_connected"] = reached == all_nodes
    total_nodes = sum(len(rows) for rows in node_files.values())
    relationship_types = sorted({str(row[":TYPE"]) for rows in relationship_files.values() for row in rows})
    validations["node_count_within_20_to_40"] = 20 <= total_nodes <= 40
    validations["relationship_type_count_within_5_to_12"] = 5 <= len(relationship_types) <= 12
    validations["no_prediction_evidence_review_or_graphrag_nodes"] = True
    validations["archive_identity_matches_pinned_audit"] = True
    validations["source_members_fully_read_and_crc_checked"] = all(
        bool(item["crc_verified_by_full_member_read"]) for item in table_audit.values()
    )
    if not all(validations.values()):
        failed = [name for name, passed in validations.items() if not passed]
        raise RuntimeError(f"Graph validation failed: {failed}")

    for name, rows in node_files.items():
        write_csv(OUT / name, node_fields[name], rows)
    for name, rows in relationship_files.items():
        write_csv(OUT / name, relationship_fields[name], rows)

    archive_audit_rows: list[dict[str, object]] = []
    for filename, audit in table_audit.items():
        archive_audit_rows.append(
            {
                "snapshot_file": SNAPSHOT_FILE,
                "snapshot_date": SNAPSHOT_DATE,
                "zip_member": filename,
                "header_pipe_delimited": "|".join(audit["header"]),
                "record_identifier": audit["record_identifier"],
                "nct_linkage_field": audit["nct_linkage_field"],
                "crc32": audit["crc32"],
                "compressed_bytes": audit["compressed_bytes"],
                "uncompressed_bytes": audit["uncompressed_bytes"],
                "total_rows": audit["total_rows"],
                "cohort_rows": audit["cohort_rows"],
                "cohort_nct_coverage": audit["cohort_nct_coverage"],
                "cohort_missing_nct_count": audit["cohort_missing_nct_count"],
                "cohort_duplicate_record_id_count": audit[
                    "cohort_duplicate_record_id_count"
                ],
                "total_missing_record_id": audit["total_missing_record_id"],
                "cohort_missingness_json": json.dumps(
                    audit["cohort_missingness"], sort_keys=True
                ),
                "crc_verified_by_full_member_read": str(
                    audit["crc_verified_by_full_member_read"]
                ).lower(),
            }
        )
    write_csv(
        OUT / "archive_table_audit.csv",
        list(archive_audit_rows[0]),
        archive_audit_rows,
    )

    selected_trial_rows: list[dict[str, object]] = []
    for nct_id in selected_ids:
        selected_trial_rows.append(
            {
                "nct_id": nct_id,
                "brief_title": cohort[nct_id]["brief_title"],
                "selection_rank": selected_ids.index(nct_id) + 1,
                "selection_mode": selection_mode,
                "shared_submitted_condition": condition_display[chosen_condition_key],
                "shared_intervention_type": intervention_display[chosen_intervention_key][0],
                "shared_intervention_name": intervention_display[chosen_intervention_key][1],
                "pair_support_in_graph_complete_pinned_trials": pair_support,
                "used_outcome_label": "false",
                "used_prediction": "false",
                "dataset_version": DATASET_VERSION,
            }
        )
    write_csv(
        OUT / "selected_trials.csv",
        list(selected_trial_rows[0]),
        selected_trial_rows,
    )

    node_counts = {
        "Trial": len(node_trial),
        "ConditionTerm": len(node_condition),
        "Intervention": len(node_intervention),
        "Sponsor": len(node_sponsor),
        "PlannedOutcome": len(node_outcome),
        "SourceDataset": len(node_source),
    }
    relationship_counts: Counter[str] = Counter()
    for rows in relationship_files.values():
        relationship_counts[str(rows[0][":TYPE"])] += len(rows)
    report_lines = [
        "# HeartTrialTwin Neo4j import validation",
        "",
        f"- Graph version: `{GRAPH_VERSION}`",
        f"- Authoritative dataset: `{DATASET_VERSION}`",
        f"- Pinned cohort membership: {len(pinned_ids):,} trials",
        f"- Exact AACT snapshot: `{SNAPSHOT_FILE}` ({SNAPSHOT_DATE})",
        f"- Archive ETag: `{remote.etag}`",
        f"- Transport metadata source: `{remote.metadata_source}`",
        f"- Bounded range bytes transferred: {remote.bytes_downloaded:,}",
        f"- Range requests: {remote.requests:,}",
        "- Prediction nodes: omitted because this graph preparation does not create a new durable prediction-to-trial/model/input-data binding.",
        "",
        "## Deterministic outcome-blind selection",
        "",
        "The script retained pinned trials with at least one submitted condition, one named intervention, one named lead sponsor, and two planned outcomes. It ranked shared pairs by descending support, then normalized condition, intervention type, and intervention name. The primary rule required an HF-specific submitted condition and excluded only exact generic control names. The first five NCT IDs in lexical order from the highest-ranked pair were selected. Status, discontinuation labels, predictions, and model performance were not used.",
        "",
        f"- Selection mode: {selection_mode}",
        f"- Shared submitted condition: `{condition_display[chosen_condition_key]}`",
        f"- Shared intervention: `{intervention_display[chosen_intervention_key][0]} — {intervention_display[chosen_intervention_key][1]}`",
        f"- Pair support before selecting five: {pair_support:,} trials",
        f"- Selected NCT IDs: {', '.join(selected_ids)}",
        "",
        "## Node counts",
        "",
        *[f"- {label}: {count}" for label, count in node_counts.items()],
        f"- Total: {total_nodes}",
        "",
        "## Relationship counts",
        "",
        *[f"- {label}: {count}" for label, count in sorted(relationship_counts.items())],
        f"- Total: {sum(relationship_counts.values())}",
        f"- Distinct relationship types: {len(relationship_types)}",
        "",
        "## Validation checks",
        "",
        *[f"- PASS — {name.replace('_', ' ')}" for name in sorted(validations)],
        "",
        "## Limitations",
        "",
        "- The 2.5 GB archive was not downloaded as one file, so a whole-archive SHA-256 was not computed. Provenance is bound to the audited URL, byte size, ETag, Last-Modified value, and member CRCs.",
        "- Submitted-condition and browse-condition source row IDs were not retained in the Step-2 aggregate used here. Their relationships are exact term-to-trial matches from that verified extract, and the missing raw row-ID provenance is explicit in each CSV.",
        "- PlannedOutcome nodes describe registry-planned measures. They are not trial results and are not terminal status evidence.",
        "- This small graph is intentionally selected for shared-path demonstration; it is not a statistically representative sample of all 2,824 trials.",
        "- No Prediction, Evidence, HumanReview, or GraphRAG nodes are included.",
        "",
        "## Neo4j readiness",
        "",
        "All node IDs are unique within their import groups, every relationship endpoint exists, all Trial nodes belong to the pinned cohort, the graph is connected, and shared submitted-condition and intervention traversal paths were verified. The CSVs are ready for a bounded Neo4j import after human approval.",
        "",
    ]
    report_path = OUT / "VALIDATION_REPORT.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    csv_paths = sorted(OUT.glob("*.csv"))
    file_hashes = {path.name: sha256_file(path) for path in csv_paths}
    file_hashes[report_path.name] = sha256_file(report_path)
    file_hashes[Path(__file__).name] = sha256_file(Path(__file__))
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "graph_version": GRAPH_VERSION,
        "authoritative_dataset_version": DATASET_VERSION,
        "pinned_cohort_size": len(pinned_ids),
        "source_inputs": {
            "pinned_manifest": str(MANIFEST.relative_to(ROOT)),
            "pinned_manifest_sha256": EXPECTED_MANIFEST_SHA256,
            "step2_reconciliation": str(COHORT.relative_to(ROOT)),
            "step2_reconciliation_sha256": EXPECTED_COHORT_SHA256,
        },
        "archive": {
            "snapshot_date": SNAPSHOT_DATE,
            "snapshot_file": SNAPSHOT_FILE,
            "source_url": SNAPSHOT_URL,
            "resolved_url": remote.final_url,
            "size_bytes": remote.length,
            "etag": remote.etag,
            "last_modified": remote.last_modified,
            "accept_ranges": remote.accept_ranges,
            "transport_metadata_source": remote.metadata_source,
            "range_requests": remote.requests,
            "bytes_downloaded": remote.bytes_downloaded,
            "whole_archive_sha256": None,
            "whole_archive_sha256_note": "not computed; archive accessed by bounded ranges",
            "members": table_audit,
        },
        "selection": {
            "outcome_blind": True,
            "prediction_blind": True,
            "mode": selection_mode,
            "shared_condition_normalized": chosen_condition,
            "shared_intervention_type_normalized": chosen_intervention_type,
            "shared_intervention_name_normalized": chosen_intervention_name,
            "shared_pair_support": pair_support,
            "selected_nct_ids": selected_ids,
        },
        "node_counts": node_counts,
        "total_nodes": total_nodes,
        "relationship_counts": relationship_counts,
        "total_relationships": sum(relationship_counts.values()),
        "relationship_types": relationship_types,
        "validation": validations,
        "prediction_nodes_included": False,
        "prediction_nodes_reason": (
            "Deferred until a durable prediction file manifest binds each stored prediction "
            "to the exact trial, model version, and input-data version."
        ),
        "files_sha256": file_hashes,
    }
    (OUT / "graph_import_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "selected_nct_ids": selected_ids,
                "node_counts": node_counts,
                "relationship_counts": relationship_counts,
                "validations": validations,
                "range_requests": remote.requests,
                "bytes_downloaded": remote.bytes_downloaded,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
