"""Offline complete-listing tests; reuse pinned fixtures, prohibit all network."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_retrieve import Fixture, FakeDriver
from full_cohort_graphrag.src import retrieve as api
from full_cohort_graphrag.src import list_planned_outcomes as listing
from full_cohort_graphrag.src.generate_answer import GenerationInputError, save_trace
from full_cohort_graphrag.src.prepare_evidence import prepare_evidence


class CompleteOutcomeListingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = Fixture()

    def setUp(self):
        self.network_guards = []
        for name in ("neo4j.GraphDatabase.driver", "urllib.request.urlopen"):
            guard = patch(name, side_effect=AssertionError("Live services prohibited"))
            self.network_guards.append(guard.start())
            self.addCleanup(guard.stop)
        self.driver = FakeDriver(self.fixture)
        self.retriever = api.FullCohortRetriever(api.Config("bolt://127.0.0.1:7687", "offline", "offline"),
                                               driver=self.driver, contract=self.fixture.contract)
        self.retriever.verify_connection()
        self.bundle = self.prepare(self.retriever.trial_profile("NCT00206232"))
        self.question = "What planned outcomes were registered for NCT00206232?"

    def prepare(self, raw):
        return prepare_evidence(raw, contract=self.fixture.contract)

    def run_listing(self, *, bundle=None, question=None, **limits):
        bundle = self.bundle if bundle is None else bundle
        question = self.question if question is None else question
        original = copy.deepcopy(bundle)
        calls = len(self.driver.calls)
        result = listing.list_registered_planned_outcomes(question, bundle, contract=self.fixture.contract, **limits)
        self.assertEqual(bundle, original)
        self.assertEqual(len(self.driver.calls), calls, "Listing must not retrieve any additional evidence")
        for guard in self.network_guards:
            guard.assert_not_called()
        self.assertEqual(result["generation"]["attempts"], 0)
        self.assertEqual(result["generation"]["maximum_attempts"], 0)
        self.assertIsNone(result["raw_model_output"])
        self.assertFalse(result["model_generated"])
        return result

    def test_all_seven_outcomes_match_exact_pinned_source_and_citations(self):
        result = self.run_listing()
        self.assertEqual(result["status"], "COMPLETE_LISTING")
        self.assertTrue(result["validation"]["passed"])
        self.assertTrue(result["validation"]["complete_source_set"])
        records = self.bundle["trials"][0]["categories"]["planned_outcomes"]
        original = {row["evidence_id"]: row for row in records}
        pinned = {f"NCT00206232|HAS_PLANNED_OUTCOME|{row['evidence_id']}": row for row in self.fixture.by_trial["NCT00206232"]
                  if row["relationship_type"] == "HAS_PLANNED_OUTCOME"}
        rows = result["listed_outcomes"]
        self.assertEqual(len(rows), 7)
        self.assertEqual(len({row["evidence_id"] for row in rows}), 7)
        self.assertEqual({row["evidence_id"] for row in rows}, set(original))
        self.assertEqual(set(result["validation"]["listed_evidence_ids"]), set(pinned))
        self.assertEqual(result["validation"]["expected_evidence_ids"], sorted(pinned))
        references = {ref["citation_id"]: ref for ref in result["source_references"]}
        for row in rows:
            with self.subTest(evidence_id=row["evidence_id"]):
                source = pinned[row["evidence_id"]]["evidence_properties"]
                for field in ("measure", "outcome_type", "time_frame", "source_record_id", "nct_id"):
                    self.assertEqual(row["properties"].get(field), source.get(field))
                self.assertEqual(row["nct_id"], "NCT00206232")
                for field, value in original[row["evidence_id"]].items():
                    self.assertEqual(row[field], value)
                entry = result["fact_catalog"]["entries"][row["fact_id"]]
                self.assertEqual(row["sentence"], entry["sentence"])
                self.assertEqual(row["citation_ids"], entry["fact"]["citation_ids"])
                self.assertEqual(result["answer"].count(row["sentence"]), 1)
                for key in row["citation_ids"]:
                    ref = references[key]
                    self.assertEqual(ref["nct_id"], row["nct_id"])
                    self.assertEqual(ref["evidence_id"], row["evidence_id"])
                    self.assertEqual(ref["source_table"], "design_outcomes.txt")
                    self.assertEqual(ref["source_record_id"], source["source_record_id"])
                    self.assertEqual(ref["relationship"], row["relationship"])
                    self.assertEqual(ref["dataset_version"], api.DATASET)
                    self.assertEqual(ref["graph_version"], api.GRAPH)
                    self.assertEqual(ref["snapshot_date"], api.SNAPSHOT)
        self.assertIn(api.PLANNED_SAFEGUARD, result["answer"])
        self.assertIn(api.SNAPSHOT_SAFEGUARD, result["answer"])
        self.assertIn("not model-generated", result["answer"])
        self.assertEqual(result["verified_evidence"], self.bundle)
        self.assertEqual(result["deterministic_evidence_summary"], self.bundle["summary"])

    def test_listing_and_hashes_are_deterministic_and_trace_saves_exclusively(self):
        first, second = self.run_listing(), self.run_listing()
        for field in ("answer", "listed_outcomes", "validation", "fact_catalog", "prepared_evidence_sha256", "limits"):
            self.assertEqual(first[field], second[field])
        self.assertEqual(first["answer_origin"], "DETERMINISTIC_VERIFIED_EVIDENCE")
        self.assertIsNone(first["generation"]["actual_model"])
        self.assertIsNone(first["generation"]["eval_count"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "listing.json"
            save_trace(first, path)
            self.assertEqual(json.loads(path.read_text()), first)
            with self.assertRaises(FileExistsError):
                save_trace(first, path)

    def test_unsupported_or_nonexplicit_questions_abstain(self):
        cases = [("What intervention is registered for clinical trial NCT00206232?", "UNSUPPORTED_LISTING_QUESTION"),
                 ("Did spironolactone improve survival in NCT00206232?", "UNSUPPORTED_LISTING_QUESTION"),
                 ("What outcomes were observed for NCT00206232?", "UNSUPPORTED_LISTING_QUESTION"),
                 ("What planned outcomes are registered for the selected trials?", "SINGLE_TRIAL_LISTING_REQUIRED"),
                 ("What planned outcomes are registered for trials NCT00206232 and NCT00391846?", "SINGLE_TRIAL_LISTING_REQUIRED"),
                 ("What planned outcomes were registered for NCT00391846?", "QUESTION_SCOPE_MISMATCH")]
        for question, code in cases:
            with self.subTest(question=question):
                result = self.run_listing(question=question)
                self.assertEqual(result["status"], "ABSTAIN")
                self.assertEqual(result["validation"]["errors"], [code])
                self.assertEqual(result["listed_outcomes"], [])

    def test_missing_source_unknown_trial_and_pagination_abstain(self):
        cases = [("NCT00000475", 200, 0, "MISSING_SOURCE_RECORDS"),
                 ("NCT00057356", 200, 0, "MISSING_SOURCE_RECORDS"),
                 ("NCT99999999", 200, 0, "NOT_FOUND"),
                 ("NCT05256303", 20, 0, "PAGINATION_LIMITED"),
                 ("NCT05256303", 20, 140, "PAGINATION_LIMITED")]
        for nct, limit, offset, code in cases:
            with self.subTest(nct=nct, offset=offset):
                bundle = self.prepare(self.retriever.trial_profile(nct, limit=limit, offset=offset))
                result = self.run_listing(bundle=bundle, question=f"What planned outcomes were registered for {nct}?")
                self.assertEqual(result["status"], "ABSTAIN")
                self.assertIn(code, result["validation"]["errors"])
                self.assertEqual(result["validation"]["listed_evidence_ids"], [])
                self.assertEqual(result["verified_evidence"], bundle)

    def test_multi_trial_evidence_is_not_silently_filtered_to_one_trial(self):
        bundle = self.prepare(self.retriever.compare_planned_outcomes(["NCT00206232", "NCT00391846"], limit=200))
        result = self.run_listing(bundle=bundle)
        self.assertEqual(result["validation"]["errors"], ["SINGLE_TRIAL_LISTING_REQUIRED"])

    def test_blank_measure_abstains_but_missing_optional_values_are_explicit(self):
        for field in ("measure", "time_frame", "outcome_type"):
            with self.subTest(field=field):
                raw = self.retriever.trial_profile("NCT00206232")
                row = next(row for row in raw["evidence"] if row["category"] == "planned_outcomes")
                # Simulate unavailable data by removing a value, never inventing one.
                row["properties"][field] = ""
                row["missing_fields"] = sorted(key for key, value in row["properties"].items() if value == "")
                bundle = self.prepare(raw)
                result = self.run_listing(bundle=bundle)
                if field == "measure":
                    self.assertEqual(result["validation"]["errors"], ["INCOMPLETE_RELEVANT_VALUES"])
                    self.assertEqual(result["listed_outcomes"], [])
                else:
                    self.assertEqual(result["status"], "COMPLETE_LISTING")
                    listed = next(r for r in result["listed_outcomes"] if r["evidence_id"] == row["evidence_id"])
                    self.assertEqual(listed["properties"][field], "")
                    self.assertIn(field, listed["missing_optional_values"])
                    self.assertIn(f"{field}: unavailable in the supplied evidence.", result["answer"])

    def test_incomplete_duplicate_or_fabricated_catalog_source_sets_are_rejected(self):
        original = listing.build_fact_catalog(self.bundle)
        outcome_texts = [text for text, fact in original.items() if fact["field"] == "planned outcome measure"]
        missing = copy.deepcopy(original)
        del missing[outcome_texts[0]]
        duplicate = copy.deepcopy(original)
        duplicate[outcome_texts[1]]["evidence_id"] = duplicate[outcome_texts[0]]["evidence_id"]
        fabricated = copy.deepcopy(original)
        fabricated[outcome_texts[0]]["evidence_id"] = "NONEXISTENT-EVIDENCE-ID"
        for catalog in (missing, duplicate, fabricated):
            with patch.object(listing, "build_fact_catalog", return_value=catalog):
                result = self.run_listing()
            self.assertEqual(result["validation"]["errors"], ["LISTING_SOURCE_SET_MISMATCH"])
            self.assertEqual(result["listed_outcomes"], [])

    def test_wrong_catalog_citation_is_rejected_without_partial_output(self):
        catalog = listing.build_fact_catalog(self.bundle)
        fact = next(f for f in catalog.values() if f["field"] == "planned outcome measure")
        fact["citation_ids"] = ["cite:" + "f" * 24]
        with patch.object(listing, "build_fact_catalog", return_value=catalog):
            result = self.run_listing()
        self.assertEqual(result["validation"]["errors"], ["LISTING_CITATION_MISMATCH"])
        self.assertEqual(result["listed_outcomes"], [])

    def test_output_caps_publish_all_or_none_including_exact_byte_boundary(self):
        complete = self.run_listing()
        size = len(complete["answer"].encode("utf-8"))
        self.assertEqual(size, complete["limits"]["required_answer_bytes"])
        for limits in ({"max_outcomes": 6}, {"max_answer_bytes": size - 1}):
            result = self.run_listing(**limits)
            self.assertEqual(result["status"], "ABSTAIN")
            self.assertEqual(result["validation"]["errors"], ["LISTING_OUTPUT_LIMIT_EXCEEDED"])
            self.assertEqual(result["listed_outcomes"], [])
            self.assertEqual(result["validation"]["listed_evidence_ids"], [])
            self.assertFalse(result["validation"]["complete_source_set"])
            self.assertEqual(result["verified_evidence"], self.bundle)
        boundary = self.run_listing(max_answer_bytes=size, max_outcomes=7)
        self.assertEqual(boundary["status"], "COMPLETE_LISTING")
        self.assertEqual(boundary["answer"], complete["answer"])

    def test_invalid_caller_inputs_and_tampered_prepared_evidence_are_rejected(self):
        for limits in ({"max_outcomes": 0}, {"max_outcomes": True}, {"max_outcomes": listing.MAX_OUTCOMES + 1},
                       {"max_answer_bytes": 0}, {"max_answer_bytes": listing.MAX_ANSWER_BYTES + 1}):
            with self.assertRaises(GenerationInputError):
                self.run_listing(**limits)
        for question in ("", "a" * 2001, None):
            with self.assertRaises(GenerationInputError):
                listing.list_registered_planned_outcomes(question, self.bundle, contract=self.fixture.contract)
        bundle = copy.deepcopy(self.bundle)
        bundle["citations"][0]["nct_id"] = "NCT00391846"
        with self.assertRaises(GenerationInputError):
            self.run_listing(bundle=bundle)


if __name__ == "__main__":
    unittest.main()
