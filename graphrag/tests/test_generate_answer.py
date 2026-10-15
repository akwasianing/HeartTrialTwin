"""Mocked tests for grounded HeartTrialTwin GraphRAG answer generation."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "graphrag" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

spec = importlib.util.spec_from_file_location(
    "graphrag_generate_answer", SRC_DIR / "generate_answer.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load graphrag/src/generate_answer.py")
generation = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = generation
spec.loader.exec_module(generation)


def sample_evidence() -> dict:
    return {
        "question_id": "1",
        "question": "What information is registered for clinical trial NCT00206232?",
        "dataset_version": "HTT-P1-AACT-20260905",
        "graph_version": "HTT-KG-AACT-20260905-v1",
        "row_count": 1,
        "safeguards": {
            "planned_outcomes": "Registered planned outcome — not a clinical result.",
        },
        "evidence": [
            {
                "trial": {
                    "nct_id": "NCT00206232",
                    "brief_title": "Test trial",
                },
                "evidence_paths": [
                    {
                        "relationship_type": "HAS_PLANNED_OUTCOME",
                        "evidence_labels": ["PlannedOutcome"],
                        "evidence_properties": {
                            "planned_outcome_id": "planned_outcome:1426534673",
                            "source_record_id": "1426534673",
                            "measure": "Six minute walk distance",
                            "source_table": "design_outcomes.txt",
                            "dataset_version": "HTT-P1-AACT-20260905",
                        },
                    },
                    {
                        "relationship_type": "MEMBER_OF_DATASET",
                        "evidence_labels": ["SourceDataset"],
                        "evidence_properties": {
                            "source_dataset_id": "HTT-P1-AACT-20260905",
                            "dataset_version": "HTT-P1-AACT-20260905",
                            "snapshot_date": "2026-09-05",
                        },
                    },
                ],
            }
        ],
    }


def sample_question2_evidence() -> dict:
    rows = []
    for trial_index in range(5):
        nct_id = f"NCT{trial_index + 1:08d}"
        for outcome_index in range(2):
            source_record_id = str(1000 + trial_index * 2 + outcome_index)
            rows.append(
                {
                    "nct_id": nct_id,
                    "brief_title": f"Illustrative trial {trial_index + 1}",
                    "condition": {
                        "condition_id": "condition:heart-failure",
                        "name": "Heart Failure",
                    },
                    "intervention": {
                        "intervention_id": "intervention:spironolactone",
                        "name": "Spironolactone",
                    },
                    "sponsor": {
                        "sponsor_id": f"sponsor:{trial_index + 1}",
                        "name": f"Verified Sponsor {trial_index + 1}",
                    },
                    "planned_outcome": {
                        "planned_outcome_id": f"planned_outcome:{source_record_id}",
                        "source_record_id": source_record_id,
                        "measure": f"Registered measure {trial_index + 1}-{outcome_index + 1}",
                        "outcome_type": "primary" if outcome_index == 0 else "secondary",
                        "time_frame": "Six months",
                        "nct_id": nct_id,
                    },
                    "source_dataset": {
                        "dataset_version": "HTT-P1-AACT-20260905",
                        "snapshot_date": "2026-09-05",
                    },
                }
            )
    return {
        "question_id": "2",
        "question": "Which sponsors and planned outcomes are registered?",
        "dataset_version": "HTT-P1-AACT-20260905",
        "graph_version": "HTT-KG-AACT-20260905-v1",
        "evidence": rows,
    }


VALID_EXPLANATION = (
    "NCT00206232 registered Six minute walk distance as a planned outcome."
)


class FakeResponses:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_text=self.answer,
            id="resp_test_123",
            model=kwargs["model"],
            usage={"input_tokens": 100, "output_tokens": 40, "total_tokens": 140},
        )


class FakeClient:
    def __init__(self, answer: str) -> None:
        self.responses = FakeResponses(answer)


class FakeHTTPResponse:
    def __init__(self, payload) -> None:
        if isinstance(payload, bytes):
            self.payload = payload
        else:
            self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self):
        return self.payload


class FakeUrlOpen:
    def __init__(self, generate_responses=None, *, tags=None, error=None) -> None:
        self.generate_responses = list(generate_responses or [])
        self.tags = tags or {"models": [{"name": "qwen2.5:1.5b"}]}
        self.error = error
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append({"request": request, "timeout": timeout})
        if self.error is not None:
            raise self.error
        if request.full_url.endswith("/api/tags"):
            return FakeHTTPResponse(self.tags)
        if not self.generate_responses:
            raise AssertionError("No fake Ollama generation response remains")
        return FakeHTTPResponse(self.generate_responses.pop(0))


class FakeRetriever:
    def __init__(self, evidence: dict) -> None:
        self.evidence = evidence
        self.calls: list[tuple] = []

    def question_1(self, nct_id: str):
        self.calls.append(("1", nct_id))
        return self.evidence

    def question_2(self):
        self.calls.append(("2",))
        return self.evidence

    def question_3(self):
        self.calls.append(("3",))
        return self.evidence


class GroundedGenerationTests(unittest.TestCase):
    def generator(self, answer: str = VALID_EXPLANATION):
        client = FakeClient(answer)
        instance = generation.OpenAIAnswerGenerator(
            api_key="test-key-not-real",
            model=generation.DEFAULT_MODEL,
            client=client,
        )
        return instance, client

    def test_model_input_contains_only_question_and_retrieved_evidence(self) -> None:
        evidence = sample_evidence()
        text = generation.build_model_input(evidence["question"], evidence)
        payload = json.loads(text)
        self.assertEqual(
            set(payload), {"user_question", "retrieved_kg_evidence"}
        )
        self.assertEqual(payload["user_question"], evidence["question"])
        compact = payload["retrieved_kg_evidence"]
        self.assertEqual(compact["dataset_version"], "HTT-P1-AACT-20260905")
        self.assertEqual(
            compact["trial_evidence"][0]["trial"]["nct_id"], "NCT00206232"
        )
        planned = compact["trial_evidence"][0]["planned_outcomes"][0]
        self.assertEqual(planned["source_record_id"], "1426534673")
        self.assertLess(len(text), len(json.dumps(evidence)) + len(evidence["question"]))

    def test_responses_api_parameters_and_valid_answer(self) -> None:
        evidence = sample_evidence()
        generator, client = self.generator()
        result = generator.generate(evidence["question"], evidence)
        self.assertEqual(result["status"], "grounded")
        self.assertTrue(result["answer"].startswith(VALID_EXPLANATION))
        self.assertIn(
            "[source_record_id: 1426534673]", result["generated_evidence_section"]
        )
        self.assertIn("2026-09-05", result["generated_evidence_section"])
        self.assertIn(
            generation.PLANNED_OUTCOME_SAFEGUARD, result["answer"]
        )
        self.assertTrue(result["grounding_validation"]["passed"])
        self.assertTrue(result["substantive_claim_validation"]["passed"])
        call = client.responses.calls[0]
        self.assertEqual(call["model"], "gpt-6-luna")
        self.assertEqual(call["reasoning"], {"effort": "none"})
        self.assertEqual(call["max_output_tokens"], 1200)
        self.assertFalse(call["store"])
        self.assertNotIn("test-key-not-real", json.dumps(result))

    def test_unsupported_nct_identifier_is_blocked(self) -> None:
        answer = VALID_EXPLANATION.replace("NCT00206232", "NCT99999999")
        generator, _ = self.generator(answer)
        result = generator.generate(sample_evidence()["question"], sample_evidence())
        self.assertEqual(result["status"], "blocked_unsupported_claims")
        self.assertTrue(result["answer"].startswith("ABSTAIN:"))
        self.assertIn(
            "unsupported_nct_id:NCT99999999",
            result["grounding_validation"]["errors"],
        )
        self.assertEqual(result["raw_model_output"], answer)

    def test_unsupported_source_record_identifier_is_blocked(self) -> None:
        answer = (
            VALID_EXPLANATION
            + " [source_record_id: 9999999999]"
        )
        generator, _ = self.generator(answer)
        result = generator.generate(sample_evidence()["question"], sample_evidence())
        self.assertEqual(result["status"], "blocked_unsupported_claims")
        self.assertIn(
            "unsupported_source_record_id:9999999999",
            result["grounding_validation"]["errors"],
        )

    def test_provenance_and_safeguard_are_constructed_deterministically(self) -> None:
        generator, _ = self.generator(VALID_EXPLANATION)
        result = generator.generate(sample_evidence()["question"], sample_evidence())
        self.assertEqual(result["status"], "grounded")
        section = result["generated_evidence_section"]
        self.assertIn("NCT00206232", section)
        self.assertIn("[source_record_id: 1426534673]", section)
        self.assertIn("HTT-P1-AACT-20260905", section)
        self.assertIn("2026-09-05", section)
        self.assertTrue(result["provenance_construction"]["ready"])

    def test_missing_metadata_abstains_without_fabrication(self) -> None:
        evidence = sample_evidence()
        del evidence["evidence"][0]["evidence_paths"][1]["evidence_properties"][
            "snapshot_date"
        ]
        generator, client = self.generator(VALID_EXPLANATION)
        result = generator.generate(evidence["question"], evidence)
        self.assertEqual(result["status"], "missing_evidence_metadata")
        self.assertTrue(result["answer"].startswith("ABSTAIN:"))
        self.assertIn(
            "missing_snapshot_date_metadata",
            result["provenance_construction"]["errors"],
        )
        self.assertNotIn("2026-09-05", result["generated_evidence_section"])
        self.assertEqual(len(client.responses.calls), 1)

    def test_unsupported_claim_is_not_rescued_by_deterministic_citations(self) -> None:
        unsupported = "NCT00206232 improved survival."
        generator, _ = self.generator(unsupported)
        result = generator.generate(sample_evidence()["question"], sample_evidence())
        self.assertEqual(result["status"], "blocked_unsupported_claims")
        self.assertTrue(result["answer"].startswith("ABSTAIN:"))
        self.assertIn("[source_record_id: 1426534673]", result["generated_evidence_section"])
        self.assertFalse(result["substantive_claim_validation"]["passed"])
        self.assertTrue(
            any(
                "unsupported_clinical_claim_pattern:" in error
                for error in result["substantive_claim_validation"]["errors"]
            )
        )

    def test_legitimate_phase_hyphenation_and_heading_are_normalized(self) -> None:
        evidence = sample_evidence()
        evidence["evidence"][0]["trial"]["phase"] = "PHASE4"
        explanation = (
            "Key information includes:\n"
            "- Phase: Phase 4\n"
            "- Primary outcome: Six-minute walk distance."
        )
        result = generation.finalize_generated_answer(explanation, evidence)
        self.assertEqual(result["status"], "grounded")
        self.assertTrue(result["substantive_claim_validation"]["passed"])

    def test_sha256_and_planned_outcome_metadata_headings_are_not_claims(self) -> None:
        evidence = sample_evidence()
        evidence["evidence"][0]["evidence_paths"][1]["evidence_properties"][
            "pinned_manifest_sha256"
        ] = "5a2d6bbb0973a45988275efb4e9caff8400438edf4e3c560b1b7c0b1688fe7ab"
        evidence["evidence"][0]["evidence_paths"][0]["evidence_properties"][
            "time_frame"
        ] = "Baseline"
        explanation = (
            "Pinned Manifest SHA256: "
            "5a2d6bbb0973a45988275efb4e9caff8400438edf4e3c560b1b7c0b1688fe7ab\n"
            "Planned Outcome ID: planned_outcome:1426534673\n"
            "Planned Outcome NCT ID: NCT00206232\n"
            "Planned Outcome Time Frame: baseline"
        )
        result = generation.finalize_generated_answer(explanation, evidence)
        self.assertEqual(result["status"], "grounded")
        self.assertTrue(result["substantive_claim_validation"]["passed"])

    def test_intervention_metadata_requires_retrieved_value(self) -> None:
        evidence = sample_evidence()
        evidence["evidence"][0]["evidence_paths"].append(
            {
                "relationship_type": "HAS_INTERVENTION",
                "evidence_labels": ["Intervention"],
                "evidence_properties": {
                    "intervention_id": "intervention:eb4e562ee31fac7ede8a",
                    "intervention_type": "DRUG",
                    "name": "Spironolactone",
                },
            }
        )
        verified = generation.finalize_generated_answer(
            "Intervention ID: intervention:eb4e562ee31fac7ede8a\n"
            "Intervention Type: DRUG",
            evidence,
        )
        fabricated = generation.finalize_generated_answer(
            "Intervention ID: intervention:fabricated\n"
            "Intervention Type: DEVICE",
            evidence,
        )
        self.assertEqual(verified["status"], "grounded")
        self.assertEqual(fabricated["status"], "blocked_unsupported_claims")
        self.assertTrue(
            any(
                "unsupported_intervention_metadata_value" in error
                for error in fabricated["substantive_claim_validation"]["errors"]
            )
        )

    def test_question2_summary_includes_all_trials_sponsors_and_outcomes(self) -> None:
        summary = generation.build_question2_evidence_summary(
            sample_question2_evidence()
        )
        self.assertTrue(summary["ready"])
        self.assertEqual(summary["trial_count"], 5)
        self.assertEqual(summary["planned_outcome_count"], 10)
        for trial_index in range(5):
            self.assertIn(f"NCT{trial_index + 1:08d}", summary["text"])
            self.assertIn(f"Verified Sponsor {trial_index + 1}", summary["text"])
        for source_record_id in range(1000, 1010):
            self.assertIn(
                f"[source_record_id: {source_record_id}]", summary["text"]
            )

    def test_condition_metadata_requires_retrieved_identifier(self) -> None:
        evidence = sample_question2_evidence()
        verified = generation.finalize_generated_answer(
            "Condition ID: condition:heart-failure", evidence
        )
        fabricated = generation.finalize_generated_answer(
            "Condition ID: condition:fabricated", evidence
        )
        self.assertEqual(verified["status"], "grounded")
        self.assertEqual(fabricated["status"], "blocked_unsupported_claims")
        self.assertTrue(
            any(
                "unsupported_condition_metadata_value" in error
                for error in fabricated["substantive_claim_validation"]["errors"]
            )
        )

    def test_invented_sponsor_and_outcome_measure_are_blocked(self) -> None:
        explanation = (
            "NCT00206232 was sponsored by Imaginary Institute. "
            "Its primary outcome was all-cause mortality."
        )
        result = generation.finalize_generated_answer(
            explanation, sample_evidence()
        )
        errors = result["substantive_claim_validation"]["errors"]
        self.assertEqual(result["status"], "blocked_unsupported_claims")
        self.assertTrue(any("unsupported_sponsor_assertion" in e for e in errors))
        self.assertTrue(
            any("unsupported_outcome_measure_assertion" in e for e in errors)
        )

    def test_invented_termination_reason_is_blocked(self) -> None:
        result = generation.finalize_generated_answer(
            "NCT00206232 was terminated because the treatment was ineffective.",
            sample_evidence(),
        )
        errors = result["substantive_claim_validation"]["errors"]
        self.assertEqual(result["status"], "blocked_unsupported_claims")
        self.assertTrue(
            any("unsupported_clinical_claim_pattern:" in error for error in errors)
        )

    def test_explicit_abstention_is_preserved(self) -> None:
        answer = "ABSTAIN: The supplied graph evidence does not support that claim."
        generator, _ = self.generator(answer)
        result = generator.generate(sample_evidence()["question"], sample_evidence())
        self.assertEqual(result["status"], "abstained")
        self.assertEqual(result["answer"], answer)

    def test_run_question_reuses_retrieval_output_unchanged(self) -> None:
        evidence = sample_evidence()
        retriever = FakeRetriever(evidence)
        generator, _ = self.generator()
        result = generation.run_question(
            "1", retriever, generator, nct_id="NCT00206232"
        )
        self.assertEqual(retriever.calls, [("1", "NCT00206232")])
        self.assertEqual(result["kg_evidence"], evidence)
        self.assertTrue(
            result["generation"]["answer"].startswith(VALID_EXPLANATION)
        )
        self.assertGreaterEqual(result["retrieval_latency_ms"], 0)

    def test_trace_preserves_evidence_and_answer_without_credentials(self) -> None:
        evidence = sample_evidence()
        generator, _ = self.generator()
        result = generation.run_question("2", FakeRetriever(evidence), generator)
        trace = {
            "configuration": {
                "llm_provider": "openai",
                "llm_model": "gpt-6-luna",
                "api_key_configured": True,
            },
            "results": [result],
        }
        with tempfile.TemporaryDirectory() as directory:
            first = generation.save_demo_trace(trace, Path(directory))
            second = generation.save_demo_trace(trace, Path(directory))
            self.assertNotEqual(first, second)
            stored = json.loads(first.read_text(encoding="utf-8"))
        serialized = json.dumps(stored)
        self.assertEqual(stored["results"][0]["kg_evidence"], evidence)
        self.assertIn(
            generation.EVIDENCE_SECTION_HEADING,
            stored["results"][0]["generation"]["answer"],
        )
        self.assertNotIn("test-key-not-real", serialized)
        self.assertNotIn("OPENAI_API_KEY", serialized)

    def test_missing_api_key_fails_closed(self) -> None:
        with self.assertRaises(generation.AnswerGenerationError):
            generation.OpenAIAnswerGenerator(api_key="")

    def test_ollama_defaults_and_server_model_check(self) -> None:
        fake_urlopen = FakeUrlOpen()
        generator = generation.OllamaAnswerGenerator(urlopen=fake_urlopen)
        status = generator.check_server()
        self.assertTrue(status["available"])
        self.assertEqual(status["model"], "qwen2.5:1.5b")
        self.assertEqual(status["base_url"], "http://localhost:11434")
        self.assertTrue(fake_urlopen.calls[0]["request"].full_url.endswith("/api/tags"))

    def test_missing_ollama_server_fails_cleanly(self) -> None:
        generator = generation.OllamaAnswerGenerator(
            urlopen=FakeUrlOpen(error=urllib.error.URLError("connection refused"))
        )
        with self.assertRaisesRegex(
            generation.AnswerGenerationError, "Ollama is unavailable"
        ):
            generator.check_server()

    def test_invalid_ollama_response_is_rejected(self) -> None:
        generator = generation.OllamaAnswerGenerator(
            urlopen=FakeUrlOpen(generate_responses=[b"not-json"])
        )
        with self.assertRaisesRegex(
            generation.AnswerGenerationError, "invalid JSON"
        ):
            generator.generate(sample_evidence()["question"], sample_evidence())

    def test_ollama_generation_records_model_latency_and_grounding(self) -> None:
        response = {
            "model": "qwen2.5:1.5b",
            "response": VALID_EXPLANATION,
            "done": True,
            "done_reason": "stop",
            "total_duration": 1_250_000_000,
            "prompt_eval_count": 420,
            "eval_count": 65,
        }
        fake_urlopen = FakeUrlOpen(generate_responses=[response])
        generator = generation.OllamaAnswerGenerator(urlopen=fake_urlopen)
        result = generator.generate(sample_evidence()["question"], sample_evidence())
        self.assertEqual(result["provider"], "ollama")
        self.assertEqual(result["requested_model"], "qwen2.5:1.5b")
        self.assertEqual(result["response_model"], "qwen2.5:1.5b")
        self.assertEqual(result["status"], "grounded")
        self.assertEqual(result["provider_reported_total_duration_ms"], 1250.0)
        self.assertGreaterEqual(result["latency_ms"], 0)
        request_payload = json.loads(fake_urlopen.calls[0]["request"].data)
        self.assertFalse(request_payload["stream"])
        self.assertEqual(request_payload["options"]["num_ctx"], 8192)
        self.assertEqual(request_payload["options"]["temperature"], 0.0)
        self.assertNotIn("OPENAI_API_KEY", json.dumps(result))

    def test_ollama_invalid_grounding_is_blocked_without_repeated_retry(self) -> None:
        invalid = {
            "model": "qwen2.5:1.5b",
            "response": "NCT99999999 had a clinical result.",
            "done": True,
            "total_duration": 500_000_000,
        }
        fake_urlopen = FakeUrlOpen(generate_responses=[invalid])
        generator = generation.OllamaAnswerGenerator(urlopen=fake_urlopen)
        result = generator.generate(sample_evidence()["question"], sample_evidence())
        self.assertEqual(result["status"], "blocked_unsupported_claims")
        self.assertEqual(len(result["attempts"]), 1)
        self.assertFalse(result["attempts"][0]["grounding_validation"]["passed"])
        self.assertTrue(result["answer"].startswith("ABSTAIN:"))


if __name__ == "__main__":
    unittest.main()
