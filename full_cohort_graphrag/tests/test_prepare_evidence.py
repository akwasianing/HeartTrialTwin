"""Offline evidence adaptation using the existing pinned CSV/fake-driver fixture."""

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_retrieve import Fixture, FakeDriver
from full_cohort_graphrag.src import retrieve as api
from full_cohort_graphrag.src.prepare_evidence import prepare_evidence, EvidencePreparationError


class EvidencePreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = Fixture()

    def setUp(self):
        guard = patch("neo4j.GraphDatabase.driver", side_effect=AssertionError("Live connections prohibited"))
        guard.start()
        self.addCleanup(guard.stop)
        self.driver = FakeDriver(self.fixture)
        self.retriever = api.FullCohortRetriever(api.Config("bolt://127.0.0.1:7687", "test-user", "test-password"),
                                               driver=self.driver, contract=self.fixture.contract)
        self.retriever.verify_connection()

    def prepare(self, response, **kwargs):
        calls = len(self.driver.calls)
        result = prepare_evidence(response, contract=self.fixture.contract, **kwargs)
        self.assertEqual(len(self.driver.calls), calls, "Adapter must never fetch evidence")
        return result

    @staticmethod
    def records(bundle):
        return [record for trial in bundle["trials"] for records in trial["categories"].values() for record in records]

    def test_complete_profile_and_deterministic_summary(self):
        response = self.retriever.trial_profile("NCT00206232")
        original = copy.deepcopy(response)
        result = self.prepare(response)
        self.assertEqual(result["retrieval_status"], "COMPLETE")
        self.assertTrue(result["completeness"]["complete_evidence"])
        self.assertEqual(result["evidence_record_count"], 14)
        trial = result["trials"][0]
        self.assertEqual(len(trial["categories"]["submitted_conditions"]), 1)
        self.assertEqual(len(trial["categories"]["browse_conditions"]), 4)
        self.assertEqual(len(trial["categories"]["planned_outcomes"]), 7)
        self.assertEqual(trial["trial"], response["trial"])
        self.assertIn(api.PLANNED_SAFEGUARD, result["summary"])
        self.assertIn("not an LLM answer", result["summary"])
        self.assertEqual(result, self.prepare(response))
        self.assertEqual(response, original, "Preparation must not mutate input")

    def test_pagination_limited_profile_is_not_missing_outcomes(self):
        response = self.retriever.trial_profile("NCT05256303", limit=20)
        result = self.prepare(response)
        self.assertEqual(result["evidence_record_count"], 20)
        self.assertTrue(result["completeness"]["pagination_limited"])
        self.assertFalse(result["completeness"]["complete_evidence"])
        self.assertEqual(result["completeness"]["missing_source_records"], [])
        self.assertEqual(result["trials"][0]["categories"]["planned_outcomes"], [])
        self.assertEqual(result["trials"][0]["coverage"]["planned_outcomes"]["total"], 108)
        self.assertIn("Records exist but are not included in this page", result["summary"])

    def test_final_page_stays_response_local_partial(self):
        result = self.prepare(self.retriever.trial_profile("NCT05256303", limit=20, offset=140))
        self.assertEqual(result["evidence_record_count"], 16)
        self.assertEqual(result["retrieval_status"], "PARTIAL")
        self.assertTrue(result["completeness"]["pagination_limited"])
        self.assertFalse(result["scope"]["pagination"]["has_more"])

    def test_missing_browse_is_source_gap_not_pagination(self):
        result = self.prepare(self.retriever.trial_profile("NCT00057356", limit=200))
        self.assertFalse(result["completeness"]["pagination_limited"])
        self.assertEqual(result["completeness"]["missing_source_records"],
                         [{"nct_id": "NCT00057356", "categories": ["browse_conditions"]}])
        self.assertEqual(len(result["trials"][0]["categories"]["planned_outcomes"]), 3)
        self.assertIn("No linked record found in the pinned graph", result["summary"])

    def test_existing_trials_without_outcomes_are_retained(self):
        for nct in ("NCT00000475", "NCT00012818"):
            result = self.prepare(self.retriever.trial_profile(nct, limit=200))
            self.assertEqual(result["trials"][0]["nct_id"], nct)
            self.assertIsNotNone(result["trials"][0]["trial"])
            self.assertFalse(result["trials"][0]["state"]["not_found"])
            self.assertIn("planned_outcomes", result["completeness"]["missing_source_records"][0]["categories"])

    def test_nonexistent_profile_has_no_fabricated_facts_or_citations(self):
        result = self.prepare(self.retriever.trial_profile("NCT99999999"))
        self.assertEqual(result["retrieval_status"], "NOT_FOUND")
        self.assertEqual(result["completeness"]["not_found_nct_ids"], ["NCT99999999"])
        self.assertEqual(result["citations"], [])
        self.assertEqual(result["evidence_record_count"], 0)
        self.assertIsNone(result["trials"][0]["trial"])

    def test_search_preserves_multiple_trials_distinct_sponsors_and_outcomes(self):
        response = self.retriever.search_trials("heart failure", "spironolactone", limit=20, evidence_limit=200)
        result = self.prepare(response)
        self.assertEqual(len(result["trials"]), 12)
        sources = {p["nct_id"]: p for p in response["trial_profiles"]}
        sponsors = set()
        citations = {c["citation_id"]: c for c in result["citations"]}
        for trial in result["trials"]:
            nct = trial["nct_id"]
            self.assertEqual(trial["trial"], sources[nct]["trial"])
            expected = {r["evidence_id"] for r in sources[nct]["evidence"]}
            actual = {r["evidence_id"] for rows in trial["categories"].values() for r in rows}
            self.assertEqual(actual, expected)
            for record in trial["categories"]["lead_sponsors"]:
                sponsors.add(record["properties"]["name"])
            for record in [r for rows in trial["categories"].values() for r in rows]:
                self.assertEqual(record["relationship"]["start_id"], nct)
                for ref in record["citation_ids"]:
                    self.assertEqual(citations[ref]["nct_id"], nct)
                    self.assertEqual(citations[ref]["evidence_id"], record["evidence_id"])
        self.assertGreater(len(sponsors), 1)
        self.assertEqual(result["scope"]["search_parameters"]["condition_normalized"], "heart failure")

    def test_search_pages_do_not_claim_complete_cohort_coverage(self):
        result = self.prepare(self.retriever.search_trials("heart failure", "spironolactone", limit=2))
        self.assertEqual(len(result["trials"]), 2)
        self.assertEqual(result["scope"]["pagination"]["total"], 12)
        self.assertTrue(result["completeness"]["pagination_limited"])
        self.assertFalse(result["completeness"]["retrieval_scope_complete"])
        self.assertEqual(result["scope"]["pagination_unit"], "trials")

    def test_no_matching_search_records(self):
        result = self.prepare(self.retriever.search_trials("no matching condition", "no matching intervention"))
        self.assertEqual(result["retrieval_status"], "NOT_FOUND")
        self.assertEqual(result["trials"], [])
        self.assertFalse(result["completeness"]["source_categories_complete"])
        self.assertEqual(result["citations"], [])

    def test_comparison_preserves_exact_outcome_fields_and_source_records(self):
        response = self.retriever.compare_planned_outcomes(["NCT00206232", "NCT00391846"], limit=200)
        result = self.prepare(response)
        original = {r["evidence_id"]: r for r in response["evidence"]}
        self.assertEqual(len(self.records(result)), len(original))
        for record in self.records(result):
            self.assertEqual(record["properties"], original[record["evidence_id"]]["properties"])
            self.assertEqual(record["source_references"], original[record["evidence_id"]]["source_references"])
            self.assertEqual(record["properties"]["nct_id"], record["nct_id"])
        self.assertIn("no clinical equivalence", result["summary"])
        self.assertNotIn("shared_exact_measures", result)

    def test_partial_comparison_and_unknown_trial_are_explicit(self):
        result = self.prepare(self.retriever.compare_planned_outcomes(["NCT05256303", "NCT99999999"], limit=20))
        self.assertTrue(result["completeness"]["pagination_limited"])
        self.assertEqual(result["completeness"]["not_found_nct_ids"], ["NCT99999999"])
        self.assertEqual(result["evidence_record_count"], 20)

    def test_comparison_missing_outcomes_are_distinct_from_unknown_ids(self):
        result = self.prepare(self.retriever.compare_planned_outcomes(["NCT00000475", "NCT99999999"]))
        self.assertFalse(result["completeness"]["pagination_limited"])
        self.assertEqual(result["completeness"]["missing_source_records"],
                         [{"nct_id": "NCT00000475", "categories": ["planned_outcomes"]}])
        self.assertEqual(result["completeness"]["not_found_nct_ids"], ["NCT99999999"])

    def test_provenance_and_stable_citation_ids_are_preserved(self):
        response = self.retriever.trial_profile("NCT00206232")
        result = self.prepare(response)
        self.assertEqual(result["source_dataset"], response["source_dataset"])
        original = {r["evidence_id"]: r for r in response["evidence"]}
        for record in self.records(result):
            self.assertEqual(record["relationship"], original[record["evidence_id"]]["relationship"])
            self.assertEqual(record["missing_fields"], original[record["evidence_id"]]["missing_fields"])
        for ref in result["citations"]:
            self.assertEqual(ref["graph_version"], api.GRAPH)
            self.assertEqual(ref["dataset_version"], api.DATASET)
            self.assertEqual(ref["snapshot_date"], api.SNAPSHOT)
            self.assertEqual(ref["manifest_sha256"], api.MANIFEST_SHA256)
        response["retrieved_utc"] = "different-retrieval-time"
        self.assertEqual(result, self.prepare(response))

    def test_cross_trial_record_placement_is_rejected(self):
        response = self.retriever.search_trials("heart failure", "spironolactone", limit=2, evidence_limit=200)
        record = copy.deepcopy(response["trial_profiles"][0]["evidence"][0])
        response["trial_profiles"][1]["evidence"][0] = record
        with self.assertRaisesRegex(EvidencePreparationError, "Cross-trial"):
            self.prepare(response)

    def test_cross_trial_source_reference_is_rejected(self):
        response = self.retriever.trial_profile("NCT00206232")
        response["evidence"][0]["source_references"][0]["nct_id"] = "NCT00391846"
        with self.assertRaisesRegex(EvidencePreparationError, "Source references"):
            self.prepare(response)

    def test_wrong_sponsor_node_properties_are_rejected(self):
        response = self.retriever.trial_profile("NCT00206232")
        sponsor = next(r for r in response["evidence"] if r["category"] == "lead_sponsors")
        other = next(props for key, props in self.fixture.nodes["Sponsor"].items() if key != sponsor["node_id"])
        sponsor["properties"]["sponsor_id"] = other["sponsor_id"]
        sponsor["properties"]["name"] = other["name"]
        with self.assertRaisesRegex(EvidencePreparationError, "identifier/source"):
            self.prepare(response)

    def test_wrong_outcome_trial_binding_is_rejected(self):
        response = self.retriever.trial_profile("NCT00206232")
        outcome = next(r for r in response["evidence"] if r["category"] == "planned_outcomes")
        outcome["properties"]["nct_id"] = "NCT00391846"
        with self.assertRaisesRegex(EvidencePreparationError, "trial/source/safeguard"):
            self.prepare(response)

    def test_mixed_graph_versions_and_missing_source_identifiers_rejected(self):
        response = self.retriever.trial_profile("NCT00206232")
        bad = copy.deepcopy(response)
        bad["graph_version"] = "HTT-KG-AACT-20260905-v1"
        with self.assertRaisesRegex(EvidencePreparationError, "version"):
            self.prepare(bad)
        bad = copy.deepcopy(response)
        bad["evidence"][0]["relationship"]["properties"]["source_record_ids"] = ""
        with self.assertRaisesRegex(EvidencePreparationError, "source-record"):
            self.prepare(bad)

    def test_false_complete_flags_and_flat_nested_disagreement_rejected(self):
        response = self.retriever.trial_profile("NCT05256303", limit=20)
        response["status"] = "COMPLETE"
        with self.assertRaisesRegex(EvidencePreparationError, "status falsely"):
            self.prepare(response)
        response = self.retriever.compare_planned_outcomes(["NCT00206232"])
        response["evidence"] = []
        with self.assertRaisesRegex(EvidencePreparationError, "top-level and per-trial"):
            self.prepare(response)

    def test_record_and_summary_budgets_reject_without_silent_truncation(self):
        response = self.retriever.trial_profile("NCT00206232")
        with self.assertRaisesRegex(EvidencePreparationError, "record budget"):
            self.prepare(response, max_records=1)
        with self.assertRaisesRegex(EvidencePreparationError, "Summary budget"):
            self.prepare(response, max_summary_characters=100)
        self.assertEqual(len(response["evidence"]), 14)

    def test_unknown_properties_duplicates_and_missing_classification_rejected(self):
        response = self.retriever.trial_profile("NCT00206232")
        bad = copy.deepcopy(response)
        bad["evidence"][0]["properties"]["enrollment"] = "not-approved"
        with self.assertRaisesRegex(EvidencePreparationError, "Unexpected evidence properties"):
            self.prepare(bad)
        bad = copy.deepcopy(response)
        bad["evidence"].append(copy.deepcopy(bad["evidence"][0]))
        with self.assertRaisesRegex(EvidencePreparationError, "Duplicate evidence"):
            self.prepare(bad)
        bad = copy.deepcopy(response)
        bad["evidence"][0]["properties"]["source_kind"] = "submitted"
        with self.assertRaisesRegex(EvidencePreparationError, "classification"):
            self.prepare(bad)

    def test_blank_fields_and_input_order_do_not_change_facts(self):
        response = self.retriever.trial_profile("NCT00206232")
        expected = self.prepare(response)
        response["evidence"].reverse()
        actual = self.prepare(response)
        self.assertEqual(expected, actual)
        for record in self.records(actual):
            if record["category"] == "planned_outcomes":
                self.assertEqual(record["properties"]["population"], "")
                self.assertIn("population", record["missing_fields"])
        json.dumps(actual, ensure_ascii=False)

    def test_absent_optional_field_is_not_fabricated_as_blank_source_value(self):
        response = self.retriever.trial_profile("NCT00206232")
        record = next(r for r in response["evidence"] if r["category"] == "planned_outcomes")
        del record["properties"]["time_frame"]
        result = self.prepare(response)
        prepared = next(r for r in self.records(result) if r["evidence_id"] == record["evidence_id"])
        self.assertNotIn("time_frame", prepared["properties"])
        self.assertIn("time_frame", prepared["absent_fields"])
        self.assertIn("time_frame=<not supplied>", result["summary"])


if __name__ == "__main__":
    unittest.main()
