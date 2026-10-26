"""Pinned CSV fixtures and an in-memory read-only driver; no live services."""

import csv
import hashlib
import json
import re
import sys
import tempfile
import unittest
from collections import Counter, defaultdict
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from full_cohort_graphrag.src import queries
from full_cohort_graphrag.src import retrieve as api


class Fixture:
    """Use actual pinned source values, not invented clinical fixture records."""

    def __init__(self):
        self.contract = api.load_contract()
        self.nodes = {}
        for label, filename in (("Trial", "trial"), ("ConditionTerm", "condition_term"),
                                ("Intervention", "intervention"), ("Sponsor", "sponsor"),
                                ("PlannedOutcome", "planned_outcome"), ("SourceDataset", "source_dataset")):
            name = f"nodes_{filename}.csv"
            rows = self.rows(name)
            key = next(k for k in rows[0] if ":ID(" in k)
            self.nodes[label] = {row[key]: {k.split(":", 1)[0]: v for k, v in row.items() if k != ":LABEL"} for row in rows}
        self.edges = defaultdict(list)
        self.by_trial = defaultdict(list)
        for rel, (_, label, _, _, _) in api.EVIDENCE_SPECS.items():
            names = {"HAS_SUBMITTED_CONDITION": "submitted_condition", "HAS_BROWSE_CONDITION": "browse_condition",
                     "HAS_INTERVENTION": "intervention", "LEAD_SPONSORED_BY": "sponsor", "HAS_PLANNED_OUTCOME": "planned_outcome"}
            for row in self.rows("relationships_trial_" + names[rel] + ".csv"):
                first, second = list(row)[:2]
                edge = {"nct_id": row[first], "relationship_type": rel, "evidence_id": row[second],
                        "evidence_labels": [label], "evidence_properties": self.nodes[label][row[second]],
                        "relationship_properties": {k: v for k, v in row.items() if k not in {first, second, ":TYPE"}}}
                self.edges[rel].append(edge)
                self.by_trial[row[first]].append(edge)
        for values in self.by_trial.values():
            values.sort(key=lambda row: (row["nct_id"], row["relationship_type"], row["evidence_id"]))

    def rows(self, name):
        path = api.GRAPH_DIR / name
        if api.sha256(path) != self.contract.manifest["files_sha256"][name]:
            raise AssertionError("Unverified test fixture CSV")
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))


class FakeDriver:
    def __init__(self, fixture):
        self.fixture = fixture
        self.calls = []
        self.source = dict(fixture.contract.source)
        self.database_name = api.DATABASE
        self.bad_counts = False
        self.drop_page_row = False
        self.connectivity_error = False
        self.query_error = False
        self.extra_properties = False

    def verify_connectivity(self):
        if self.connectivity_error:
            raise RuntimeError("private-user private-password secret-host")

    def execute_query(self, query, *, parameters_, database_, routing_):
        text = query.text
        if query.timeout != api.TIMEOUT_SECONDS or database_ != api.DATABASE or routing_ != "r":
            raise AssertionError("Explicit read-only database and timeout required")
        if text not in queries.READ_ONLY_QUERIES:
            raise AssertionError("Unregistered query")
        self.calls.append((text, parameters_))
        if self.query_error:
            raise RuntimeError("private-user private-password secret-host")
        parameters = parameters_
        manifest = self.fixture.contract.manifest["validation"]
        if text == queries.DATABASE_INFO:
            rows = [{"name": self.database_name}]
        elif text == queries.TOTALS:
            rows = [{"node_count": manifest["total_nodes"] + int(self.bad_counts), "relationship_count": manifest["total_relationships"]}]
        elif text == queries.LABEL_COUNTS:
            rows = [{"label": label, "count": count} for label, count in sorted(manifest["node_counts"].items())]
        elif text == queries.RELATIONSHIP_COUNTS:
            rows = [{"relationship_type": rel, "count": count} for rel, count in sorted(manifest["relationship_counts"].items())]
        elif text == queries.SOURCE_DATASET:
            rows = [{"source_dataset": self.source}]
        elif text == queries.TRIALS:
            rows = []
            for nct in sorted(parameters["nct_ids"]):
                if nct not in self.fixture.nodes["Trial"]:
                    continue
                trial = dict(self.fixture.nodes["Trial"][nct])
                if self.extra_properties:
                    trial.update(enrollment="PRIVATE-EXTRA", overall_status="PRIVATE-EXTRA")
                rows.append({"trial": trial, "membership_type": "MEMBER_OF_DATASET",
                             "membership_properties": {"dataset_version": api.DATASET},
                             "source_dataset": self.source})
        elif text == queries.EVIDENCE_COUNTS:
            counts = Counter((nct, row["relationship_type"]) for nct in parameters["nct_ids"]
                             for row in self.fixture.by_trial[nct] if row["relationship_type"] in parameters["relationship_types"])
            rows = [{"nct_id": nct, "relationship_type": rel, "count": count} for (nct, rel), count in sorted(counts.items())]
        elif text == queries.EVIDENCE_PAGE:
            rows = [row for nct in sorted(parameters["nct_ids"]) for row in self.fixture.by_trial[nct]
                    if row["relationship_type"] in parameters["relationship_types"]]
            rows = rows[parameters["offset"]:parameters["offset"] + parameters["limit"]]
            if self.extra_properties:
                rows = [{**row, "evidence_properties": {**row["evidence_properties"], "enrollment": "PRIVATE-EXTRA", "why_stopped": "PRIVATE-EXTRA"}} for row in rows]
            if self.drop_page_row:
                rows = rows[:-1]
        elif text in {queries.SEARCH_COUNT, queries.SEARCH_PAGE}:
            ids = []
            for nct in sorted(self.fixture.nodes["Trial"]):
                records = self.fixture.by_trial[nct]
                conditions = any(row["relationship_type"] == "HAS_SUBMITTED_CONDITION"
                                 and row["evidence_properties"]["normalized_name"] == parameters["condition_normalized"] for row in records)
                interventions = any(row["relationship_type"] == "HAS_INTERVENTION"
                                    and row["evidence_properties"]["normalized_name"] == parameters["intervention_normalized"] for row in records)
                if conditions and interventions:
                    ids.append(nct)
            rows = [{"total": len(ids)}] if text == queries.SEARCH_COUNT else [{"nct_id": nct} for nct in ids[parameters["offset"]:parameters["offset"] + parameters["limit"]]]
        else:
            raise AssertionError("Unsupported query")
        return rows, None, None


class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = Fixture()

    def setUp(self):
        self.no_live_driver = patch("neo4j.GraphDatabase.driver", side_effect=AssertionError("No live driver allowed"))
        self.no_live_driver.start()
        self.addCleanup(self.no_live_driver.stop)
        self.driver = FakeDriver(self.fixture)
        self.config = api.Config("bolt://127.0.0.1:7687", "private-user", "private-password")
        self.retriever = api.FullCohortRetriever(self.config, driver=self.driver, contract=self.fixture.contract)
        self.retriever.verify_connection()

    def test_pinned_contract_and_counts(self):
        verified = self.retriever.verify_connection()
        self.assertEqual(len(self.fixture.contract.membership), 2824)
        self.assertEqual(verified["node_counts"]["Trial"], 2824)
        self.assertEqual(sum(verified["node_counts"].values()), 28777)
        self.assertEqual(sum(verified["relationship_counts"].values()), 79125)
        self.assertEqual(verified["manifest_sha256"], api.MANIFEST_SHA256)

    def test_tampered_manifest_and_membership_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "full_cohort_manifest.json").write_text("{}")
            with self.assertRaisesRegex(api.RetrievalError, "manifest SHA-256"):
                api.load_contract(directory)
        original = api.sha256
        with patch.object(api, "sha256", side_effect=lambda p: "bad" if Path(p).name == "cohort_membership.csv" else original(p)):
            with self.assertRaisesRegex(api.RetrievalError, "Membership SHA-256"):
                api.load_contract()

    def test_dedicated_credentials_no_fallback_and_no_secret_repr(self):
        # Do not read the user's configured private .env during offline tests.
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text("")
            with self.assertRaisesRegex(api.RetrievalError, "no fallback"):
                api.load_config(env_path, environ={"NEO4J_PASSWORD": "private-password", "FULL_NEO4J_DATABASE": api.DATABASE})
            config = api.load_config(env_path, environ={"FULL_GRAPHRAG_NEO4J_URI": self.config.uri,
                                                      "FULL_GRAPHRAG_NEO4J_USERNAME": self.config.username,
                                                      "FULL_GRAPHRAG_NEO4J_PASSWORD": self.config.password,
                                                      "FULL_GRAPHRAG_NEO4J_DATABASE": api.DATABASE})
        self.assertEqual(config, self.config)
        self.assertNotIn("private-password", repr(config))
        self.assertNotIn("private-user", repr(config))

    def test_explicit_private_env_file_and_no_interpolation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("FULL_GRAPHRAG_NEO4J_URI=bolt://localhost:7687\nFULL_GRAPHRAG_NEO4J_USERNAME=test-user\nFULL_GRAPHRAG_NEO4J_PASSWORD=${UNRELATED_PASSWORD}\nFULL_GRAPHRAG_NEO4J_DATABASE=hearttrialtwin-full2824\n")
            config = api.load_config(path, environ={})
            self.assertEqual(config.password, "${UNRELATED_PASSWORD}")

    def test_wrong_database_and_remote_targets_rejected_without_driver(self):
        for uri, database in ((self.config.uri, "neo4j"), (self.config.uri, "57aa5fa3"),
                              ("neo4j+s://57aa5fa3.databases.neo4j.io", api.DATABASE),
                              ("bolt://remote-host:7687", api.DATABASE)):
            with self.subTest(database=database), self.assertRaises(api.RetrievalError):
                api.FullCohortRetriever(api.Config(uri, "user", "password", database), contract=self.fixture.contract)

    def test_live_identity_counts_graph_version_and_snapshot_rejected(self):
        for key, value in (("database_name", "neo4j"), ("bad_counts", True),
                           ("graph_version", "HTT-KG-AACT-20260905-v1"), ("snapshot_date", "2026-09-06"),
                           ("archive_sha256", "wrong")):
            driver = FakeDriver(self.fixture)
            if key in driver.source:
                driver.source[key] = value
            else:
                setattr(driver, key, value)
            retriever = api.FullCohortRetriever(self.config, driver=driver, contract=self.fixture.contract)
            with self.subTest(key=key), self.assertRaises(api.RetrievalError):
                retriever.verify_connection()
            with self.assertRaisesRegex(api.RetrievalError, "verification"):
                retriever.trial_profile("NCT00206232")

    def test_complete_profile_has_seven_outcomes_not_demo_cap(self):
        result = self.retriever.trial_profile("nct00206232")
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["coverage"]["planned_outcomes"]["total"], 7)
        self.assertEqual(result["coverage"]["submitted_conditions"]["total"], 1)
        self.assertEqual(result["coverage"]["browse_conditions"]["total"], 4)
        self.assertTrue(result["pagination"]["all_evidence_returned"])
        self.assertEqual(result["safeguards"]["planned_outcomes"], api.PLANNED_SAFEGUARD)

    def test_missing_browse_conditions_preserved(self):
        result = self.retriever.trial_profile("NCT00057356")
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["coverage"]["browse_conditions"]["total"], 0)
        self.assertEqual(result["coverage"]["planned_outcomes"]["total"], 3)
        self.assertEqual(result["coverage"]["browse_conditions"]["source_status"], "NO_LINKED_RECORD_IN_PINNED_GRAPH")

    def test_missing_outcomes_and_missing_both_are_not_not_found(self):
        for nct, browse in (("NCT00000475", 3), ("NCT00012818", 0)):
            result = self.retriever.trial_profile(nct)
            self.assertEqual(result["status"], "PARTIAL")
            self.assertIsNotNone(result["trial"])
            self.assertEqual(result["coverage"]["planned_outcomes"]["total"], 0)
            self.assertEqual(result["coverage"]["browse_conditions"]["total"], browse)

    def test_unknown_trial_structured_not_found(self):
        before = len(self.driver.calls)
        result = self.retriever.trial_profile("NCT99999999")
        self.assertEqual(result["status"], "NOT_FOUND")
        self.assertIsNone(result["trial"])
        self.assertEqual(result["evidence"], [])
        self.assertEqual(len(self.driver.calls), before)
        self.assertEqual(result["source_dataset"]["graph_version"], api.GRAPH)

    def test_high_outcome_trial_profile_pagination_has_no_loss_or_duplicates(self):
        offset, records, total = 0, [], None
        while True:
            result = self.retriever.trial_profile("NCT05256303", limit=37, offset=offset)
            self.assertLessEqual(len(result["evidence"]), 37)
            total = result["pagination"]["total"]
            records.extend(result["evidence"])
            if not result["pagination"]["has_more"]:
                break
            offset = result["pagination"]["next_offset"]
        self.assertEqual(len(records), total)
        self.assertEqual(len({row["evidence_id"] for row in records}), total)
        self.assertEqual(sum(row["category"] == "planned_outcomes" for row in records), 108)

    def _high_outcome_profile_pages_limit20(self):
        pages, offset = [], 0
        # Bounded iteration also makes a broken/stuck cursor fail promptly.
        for _ in range(8):
            page = self.retriever.trial_profile("NCT05256303", limit=20, offset=offset)
            pages.append(page)
            if not page["pagination"]["has_more"]:
                break
            offset = page["pagination"]["next_offset"]
        return pages

    def test_profile_limit20_page_boundaries_outcomes_and_final_partial_status(self):
        pages = self._high_outcome_profile_pages_limit20()
        self.assertEqual(len(pages), 8)
        self.assertEqual([len(p["evidence"]) for p in pages], [20] * 7 + [16])
        self.assertEqual([p["pagination"]["returned"] for p in pages], [20] * 7 + [16])
        self.assertEqual([p["pagination"]["offset"] for p in pages], list(range(0, 156, 20)))
        outcome_counts = [sum(row["category"] == "planned_outcomes" for row in p["evidence"]) for p in pages]
        self.assertEqual(outcome_counts, [0, 4, 20, 20, 20, 20, 20, 4])
        self.assertEqual(sum(outcome_counts), 108)
        for index, page in enumerate(pages):
            with self.subTest(page=index + 1):
                self.assertEqual(page["pagination"]["total"], 156)
                self.assertEqual(page["pagination"]["limit"], 20)
                self.assertEqual(page["status"], "PARTIAL")
                self.assertFalse(page["pagination"]["all_evidence_returned"])
                self.assertEqual(page["coverage"]["planned_outcomes"]["total"], 108)
                self.assertEqual(page["coverage"]["planned_outcomes"]["returned"], outcome_counts[index])
                self.assertEqual(page["coverage"]["planned_outcomes"]["source_status"], "AVAILABLE")
                self.assertEqual(page["pagination"]["has_more"], index < 7)
                self.assertEqual(page["pagination"]["next_offset"], (index + 1) * 20 if index < 7 else None)
        final = pages[-1]
        self.assertFalse(final["pagination"]["has_more"])
        self.assertIsNone(final["pagination"]["next_offset"])
        self.assertEqual(final["pagination"]["returned"], 16)
        self.assertEqual(final["status"], "PARTIAL")

    def test_profile_limit20_identifiers_exactly_match_pinned_csv_evidence(self):
        nct = "NCT05256303"
        # Independent expected IDs from checksum-verified CSV relationship rows,
        # not the fake driver's ordered/page-sliced by_trial representation.
        expected_ids, expected_outcome_ids = [], set()
        for suffix, endpoint in (
            ("submitted_condition", ":END_ID(ConditionTerm)"),
            ("browse_condition", ":END_ID(ConditionTerm)"),
            ("intervention", ":END_ID(Intervention)"),
            ("sponsor", ":END_ID(Sponsor)"),
            ("planned_outcome", ":END_ID(PlannedOutcome)"),
        ):
            for row in self.fixture.rows(f"relationships_trial_{suffix}.csv"):
                if row[":START_ID(Trial)"] == nct:
                    evidence_id = "|".join((nct, row[":TYPE"], row[endpoint]))
                    expected_ids.append(evidence_id)
                    if row[":TYPE"] == "HAS_PLANNED_OUTCOME":
                        expected_outcome_ids.add(evidence_id)
        records = [row for page in self._high_outcome_profile_pages_limit20() for row in page["evidence"]]
        actual_ids = [row["evidence_id"] for row in records]
        self.assertEqual(len(expected_ids), 156)
        self.assertEqual(len(set(expected_ids)), 156)
        self.assertEqual(len(actual_ids), 156)
        self.assertEqual(len(set(actual_ids)), 156)
        self.assertCountEqual(actual_ids, expected_ids)
        self.assertEqual(set(actual_ids), set(expected_ids))
        actual_outcome_ids = {row["evidence_id"] for row in records if row["category"] == "planned_outcomes"}
        self.assertEqual(len(expected_outcome_ids), 108)
        self.assertEqual(actual_outcome_ids, expected_outcome_ids)

    def test_relationship_citations_and_trial_source_provenance_preserved(self):
        result = self.retriever.trial_profile("NCT00206232")
        self.assertEqual(result["dataset_relationship"]["start_id"], "NCT00206232")
        self.assertEqual(result["dataset_relationship"]["type"], "MEMBER_OF_DATASET")
        for record in result["evidence"]:
            rel = record["relationship"]
            self.assertEqual(rel["start_id"], record["nct_id"])
            original = next(row for row in self.fixture.by_trial[record["nct_id"]] if row["evidence_id"] == record["node_id"] and row["relationship_type"] == rel["type"])
            self.assertEqual(rel["properties"], original["relationship_properties"])
            refs = record["source_references"]
            for ref in refs:
                self.assertEqual(ref["nct_id"], record["nct_id"])
                self.assertEqual(ref["source_table"], rel["properties"]["source_table"])
            source_ids = rel["properties"].get("source_record_ids", rel["properties"].get("source_record_id"))
            self.assertEqual([ref["source_record_id"] for ref in refs], source_ids.split(";"))

    def test_search_exact_entities_returns_twelve_trials_without_join_multiplication(self):
        result = self.retriever.search_trials("  HEART   FAILURE ", "Spironolactone", limit=20, evidence_limit=200)
        self.assertEqual(result["pagination"]["total"], 12)
        ids = [profile["nct_id"] for profile in result["trial_profiles"]]
        self.assertEqual(ids, sorted(set(ids)))
        self.assertEqual(sum(p["coverage"]["planned_outcomes"]["total"] for p in result["trial_profiles"]), 81)
        page = self.retriever.search_trials("heart failure", "spironolactone", limit=5)
        self.assertEqual(page["status"], "PARTIAL")
        self.assertEqual(page["pagination"]["next_offset"], 5)

    def test_search_does_not_filter_trials_with_missing_evidence(self):
        # Choose actual registered entities from a trial missing both categories.
        rows = self.fixture.by_trial["NCT00012818"]
        condition = next(r["evidence_properties"]["name"] for r in rows if r["relationship_type"] == "HAS_SUBMITTED_CONDITION")
        intervention = next(r["evidence_properties"]["name"] for r in rows if r["relationship_type"] == "HAS_INTERVENTION")
        result = self.retriever.search_trials(condition, intervention, limit=20, evidence_limit=200)
        profile = next(p for p in result["trial_profiles"] if p["nct_id"] == "NCT00012818")
        self.assertEqual(profile["status"], "PARTIAL")
        self.assertEqual(profile["coverage"]["planned_outcomes"]["total"], 0)

    def test_search_empty_result_not_found(self):
        result = self.retriever.search_trials("no such registered condition", "no such registered intervention")
        self.assertEqual(result["status"], "NOT_FOUND")
        self.assertEqual(result["pagination"]["total"], 0)

    def test_comparison_preserves_missing_and_unknown_trials(self):
        ids = ["NCT00206232", "NCT00000475", "NCT00012818", "NCT99999999"]
        result = self.retriever.compare_planned_outcomes(ids)
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["pagination"]["total"], 7)
        trials = {t["nct_id"]: t for t in result["trials"]}
        self.assertEqual(trials["NCT99999999"]["status"], "NOT_FOUND")
        self.assertEqual(trials["NCT00000475"]["status"], "PARTIAL")
        self.assertEqual(trials["NCT00012818"]["status"], "PARTIAL")
        unknown = self.retriever.compare_planned_outcomes(["NCT99999999"])
        self.assertEqual(unknown["status"], "NOT_FOUND")

    def test_comparison_paginates_all_108_outcomes_and_defers_shared_claims(self):
        first = self.retriever.compare_planned_outcomes(["NCT05256303"], limit=50)
        self.assertEqual(first["pagination"]["total"], 108)
        self.assertEqual(first["pagination"]["returned"], 50)
        self.assertEqual(first["comparison"]["status"], "DEFERRED_UNTIL_ALL_PAGES")
        all_rows = self.retriever.compare_planned_outcomes(["NCT05256303"], limit=200)
        self.assertEqual(all_rows["status"], "COMPLETE")
        self.assertEqual(len(all_rows["evidence"]), 108)
        self.assertEqual(all_rows["comparison"]["shared_exact_measures"], [])

    def test_deterministic_subset_order_and_result_serialization(self):
        first = self.retriever.compare_planned_outcomes(["NCT00206232", "NCT00057356"])
        second = self.retriever.compare_planned_outcomes(["NCT00057356", "NCT00206232"])
        first.pop("retrieved_utc")
        second.pop("retrieved_utc")
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertIn("no clinical equivalence", first["comparison"]["method"])

    def test_queries_are_allowlisted_read_only_bounded_and_safely_projected(self):
        writes = re.compile(r"\b(CREATE|DELETE|DETACH|DROP|MERGE|REMOVE|SET|LOAD\s+CSV)\b", re.IGNORECASE)
        prohibited = ("enrollment", "overall_status", "why_stopped", "completion_date", "study_first_submitted_date", "prediction")
        for query in queries.READ_ONLY_QUERIES:
            self.assertIsNone(writes.search(query))
            self.assertIn("LIMIT", query)
            self.assertNotIn("properties(", query)
            for prop in prohibited:
                self.assertNotIn(prop, query)
        with self.assertRaisesRegex(api.RetrievalError, "allowlist"):
            self.retriever._run("MATCH (n) RETURN n", maximum=1)
        malicious = "heart failure' MATCH (n) RETURN n //"
        self.retriever.search_trials(malicious, "spironolactone")
        self.assertNotIn(malicious, self.driver.calls[-1][0])
        self.assertIn(malicious.casefold(), self.driver.calls[-1][1].values())

    def test_invalid_input_limits_and_subsets_rejected_before_queries(self):
        before = len(self.driver.calls)
        for nct in (None, "NCT123", "NCT00206232 MATCH (n)"):
            with self.assertRaises(api.RetrievalError):
                self.retriever.trial_profile(nct)
        for limit, offset in ((0, 0), (201, 0), (50, -1), (True, 0)):
            with self.assertRaises(api.RetrievalError):
                self.retriever.trial_profile("NCT00206232", limit=limit, offset=offset)
        for subset in ([], ["NCT00206232"] * 2, ["NCT00206232"] * 21, "NCT00206232"):
            with self.assertRaises(api.RetrievalError):
                self.retriever.compare_planned_outcomes(subset)
        for condition in (None, " ", "x" * 201):
            with self.assertRaises(api.RetrievalError):
                self.retriever.search_trials(condition, "spironolactone")
        self.assertEqual(len(self.driver.calls), before)

    def test_unexpected_properties_are_never_exposed(self):
        self.driver.extra_properties = True
        result = self.retriever.trial_profile("NCT00206232")
        text = json.dumps(result)
        self.assertNotIn("PRIVATE-EXTRA", text)
        def keys(value):
            if isinstance(value, dict):
                return set(value) | set().union(*(keys(item) for item in value.values()))
            if isinstance(value, list):
                return set().union(*(keys(item) for item in value))
            return set()
        self.assertFalse(keys(result) & {"enrollment", "why_stopped", "overall_status"})
        # A registered measurement time frame legitimately says "enrollment";
        # field exclusion must not rewrite or censor verified source text.
        self.assertTrue(any("enrollment" in row["properties"].get("time_frame", "") for row in result["evidence"]))

    def test_page_mismatch_and_driver_errors_fail_closed_without_credentials(self):
        self.driver.drop_page_row = True
        with self.assertRaisesRegex(api.RetrievalError, "Page size"):
            self.retriever.trial_profile("NCT00206232")
        self.driver.query_error = True
        with self.assertRaises(api.RetrievalError) as caught:
            self.retriever.trial_profile("NCT00206232")
        for secret in ("private-user", "private-password", "secret-host"):
            self.assertNotIn(secret, str(caught.exception))

    def test_blank_source_fields_are_preserved_not_invented(self):
        result = self.retriever.trial_profile("NCT00206232")
        outcomes = [r for r in result["evidence"] if r["category"] == "planned_outcomes"]
        self.assertTrue(outcomes)
        self.assertTrue(all(r["properties"]["population"] == "" for r in outcomes))
        self.assertTrue(all("population" in r["missing_fields"] for r in outcomes))


if __name__ == "__main__":
    unittest.main()
