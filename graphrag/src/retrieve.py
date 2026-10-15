#!/usr/bin/env python3
"""Read-only Neo4j retrieval for the HeartTrialTwin GraphRAG prototype.

Phase 1 retrieves and structures verified graph evidence only. It does not use
an LLM, generate Cypher, summarize clinical evidence, or modify Neo4j records.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import queries


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH = REPO_ROOT / "graphrag" / ".env"
LEGACY_ENV_PATH = REPO_ROOT / "artifacts" / "knowledge_graph" / ".env"
DEFAULT_RESULTS_DIR = REPO_ROOT / "graphrag" / "results"

EXPECTED_DATABASE = "57aa5fa3"
EXPECTED_DATASET_VERSION = "HTT-P1-AACT-20260905"
EXPECTED_GRAPH_VERSION = "HTT-KG-AACT-20260905-v1"
EXPECTED_NODE_COUNT = 26
EXPECTED_RELATIONSHIP_COUNT = 65
EXPECTED_TRIAL_COUNT = 5
EXPECTED_OUTCOME_COUNT = 10

NCT_PATTERN = re.compile(r"^NCT\d{8}$", re.IGNORECASE)
SUPPORTED_EVIDENCE_RELATIONSHIPS = [
    "HAS_SUBMITTED_CONDITION",
    "HAS_BROWSE_CONDITION",
    "HAS_INTERVENTION",
    "LEAD_SPONSORED_BY",
    "HAS_PLANNED_OUTCOME",
    "MEMBER_OF_DATASET",
]
PLANNED_OUTCOME_SAFEGUARD = "Registered planned outcome — not a clinical result."
SNAPSHOT_SAFEGUARD = (
    "Evidence comes from the pinned September 5, 2026 snapshot and may include "
    "later amendments; it is not asserted to be the original registration record."
)

QUESTION_TEXT = {
    "1": "What information is registered for clinical trial NCT00206232?",
    "2": (
        "Which sponsors are associated with heart-failure trials investigating "
        "spironolactone, and what planned outcomes did those trials register?"
    ),
    "3": (
        "What similarities and differences exist in the registered planned "
        "outcomes across the five selected heart-failure trials?"
    ),
}


class GraphRetrievalError(RuntimeError):
    """Raised when configuration, graph integrity, or retrieval is invalid."""


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str
    username: str
    password: str
    database: str
    env_source: str

    def public_summary(self) -> dict[str, str]:
        """Return only non-secret connection facts safe for logs and reports."""

        return {
            "database": self.database,
            "env_source": self.env_source,
            "uri_scheme": self.uri.split(":", 1)[0],
            "username_configured": str(bool(self.username)).lower(),
        }


def _load_dotenv_if_present(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise GraphRetrievalError(
            "python-dotenv is required to read a local .env file"
        ) from exc
    load_dotenv(path, override=False)
    return True


def load_config(env_path: Path | None = None) -> Neo4jConfig:
    """Load credentials without printing them.

    Process environment variables take precedence. If they are incomplete, the
    explicitly supplied path, ``graphrag/.env``, and finally the existing secure
    Challenge 3 ``artifacts/knowledge_graph/.env`` are checked in that order.
    """

    candidates: list[Path] = []
    if env_path is not None:
        candidates.append(Path(env_path))
    candidates.extend([DEFAULT_ENV_PATH, LEGACY_ENV_PATH])
    loaded_from = "process_environment"
    required_names = (
        "NEO4J_URI",
        "NEO4J_USERNAME",
        "NEO4J_PASSWORD",
        "NEO4J_DATABASE",
    )
    if not all(os.environ.get(name) for name in required_names):
        for candidate in candidates:
            if _load_dotenv_if_present(candidate):
                try:
                    loaded_from = str(candidate.relative_to(REPO_ROOT))
                except ValueError:
                    # Do not expose an arbitrary absolute local path in output.
                    loaded_from = "explicit_env_file"
                if all(os.environ.get(name) for name in required_names):
                    break

    values = {name: os.environ.get(name, "").strip() for name in required_names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise GraphRetrievalError(
            "Missing required Neo4j settings: " + ", ".join(missing)
        )
    uri = values["NEO4J_URI"]
    if not uri.startswith(("neo4j://", "neo4j+s://", "bolt://", "bolt+s://")):
        raise GraphRetrievalError("NEO4J_URI must use a supported Neo4j/Bolt scheme")
    database = values["NEO4J_DATABASE"]
    if database != EXPECTED_DATABASE:
        raise GraphRetrievalError(
            f"Configured database must be {EXPECTED_DATABASE!r}; found {database!r}"
        )
    return Neo4jConfig(
        uri=uri,
        username=values["NEO4J_USERNAME"],
        password=values["NEO4J_PASSWORD"],
        database=database,
        env_source=loaded_from,
    )


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "iso_format"):
        return value.iso_format()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def deterministic_outcome_comparison(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Compare exact registered outcome fields without clinical interpretation."""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    titles: dict[str, str] = {}
    measures_to_trials: dict[str, set[str]] = defaultdict(set)
    display_measure: dict[str, str] = {}
    outcome_type_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for row in rows:
        nct_id = str(row["nct_id"])
        titles[nct_id] = str(row.get("brief_title") or "")
        outcome = dict(row["planned_outcome"])
        grouped[nct_id].append(outcome)
        measure = str(outcome.get("measure") or "")
        normalized_measure = " ".join(measure.casefold().split())
        if normalized_measure:
            measures_to_trials[normalized_measure].add(nct_id)
            display_measure.setdefault(normalized_measure, measure)
        outcome_type_counts[nct_id][str(outcome.get("outcome_type") or "unspecified")] += 1

    shared_exact_measures = [
        {
            "measure": display_measure[measure],
            "nct_ids": sorted(trials),
            "trial_count": len(trials),
        }
        for measure, trials in sorted(measures_to_trials.items())
        if len(trials) > 1
    ]
    per_trial = []
    for nct_id in sorted(grouped):
        ordered_outcomes = sorted(
            grouped[nct_id],
            key=lambda item: int(item.get("source_record_id") or 0),
        )
        per_trial.append(
            {
                "nct_id": nct_id,
                "brief_title": titles[nct_id],
                "planned_outcome_count": len(ordered_outcomes),
                "outcome_type_counts": dict(sorted(outcome_type_counts[nct_id].items())),
                "registered_measures": [item.get("measure") for item in ordered_outcomes],
                "registered_time_frames": [item.get("time_frame") for item in ordered_outcomes],
            }
        )
    return {
        "comparison_method": (
            "Exact normalized-string comparison of registered measure names, plus "
            "counts of stored outcome types and time frames; no clinical inference."
        ),
        "trial_count": len(grouped),
        "planned_outcome_count": sum(len(values) for values in grouped.values()),
        "shared_exact_measures": shared_exact_measures,
        "shared_exact_measure_count": len(shared_exact_measures),
        "per_trial": per_trial,
    }


class Neo4jRetriever:
    """Read-only executor for the three fixed HeartTrialTwin workflows."""

    def __init__(self, config: Neo4jConfig, driver: Any | None = None) -> None:
        self.config = config
        self._owns_driver = driver is None
        if driver is None:
            try:
                from neo4j import GraphDatabase
            except ImportError as exc:
                raise GraphRetrievalError(
                    "neo4j is required; install graphrag/requirements.txt"
                ) from exc
            driver = GraphDatabase.driver(
                config.uri, auth=(config.username, config.password)
            )
        self.driver = driver

    def close(self) -> None:
        if self._owns_driver:
            self.driver.close()

    def __enter__(self) -> "Neo4jRetriever":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _run(self, query: str, parameters: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
        try:
            from neo4j import RoutingControl
        except ImportError as exc:
            raise GraphRetrievalError("neo4j is required for retrieval") from exc
        try:
            records, _, _ = self.driver.execute_query(
                query,
                parameters_=dict(parameters or {}),
                database_=self.config.database,
                routing_=RoutingControl.READ,
            )
        except Exception as exc:
            raise GraphRetrievalError(f"Neo4j read query failed: {exc}") from exc
        return [_json_safe(dict(record)) for record in records]

    def verify_connection(self) -> dict[str, Any]:
        try:
            self.driver.verify_connectivity()
        except Exception as exc:
            raise GraphRetrievalError(f"Neo4j connectivity check failed: {exc}") from exc
        database_rows = self._run(queries.DATABASE_INFO_QUERY)
        if len(database_rows) != 1 or database_rows[0].get("name") != self.config.database:
            raise GraphRetrievalError("Connected database identity did not match configuration")
        totals = self._run(queries.GRAPH_TOTALS_QUERY)
        if len(totals) != 1:
            raise GraphRetrievalError("Graph totals query returned an unexpected result")
        node_count = int(totals[0]["node_count"])
        relationship_count = int(totals[0]["relationship_count"])
        if (node_count, relationship_count) != (
            EXPECTED_NODE_COUNT,
            EXPECTED_RELATIONSHIP_COUNT,
        ):
            raise GraphRetrievalError(
                "Connected graph does not match the verified 26-node/65-relationship graph"
            )
        source_rows = self._run(
            queries.SOURCE_DATASET_QUERY,
            {"dataset_version": EXPECTED_DATASET_VERSION},
        )
        if len(source_rows) != 1:
            raise GraphRetrievalError("Pinned SourceDataset node was not found exactly once")
        source = source_rows[0]["source_dataset"]
        if source.get("graph_version") != EXPECTED_GRAPH_VERSION:
            raise GraphRetrievalError("Connected graph version does not match the manifest")
        return {
            "connected": True,
            "database": self.config.database,
            "node_count": node_count,
            "relationship_count": relationship_count,
            "dataset_version": source.get("dataset_version"),
            "graph_version": source.get("graph_version"),
            "snapshot_date": source.get("snapshot_date"),
        }

    def question_1(self, nct_id: str = "NCT00206232") -> dict[str, Any]:
        if not isinstance(nct_id, str) or not NCT_PATTERN.fullmatch(nct_id.strip()):
            raise GraphRetrievalError("nct_id must match NCT followed by eight digits")
        normalized_nct_id = nct_id.strip().upper()
        rows = self._run(
            queries.BASIC_TRIAL_QUERY,
            {
                "nct_id": normalized_nct_id,
                "relationship_types": SUPPORTED_EVIDENCE_RELATIONSHIPS,
            },
        )
        if not rows:
            raise GraphRetrievalError(f"Trial not found in the prepared graph: {normalized_nct_id}")
        return self._result("1", rows, {"nct_id": normalized_nct_id})

    def question_2(self) -> dict[str, Any]:
        parameters = {
            "condition_normalized": "heart failure",
            "intervention_normalized": "spironolactone",
            "dataset_version": EXPECTED_DATASET_VERSION,
        }
        rows = self._run(queries.SPONSOR_OUTCOME_QUERY, parameters)
        return self._result("2", rows, parameters)

    def question_3(self) -> dict[str, Any]:
        parameters = {"dataset_version": EXPECTED_DATASET_VERSION}
        rows = self._run(queries.OUTCOME_COMPARISON_QUERY, parameters)
        comparison = deterministic_outcome_comparison(rows)
        if comparison["trial_count"] != EXPECTED_TRIAL_COUNT:
            raise GraphRetrievalError(
                f"Expected outcomes for five trials; found {comparison['trial_count']}"
            )
        if comparison["planned_outcome_count"] != EXPECTED_OUTCOME_COUNT:
            raise GraphRetrievalError(
                "Expected ten registered planned outcomes; found "
                f"{comparison['planned_outcome_count']}"
            )
        result = self._result("3", rows, parameters)
        result["deterministic_comparison"] = comparison
        return result

    @staticmethod
    def _result(
        question_id: str,
        rows: Sequence[Mapping[str, Any]],
        parameters: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "question_id": question_id,
            "question": QUESTION_TEXT[question_id],
            "parameters": dict(parameters),
            "dataset_version": EXPECTED_DATASET_VERSION,
            "graph_version": EXPECTED_GRAPH_VERSION,
            "retrieved_utc": datetime.now(timezone.utc).isoformat(),
            "row_count": len(rows),
            "safeguards": {
                "planned_outcomes": PLANNED_OUTCOME_SAFEGUARD,
                "snapshot": SNAPSHOT_SAFEGUARD,
                "no_llm_generation": True,
                "read_only_retrieval": True,
            },
            "evidence": list(rows),
        }


def save_results(payload: Mapping[str, Any], results_dir: Path) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    base = results_dir / f"neo4j_phase1_retrieval_{timestamp}.json"
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    for counter in range(1000):
        path = base if counter == 0 else base.with_stem(f"{base.stem}_{counter}")
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(text)
            return path
        except FileExistsError:
            continue
    raise GraphRetrievalError("Could not allocate a unique result filename")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run fixed, read-only HeartTrialTwin Neo4j retrieval workflows."
    )
    parser.add_argument(
        "--question", choices=("1", "2", "3", "all"), default="all"
    )
    parser.add_argument("--nct-id", default="NCT00206232")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = load_config(args.env_file)
        with Neo4jRetriever(config) as retriever:
            connection = retriever.verify_connection()
            selected = ("1", "2", "3") if args.question == "all" else (args.question,)
            results = []
            for question_id in selected:
                if question_id == "1":
                    results.append(retriever.question_1(args.nct_id))
                elif question_id == "2":
                    results.append(retriever.question_2())
                else:
                    results.append(retriever.question_3())
        payload: dict[str, Any] = {
            "phase": "Neo4j retrieval only; no LLM",
            "connection": connection,
            "configuration": config.public_summary(),
            "results": results,
        }
        if args.save:
            payload["saved_to"] = str(save_results(payload, args.results_dir))
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except GraphRetrievalError as exc:
        print(f"Graph retrieval failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
