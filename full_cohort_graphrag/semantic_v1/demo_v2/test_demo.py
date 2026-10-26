"""Offline tests using pinned CSV fixtures; no Neo4j, encoder or Ollama calls."""
import copy
import io
import json
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from full_cohort_graphrag.semantic_v1.identity import ROOT, VERSION, MODEL, REVISION, FEATURE_SHA, PROTOCOL_SHA
from full_cohort_graphrag.src import retrieve as api, generate_answer as g
from full_cohort_graphrag.src.prepare_evidence import prepare_evidence
from .facts import factual_answer
from .engine import Demonstration, BoundedOllama
from .client import run_question
from .worker import execute

sys.path.insert(0, str(ROOT / 'full_cohort_graphrag/tests'))
from test_retrieve import Fixture, FakeDriver


class DemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = Fixture()

    def setUp(self):
        for name in ('neo4j.GraphDatabase.driver', 'urllib.request.urlopen', 'subprocess.run'):
            guard = patch(name, side_effect=AssertionError('Live calls forbidden'))
            guard.start()
            self.addCleanup(guard.stop)
        self.driver = FakeDriver(self.fixture)
        self.retriever = api.FullCohortRetriever(api.Config('bolt://127.0.0.1:7687', 'offline', 'offline'),
                                               driver=self.driver, contract=self.fixture.contract)
        self.ranker = Mock()
        self.model = Mock(side_effect=AssertionError('No default generation'))
        self.engine = Demonstration(self.retriever, ranker=self.ranker, generator=self.model)

    def ranking(self, ids):
        members = sorted(self.fixture.contract.membership)
        return {'status': 'OK', 'ranked_trials': [dict(rank=i+1, nct_id=nct, similarity=.9-i*.1,
                    candidate_index=members.index(nct)) for i, nct in enumerate(ids)],
                'provenance': dict(version=VERSION, model=MODEL, revision=REVISION, feature_manifest_sha256=FEATURE_SHA,
                    protocol_sha256=PROTOCOL_SHA, dataset_version=api.DATASET, graph_version=api.GRAPH,
                    snapshot_date=api.SNAPSHOT, dimensions=384, candidate_count=2824, association_labels_used=False)}

    def prepared(self, nct='NCT00206232', limit=200):
        self.retriever.verify_connection()
        return prepare_evidence(self.retriever.trial_profile(nct, limit=limit), contract=self.fixture.contract)

    def test_title_sponsor_intervention_are_deterministic_complete_facts(self):
        for question, value in (
            ('What title is registered for NCT00206232?', 'Novel Treatment for Diastolic Heart Failure in Women'),
            ('Who is the lead sponsor of NCT00206232?', 'Baylor College of Medicine'),
            ('What intervention is registered for NCT00206232?', 'Spironolactone')):
            result = self.engine.run(question)
            self.assertEqual(result['status'], 'GROUNDED')
            self.assertIn(value, result['answer'])
            self.assertEqual(result['model_attempts'], 0)
            self.assertTrue(result['validation']['source_grounding_passed'])
        self.ranker.rank.assert_not_called()
        self.model.generate.assert_not_called()

    def test_citations_match_exact_trial_evidence_and_snapshot(self):
        result = self.engine.run('What intervention is registered for NCT00206232?')
        inner = result['trial_results'][0]['answer_trace']
        refs = {r['citation_id']: r for r in inner['source_references']}
        for fact in inner['validation']['accepted_facts']:
            for cid in fact['citation_ids']:
                self.assertEqual(refs[cid]['evidence_id'], fact['evidence_id'])
                self.assertEqual(refs[cid]['nct_id'], 'NCT00206232')
                self.assertEqual(refs[cid]['snapshot_date'], api.SNAPSHOT)

    def test_seven_outcomes_all_present_once_with_types_and_timeframes(self):
        result = self.engine.run('What planned outcomes were registered for NCT00206232?', answer_mode='ollama')
        self.assertEqual(result['status'], 'COMPLETE_LISTING')
        inner = result['trial_results'][0]['answer_trace']
        expected = result['trial_results'][0]['prepared_evidence']['trials'][0]['categories']['planned_outcomes']
        self.assertEqual(len(inner['listed_outcomes']), 7)
        self.assertEqual({r['evidence_id'] for r in inner['listed_outcomes']}, {r['evidence_id'] for r in expected})
        for actual in inner['listed_outcomes']:
            original = next(r for r in expected if r['evidence_id'] == actual['evidence_id'])
            self.assertEqual(actual['properties'], original['properties'])
            self.assertEqual(actual['citation_ids'], original['citation_ids'])
        self.assertEqual(result['model_attempts'], 0)

    def test_conditions_preserve_submitted_and_browse_distinction(self):
        result = self.engine.run('What conditions are registered for NCT00206232?')
        facts = result['trial_results'][0]['answer_trace']['validation']['accepted_facts']
        self.assertEqual({f['field'] for f in facts}, {'submitted condition', 'browse condition'})

    def test_stable_semantic_ranking_skips_missing_outcomes_without_renumbering(self):
        ids = ['NCT00939146', 'NCT00012870', 'NCT00206232']
        ranking = self.ranking(ids)
        self.ranker.rank.return_value = copy.deepcopy(ranking)
        result = self.engine.run('Find trials with registered planned outcomes about quality of life.', scan_limit=3)
        self.assertEqual(result['status'], 'GROUNDED_CANDIDATE_EVIDENCE')
        self.assertEqual(result['ranking'], ranking)
        self.assertEqual(result['selected_nct_ids'], [ids[0], ids[2]])
        self.assertEqual(result['skipped_candidates'][0]['original_rank'], 2)
        self.assertIn('MISSING_SOURCE_RECORDS', result['skipped_candidates'][0]['reasons'])
        self.assertEqual(result['selection']['examined'], 3)
        self.assertFalse(result['validation']['semantic_association_confirmed'])
        self.assertIn('not a search of every trial', result['answer'])

    def test_budget_exhaustion_publishes_only_complete_selected_trial_with_partial_label(self):
        self.ranker.rank.return_value = self.ranking(['NCT00939146', 'NCT00012870'])
        result = self.engine.run('Find trials with registered planned outcomes about quality of life.', scan_limit=2)
        self.assertEqual(result['status'], 'PARTIAL_CANDIDATE_EVIDENCE')
        self.assertEqual(result['selected_nct_ids'], ['NCT00939146'])
        self.assertFalse(result['selection']['requested_candidate_count_met'])
        self.assertFalse(result['trial_results'][1]['published'])

    def test_no_eligible_candidate_abstains_not_absence(self):
        self.ranker.rank.return_value = self.ranking(['NCT00012870'])
        result = self.engine.run('Find trials with registered planned outcomes about quality of life.',
                                 candidate_count=1, scan_limit=1)
        self.assertEqual(result['status'], 'ABSTAIN')
        self.assertIn('absence is not established', result['answer'])

    def test_candidate_mapping_or_checksum_failure_stops(self):
        result = self.ranking(['NCT00206232'])
        result['provenance']['feature_manifest_sha256'] = 'tampered'
        self.ranker.rank.return_value = result
        trace = self.engine.run('Find trials with registered planned outcomes about quality of life.',
                                candidate_count=1, scan_limit=1)
        self.assertEqual(trace['status'], 'ABSTAIN')
        self.assertFalse(self.driver.calls)

    def test_effectiveness_unknown_intent_and_invalid_id_never_reach_services(self):
        for q in ('Did spironolactone improve survival in NCT00206232?',
                  'Why was NCT00604006 terminated?', 'What title is registered for NCT0020623?',
                  'Explain all clinical results.'):
            self.assertEqual(self.engine.run(q)['status'], 'ABSTAIN')
        self.assertFalse(self.driver.calls)
        self.ranker.rank.assert_not_called()

    def test_unknown_nct_not_replaced_by_semantic_candidate(self):
        result = self.engine.run('What planned outcomes were registered for NCT99999999?')
        self.assertEqual(result['status'], 'ABSTAIN')
        self.assertIn('NOT_FOUND', result['errors'][0])
        self.ranker.rank.assert_not_called()

    def test_pagination_limited_evidence_not_a_complete_listing(self):
        result = factual_answer('What planned outcomes were registered for NCT05256303?',
                                self.prepared('NCT05256303', 20), contract=self.fixture.contract)
        self.assertEqual(result['status'], 'ABSTAIN')
        self.assertIn('PAGINATION_LIMITED', result['validation']['errors'])

    def test_missing_unrequested_category_retains_strict_policy(self):
        result = self.engine.run('What title is registered for NCT00012870?')
        self.assertEqual(result['status'], 'ABSTAIN')
        self.assertIn('MISSING_SOURCE_RECORDS', result['errors'][0])

    def test_tampered_citations_fail_closed(self):
        value = self.prepared()
        value['citations'][0]['nct_id'] = 'NCT00391846'
        with self.assertRaises(g.GenerationInputError):
            factual_answer('What title is registered for NCT00206232?', value, contract=self.fixture.contract)

    def test_output_limit_no_partial_facts(self):
        result = factual_answer('What intervention is registered for NCT00206232?', self.prepared(),
                                contract=self.fixture.contract, max_answer_bytes=1)
        self.assertEqual(result['status'], 'ABSTAIN')
        self.assertEqual(result['validation']['accepted_facts'], [])

    def test_neo4j_failure_hides_private_details(self):
        with patch.object(self.retriever, 'verify_connection', side_effect=RuntimeError('private-password')):
            result = self.engine.run('What title is registered for NCT00206232?')
        self.assertEqual(result['status'], 'ABSTAIN')
        self.assertNotIn('private-password', json.dumps(result))

    def test_ollama_request_timeout_one_attempt_no_automatic_deterministic_fallback(self):
        opener = Mock(side_effect=TimeoutError('secret-host'))
        result = BoundedOllama(self.fixture.contract, opener=opener).generate(
            'What title is registered for NCT00206232?', self.prepared())
        self.assertEqual(result['status'], 'ABSTAIN')
        self.assertEqual(result['generation']['attempts'], 1)
        self.assertEqual(opener.call_args.kwargs['timeout'], 60)
        self.assertIn('60-second', result['answer'])
        self.assertNotIn('secret-host', json.dumps(result))

    def test_optional_ollama_preserves_original_citation_validator(self):
        def reply(request, **kwargs):
            prompt = json.loads(json.loads(request.data)['prompt'])
            key = next(iter(prompt['fact_catalog']))
            return io.BytesIO(json.dumps({'model': g.MODEL, 'response': json.dumps({'fact_ids': [key]}),
                                         'done': True, 'done_reason': 'stop'}).encode())
        opener = Mock(side_effect=reply)
        model = BoundedOllama(self.fixture.contract, opener=opener)
        result = Demonstration(self.retriever, ranker=self.ranker, generator=model).run(
            'What intervention is registered for NCT00206232?', answer_mode='ollama')
        self.assertEqual(result['status'], 'GROUNDED')
        self.assertEqual(result['model_attempts'], 1)
        self.assertIn('Spironolactone', result['answer'])

    def test_explicit_deterministic_request_after_model_timeout_not_silent_fallback(self):
        opener = Mock(side_effect=TimeoutError())
        engine = Demonstration(self.retriever, generator=BoundedOllama(self.fixture.contract, opener=opener))
        question = 'What intervention is registered for NCT00206232?'
        failed = engine.run(question, answer_mode='ollama')
        self.assertEqual(failed['status'], 'ABSTAIN')
        self.assertIn('60-second', failed['answer'])
        self.assertEqual(failed['model_attempts'], 1)
        chosen = engine.run(question, answer_mode='deterministic')
        self.assertEqual(chosen['status'], 'GROUNDED')
        self.assertEqual(chosen['model_attempts'], 0)
        self.assertIn('Spironolactone', chosen['answer'])
        opener.assert_called_once()

    def test_scan_configuration_bounded_before_services(self):
        for options in ({'scan_limit': 11}, {'candidate_count': 4}, {'scan_limit': 1, 'candidate_count': 2},
                        {'answer_mode': 'unknown'}):
            self.assertEqual(self.engine.run('What title is registered for NCT00206232?', **options)['status'], 'ABSTAIN')
        self.assertFalse(self.driver.calls)

    def test_backend_uses_fixed_python_no_shell_and_explicit_deadline(self):
        runner = Mock(return_value=SimpleNamespace(returncode=0, stdout='{"status":"ABSTAIN","answer":"safe"}'))
        result = run_question('question', runner=runner)
        self.assertEqual(result['answer'], 'safe')
        args, kwargs = runner.call_args
        self.assertIn('.venv-graphrag/bin/python', args[0][0])
        self.assertEqual(kwargs['timeout'], 240)
        self.assertNotIn('shell', kwargs)

    def test_backend_failure_and_timeout_safe(self):
        for failure in (subprocess.TimeoutExpired('command', 240), RuntimeError('password')):
            result = run_question('question', runner=Mock(side_effect=failure))
            self.assertEqual(result['status'], 'ABSTAIN')
            self.assertNotIn('password', json.dumps(result))

    def test_worker_rejects_extra_fields_and_unsupported_requests_before_driver(self):
        with self.assertRaises(ValueError):
            execute({'question': 'hello', 'cypher': 'MATCH'})
        with self.assertRaises(ValueError):
            execute(dict(question='Did spironolactone improve survival in NCT00206232?',
                         candidate_count=2, scan_limit=5, answer_mode='deterministic'))


if __name__ == '__main__':
    unittest.main()
