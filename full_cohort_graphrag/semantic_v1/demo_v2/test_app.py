"""Streamlit AppTest with saved real-source traces and mocked backend only."""
import copy
import json
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from ..identity import ROOT

APP = ROOT / 'full_cohort_graphrag/semantic_v1/demo_v2/app.py'
OLD = ROOT / 'full_cohort_graphrag/semantic_v1/live_validation/HTT-MINILM-GRAPHRAG-LIVE-v1'


def fixture(name):
    # UI rendering checks only, not a new live generation/performance claim.
    value = copy.deepcopy(json.loads((OLD / name).read_text()))
    value['client_elapsed_seconds'] = value['elapsed_seconds']
    value['model_attempts'] = sum(r['answer_trace']['generation']['attempts'] for r in value['trial_results'])
    value['selected_nct_ids'] = [r['nct_id'] for r in value['trial_results'] if r['answer_trace']['validation']['passed']]
    for row in value['trial_results']:
        row['published'] = row['nct_id'] in value['selected_nct_ids']
    value['skipped_candidates'] = []
    value['selection'] = {'examined': len(value['trial_results']), 'fixture': 'Prior real trace; UI test only'}
    return value


class AppTests(unittest.TestCase):
    def app(self):
        return AppTest.from_file(str(APP), default_timeout=15).run()

    def test_initial_page_no_backend_request(self):
        with patch('full_cohort_graphrag.semantic_v1.demo_v2.client.run_question') as backend:
            at = self.app()
        self.assertFalse(at.exception)
        backend.assert_not_called()
        self.assertEqual(at.title[0].value, 'HeartTrialTwin')
        self.assertIn('clinical effectiveness', at.warning[0].value)

    def test_exact_outcomes_workflow_and_source_expanders(self):
        with patch('full_cohort_graphrag.semantic_v1.demo_v2.client.run_question', return_value=fixture('05_outcomes.json')) as backend:
            at = self.app()
            at.selectbox[0].select('planned outcomes').run()
            at.button[0].click().run()
        self.assertFalse(at.exception)
        self.assertIn('planned outcomes', backend.call_args.args[0])
        self.assertEqual(at.metric[0].value, 'COMPLETE_LISTING')
        self.assertTrue(any('source records' in t.value for t in at.text))

    def test_semantic_discovery_renders_original_rank_table(self):
        value = fixture('02_discovery.json')
        with patch('full_cohort_graphrag.semantic_v1.demo_v2.client.run_question', return_value=value) as backend:
            at = self.app()
            at.radio[0].set_value('Semantic discovery').run()
            at.button[0].click().run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.dataframe), 1)
        self.assertEqual(backend.call_args.kwargs['scan_limit'], 5)
        self.assertTrue(backend.call_args.args[0].startswith('Find trials with'))

    def test_safe_timeout_rendered_as_abstention(self):
        value = dict(status='ABSTAIN', answer='ABSTAIN: Local Ollama exceeded the 60-second request bound.',
                     errors=['OLLAMA_CONNECTION_OR_TIMEOUT_FAILURE'], client_elapsed_seconds=60,
                     question='What title is registered for NCT00206232?', model_attempts=1)
        with patch('full_cohort_graphrag.semantic_v1.demo_v2.client.run_question', return_value=value):
            at = self.app()
            at.button[0].click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.metric[0].value, 'ABSTAIN')
        self.assertIn('60-second', at.text[0].value)


if __name__ == '__main__':
    unittest.main()
