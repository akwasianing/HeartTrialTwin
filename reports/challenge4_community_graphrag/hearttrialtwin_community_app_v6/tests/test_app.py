"""Real local evidence/UI smoke tests; external services are forbidden."""
import logging
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import integrity


class AppTests(unittest.TestCase):
    def setUp(self):
        # Fail rather than accidentally making a network/LLM call in these tests.
        self.net = patch("urllib.request.urlopen", side_effect=AssertionError("External request forbidden"))
        self.net.start()
        self.addCleanup(self.net.stop)

    def app(self):
        app = AppTest.from_file(str(HERE / "app.py"), default_timeout=70).run()
        self.assertFalse(app.exception)
        return app

    def field(self, app, value):
        next(v for v in app.selectbox if v.key == "v6_verified_field").set_value(value).run()
        next(b for b in app.button if b.key == "v6_verified_get").click().run()
        self.assertFalse(app.exception)
        return app.session_state["v6_verified_answer"]["result"]

    def test_startup_five_pages_and_default_trial(self):
        app = self.app()
        self.assertEqual(len(app.sidebar.radio[0].options), 5)
        self.assertEqual(next(t for t in app.text_input if t.key == "v6_guided_nct").value, "NCT00206232")
        self.assertTrue(any("Version 6" in t.value for t in app.caption))
        self.assertEqual(next(m for m in app.metric if m.label == "Registered planned outcomes").value, "7")

    def test_real_sponsor_and_intervention_citations(self):
        app = self.app()
        for field, expected in [("lead sponsor", "Baylor College of Medicine"), ("intervention", "Spironolactone")]:
            result = self.field(app, field)
            self.assertEqual(result["status"], "GROUNDED")
            self.assertIn(expected, result["answer"])
            self.assertIn("[cite:", result["answer"])
            self.assertEqual(result["model_attempts"], 0)
            refs = {r["citation_id"]: r for r in result["prepared_evidence"]["citations"]}
            for fact in result["answer_trace"]["validation"]["accepted_facts"]:
                for cid in fact["citation_ids"]:
                    self.assertEqual(refs[cid]["nct_id"], "NCT00206232")

    def test_seven_outcomes_exact_trial_bound_evidence(self):
        app = self.app()
        result = self.field(app, "planned outcomes")
        self.assertEqual(result["status"], "COMPLETE_LISTING")
        self.assertEqual(result["model_attempts"], 0)
        listed = result["answer_trace"]["listed_outcomes"]
        refs = {r["citation_id"]: r for r in result["prepared_evidence"]["citations"]}
        self.assertEqual(len({r["evidence_id"] for r in listed}), 7)
        self.assertEqual(len(listed), 7)
        for fact in listed:
            self.assertEqual(fact["nct_id"], "NCT00206232")
            for cid in fact["citation_ids"]:
                self.assertEqual(refs[cid]["nct_id"], fact["nct_id"])
                self.assertEqual(refs[cid]["evidence_id"], fact["evidence_id"])
        self.assertIn("not observed clinical results", result["answer"])
        self.assertIn("2026-09-05", result["answer"])

    def test_unknown_and_invalid_ids_show_no_fabricated_evidence(self):
        app = self.app()
        for nct in ["NCT99999999", "invalid"]:
            next(t for t in app.text_input if t.key == "v6_guided_nct").set_value(nct).run()
            self.assertFalse(app.exception)
            self.assertFalse(app.metric)
            self.assertFalse(any(b.key == "v6_verified_get" for b in app.button))

    def test_missing_outcomes_abstain(self):
        app = self.app()
        next(t for t in app.text_input if t.key == "v6_guided_nct").set_value("NCT00000475").run()
        result = self.field(app, "planned outcomes")
        self.assertEqual(result["status"], "ABSTAIN")
        self.assertEqual(result["answer_trace"]["listed_outcomes"], [])
        self.assertFalse(result["answer_trace"]["validation"]["passed"])
        self.assertTrue(result["prepared_evidence"]["citations"])

    def test_effectiveness_and_cross_trial_questions_abstain(self):
        app = self.app()
        for question in ["Did spironolactone improve survival in NCT00206232?",
                         "What intervention was registered for NCT00391846?"]:
            next(t for t in app.text_input if t.key == "v6_custom_question").set_value(question).run()
            next(b for b in app.button if b.key == "v6_verified_get").click().run()
            self.assertEqual(app.session_state["v6_verified_answer"]["result"]["status"], "ABSTAIN")

    def test_changing_field_hides_stale_answer(self):
        app = self.app()
        self.field(app, "lead sponsor")
        next(v for v in app.selectbox if v.key == "v6_verified_field").set_value("phase").run()
        self.assertFalse(app.text)

    def test_community_evidence_and_feedback_without_ollama(self):
        app = self.app()
        app.sidebar.radio[0].set_value("Community Explorer").run()
        next(t for t in app.text_input if t.key == "v6_community_search").set_value("NCT00206232").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("904" == m.value for m in app.metric))
        self.assertFalse(any("Generate" in b.label or "Revise" in b.label for b in app.button))
        self.assertTrue(any("disabled" in v.value for v in app.info))
        next(b for b in app.button if b.key == "v6_record_feedback").click().run()
        self.assertEqual(app.session_state["v6_feedback_records"][0]["anchor_nct_id"], "NCT00206232")

    def test_phase_filters_and_blocked_dashboard(self):
        app = self.app()
        app.sidebar.radio[0].set_value("Phase and Intervention Explorer").run()
        app.selectbox[0].set_value("NA").run()
        app.selectbox[1].set_value("DRUG").run()
        self.assertEqual(app.metric[0].value, "115")
        app.sidebar.radio[0].set_value("Operational Risk Dashboard").run()
        self.assertFalse(app.exception)
        self.assertEqual(next(m for m in app.metric if m.label == "Binary evaluable").value, "329")
        self.assertEqual(next(m for m in app.metric if m.label == "2021–24 ROC-AUC").value, "0.487")
        self.assertTrue(any("BLOCKED" in e.value for e in app.error))

    def test_scenario_acknowledgement_gate(self):
        app = self.app()
        app.sidebar.radio[0].set_value("Digital Trial-Twin Scenario Lab").run()
        next(b for b in app.button if b.key == "load_profiles").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["historical_profiles"]["count"], 257)
        self.assertTrue(next(b for b in app.button if b.key == "scenario_run").disabled)
        self.assertTrue(any("noncausal" in e.value or "causal" in e.value for e in app.error))
        next(s for s in app.selectbox if s.key == "scenario_nct").set_value("NCT03015402").run()
        next(v for v in app.number_input if v.key == "hypothetical_NCT03015402").set_value(39).run()
        next(c for c in app.checkbox if c.key == "research_ack").check().run()
        next(b for b in app.button if b.key == "scenario_run").click().run()
        self.assertFalse(app.exception)
        result = app.session_state["scenario_result"]
        self.assertEqual((result["baseline_planned_enrollment"], result["hypothetical_planned_enrollment"]), (26, 39))
        self.assertEqual(len(result["scores"]), 4)
        self.assertEqual(result["model_fits"], 0)
        self.assertFalse(result["source_evidence_written"])
        self.assertEqual(result["forecasting_release"], "BLOCKED_UNCHANGED")

    def test_integrity_failure_blocks_the_entire_app(self):
        with patch.object(integrity, "verify_runtime", side_effect=integrity.IntegrityError("fixture failure")):
            app = AppTest.from_file(str(HERE / "app.py"), default_timeout=70).run()
        self.assertFalse(app.exception)
        self.assertTrue(any("failed verification" in e.value for e in app.error))
        self.assertFalse(app.button)

    def test_timeout_and_backend_failure_remain_abstentions(self):
        import client
        import subprocess
        app = self.app()
        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="fixture-worker", timeout=60)
        def unavailable(*args, **kwargs):
            raise OSError("fixture worker missing")
        for runner, code in [(timeout, "LOCAL_WORKER_TIMEOUT"), (unavailable, "LOCAL_WORKER_FAILURE")]:
            result = client.request({"action": "answer", "question": "What title was registered for NCT00206232?"},
                                    runner=runner)
            self.assertEqual(result["status"], "ABSTAIN")
            self.assertEqual(result["error_code"], code)
            with patch.object(client, "request", return_value=result):
                next(b for b in app.button if b.key == "v6_verified_get").click().run()
            self.assertTrue(any("No automatic retry" in t.value or "No result was fabricated" in t.value
                                for t in app.text))


if __name__ == "__main__":
    unittest.main()
