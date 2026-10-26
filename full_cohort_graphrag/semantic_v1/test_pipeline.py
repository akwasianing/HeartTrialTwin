"""Real pinned CSV fixtures, mocked Neo4j/Ollama/worker; no live service calls."""
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from . import pipeline as p
from .bridge import RankingWorker, validate_ranking
from .identity import ROOT, VERSION, FEATURE_SHA, PROTOCOL_SHA, MODEL, REVISION, SemanticError, DATASET, GRAPH, SNAPSHOT
from full_cohort_graphrag.src import retrieve as api
from full_cohort_graphrag.src import generate_answer as g

sys.path.insert(0,str(ROOT/'full_cohort_graphrag/tests'))
from test_retrieve import Fixture, FakeDriver


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = Fixture()

    def setUp(self):
        for name in ('neo4j.GraphDatabase.driver','urllib.request.urlopen','subprocess.run'):
            guard=patch(name,side_effect=AssertionError('Live services prohibited'))
            guard.start()
            self.addCleanup(guard.stop)
        self.driver=FakeDriver(self.fixture)
        self.retriever=api.FullCohortRetriever(api.Config('bolt://127.0.0.1:7687','offline','offline'),
            driver=self.driver,contract=self.fixture.contract)
        self.ranker=Mock()
        self.ranker.rank.side_effect=lambda text,k:self.ranking(['NCT00206232','NCT00391846'][:k])

    def ranking(self,ids):
        members=sorted(self.fixture.contract.membership)
        return {'status':'OK','ranked_trials':[{'rank':i+1,'nct_id':n,'similarity':.8-i*.1,
                'candidate_index':members.index(n)} for i,n in enumerate(ids)],
            'provenance':{'version':VERSION,'model':MODEL,'revision':REVISION,'feature_manifest_sha256':FEATURE_SHA,
                'dataset_version':DATASET,'graph_version':GRAPH,'snapshot_date':SNAPSHOT,
                'protocol_sha256':PROTOCOL_SHA,'dimensions':384,'candidate_count':2824,'association_labels_used':False}}

    def client(self,opener):
        return p.SemanticGraphRAG(self.retriever,ranker=self.ranker,
                                 generator=g.OllamaAnswerGenerator(urlopen=opener,contract=self.fixture.contract))

    def test_complete_exact_listing_never_ranks_or_generates(self):
        opener=Mock(side_effect=AssertionError('No generation for complete listing'))
        result=self.client(opener).run('What planned outcomes were registered for NCT00206232?')
        self.assertEqual(result['status'],'COMPLETE_LISTING')
        inner=result['trial_results'][0]['answer_trace']
        self.assertEqual(len(inner['listed_outcomes']),7)
        self.assertEqual(len(set(inner['validation']['listed_evidence_ids'])),7)
        self.assertEqual(inner['generation']['attempts'],0)
        self.ranker.rank.assert_not_called()
        opener.assert_not_called()
        self.assertIn(api.PLANNED_SAFEGUARD,result['answer'])
        self.assertIn(api.SNAPSHOT_SAFEGUARD,result['answer'])

    def test_supported_factual_question_uses_original_validator(self):
        def reply(request,**kwargs):
            prompt=json.loads(json.loads(request.data)['prompt'])
            key=next(iter(prompt['fact_catalog']))
            return io.BytesIO(json.dumps({'model':g.MODEL,'response':json.dumps({'fact_ids':[key]}),
                'done':True,'done_reason':'stop','prompt_eval_count':20,'eval_count':10}).encode())
        opener=Mock(side_effect=reply)
        result=self.client(opener).run('What intervention is registered for clinical trial NCT00206232?')
        self.assertEqual(result['status'],'GROUNDED')
        self.assertEqual(result['answer_origin'],'OLLAMA_CATALOG_SELECTION')
        opener.assert_called_once()
        self.ranker.rank.assert_not_called()
        inner=result['trial_results'][0]['answer_trace']
        self.assertTrue(all(v['field']=='intervention' and v['nct_id']=='NCT00206232'
                            for v in inner['validation']['accepted_facts']))

    def test_ranked_ids_keep_exact_trial_citations_and_outcomes(self):
        result=self.client(Mock(side_effect=AssertionError('No model for semantic evidence listings'))).run(
            'Find trials with registered planned outcomes about quality of life.',top_k=2)
        self.assertEqual(result['status'],'GROUNDED_CANDIDATE_EVIDENCE')
        self.ranker.rank.assert_called_once_with('quality of life',2)
        self.assertFalse(result['validation']['semantic_association_confirmed'])
        self.assertIn('not verified query-to-trial associations',result['answer'])
        for row in result['trial_results']:
            self.assertEqual(row['prepared_evidence']['scope']['selected_nct_ids'],[row['nct_id']])
            self.assertTrue(row['evidence_question_is_derived'])
            trace=row['answer_trace']
            refs={v['citation_id']:v for v in trace['source_references']}
            self.assertEqual(set(trace['validation']['listed_evidence_ids']),set(trace['validation']['expected_evidence_ids']))
            for outcome in trace['listed_outcomes']:
                for cid in outcome['citation_ids']:
                    self.assertEqual(refs[cid]['nct_id'],row['nct_id'])
                    self.assertEqual(refs[cid]['evidence_id'],outcome['evidence_id'])

    def test_unsupported_clinical_claims_never_retrieve(self):
        for question in ('Did spironolactone improve survival in NCT00206232?',
                         'Why was NCT00604006 terminated?', 'What treatment is best for heart failure?'):
            result=self.client(Mock()).run(question)
            self.assertEqual(result['status'],'ABSTAIN')
        self.assertEqual(self.driver.calls,[])
        self.ranker.rank.assert_not_called()

    def test_invalid_and_multiple_ids_never_fall_back(self):
        for question in ('What phase is registered for NCT0020623?',
                         'What phase is registered for NCTabc?',
                         'What phases are registered for NCT00206232 and NCT00391846?'):
            self.assertEqual(self.client(Mock()).run(question)['status'],'ABSTAIN')
        self.assertFalse(self.driver.calls)
        self.ranker.rank.assert_not_called()

    def test_unknown_trial_not_semantically_replaced(self):
        result=self.client(Mock()).run('What planned outcomes were registered for NCT99999999?')
        self.assertEqual(result['status'],'ABSTAIN')
        self.assertEqual(result['trial_results'][0]['prepared_evidence']['retrieval_status'],'NOT_FOUND')
        self.assertIn('NOT_FOUND',result['errors'][0])
        self.ranker.rank.assert_not_called()

    def test_missing_sources_block_entire_answer(self):
        for nct in ('NCT00057356','NCT00000475'):
            result=self.client(Mock()).run(f'What planned outcomes were registered for {nct}?')
            self.assertEqual(result['status'],'ABSTAIN')
            self.assertIn('MISSING_SOURCE_RECORDS',result['errors'][0])
            self.assertEqual(result['trial_results'][0]['answer_trace']['listed_outcomes'],[])

    def test_partial_candidate_never_published_as_complete(self):
        self.ranker.rank.side_effect=None
        self.ranker.rank.return_value=self.ranking(['NCT00000475'])
        result=self.client(Mock()).run('Find trials with registered planned outcomes about quality of life.',top_k=1)
        self.assertEqual(result['status'],'ABSTAIN')
        self.assertNotIn('complete registered planned-outcome listing',result['answer'])

    def test_paginated_evidence_abstains_without_fetching_more_pages(self):
        original=self.retriever.trial_profile
        def limited(nct,**kwargs):
            return original(nct,limit=20,offset=0)
        with patch.object(self.retriever,'trial_profile',side_effect=limited):
            result=self.client(Mock()).run('What planned outcomes were registered for NCT05256303?')
        self.assertEqual(result['status'],'ABSTAIN')
        self.assertIn('PAGINATION_LIMITED',result['errors'][0])
        self.assertEqual(result['trial_results'][0]['prepared_evidence']['evidence_record_count'],20)

    def test_invalid_top_k_fails_before_services(self):
        self.assertEqual(self.client(Mock()).run('What phase is registered for NCT00206232?',top_k=6)['status'],'ABSTAIN')
        self.assertFalse(self.driver.calls)
        self.ranker.rank.assert_not_called()

    def test_ranker_integrity_failure_stops_before_database(self):
        self.ranker.rank.side_effect=SemanticError('Feature manifest checksum mismatch')
        result=self.client(Mock()).run('Find trials with registered planned outcomes about survival.',top_k=1)
        self.assertEqual(result['status'],'ABSTAIN')
        self.assertIn('checksum',result['errors'][0])
        self.assertFalse(self.driver.calls)

    def test_wrong_candidate_mapping_and_provenance_rejected(self):
        original=self.ranking(['NCT00206232'])
        for mutate in (lambda d:d['ranked_trials'][0].update(candidate_index=0),
                       lambda d:d['ranked_trials'][0].update(nct_id='NCT99999999'),
                       lambda d:d['provenance'].update(revision='unknown'),
                       lambda d:d['ranked_trials'][0].update(similarity=float('nan'))):
            value=copy.deepcopy(original)
            mutate(value)
            with self.assertRaises(SemanticError):
                validate_ranking(value,1,self.fixture.contract.membership)

    def test_misattributed_or_tampered_evidence_abstains(self):
        original=self.retriever.trial_profile
        def bad(nct,**kwargs):
            raw=original(nct,**kwargs)
            raw['evidence'][0]['relationship']['start_id']='NCT00391846'
            return raw
        with patch.object(self.retriever,'trial_profile',side_effect=bad):
            result=self.client(Mock()).run('What planned outcomes were registered for NCT00206232?')
        self.assertEqual(result['status'],'ABSTAIN')
        self.assertFalse(result['validation']['source_grounding_passed'])

    def test_invalid_citation_selection_stays_blocked(self):
        opener=Mock(return_value=io.BytesIO(json.dumps({'model':g.MODEL,'response':'{"fact_ids":["F99999"]}',
            'done':True,'done_reason':'stop'}).encode()))
        result=self.client(opener).run('What phase is registered for NCT00206232?')
        self.assertEqual(result['status'],'ABSTAIN')
        self.assertIn('UNKNOWN_FACT_ID',result['errors'][0])

    def test_generation_error_does_not_leak_credentials(self):
        opener=Mock(side_effect=RuntimeError('private-password secret-host'))
        result=self.client(opener).run('What phase is registered for NCT00206232?')
        self.assertEqual(result['status'],'ABSTAIN')
        self.assertNotIn('private-password',json.dumps(result))

    def test_trace_save_is_exclusive(self):
        result=self.client(Mock()).run('What planned outcomes were registered for NCT00206232?')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace.json'
            p.save_trace(result,path)
            self.assertEqual(json.loads(path.read_text()),result)
            with self.assertRaises(FileExistsError):
                p.save_trace(result,path)

    def test_worker_timeout_invalid_json_and_secret_environment(self):
        runner=Mock(side_effect=subprocess.TimeoutExpired('worker',180))
        with self.assertRaises(SemanticError):
            RankingWorker(runner=runner).rank('quality of life',1)
        runner=Mock(return_value=SimpleNamespace(returncode=0,stdout='not JSON'))
        with self.assertRaises(SemanticError):
            RankingWorker(runner=runner).rank('quality of life',1)
        runner=Mock(return_value=SimpleNamespace(returncode=0,stdout=json.dumps(self.ranking(['NCT00206232']))))
        with patch.dict('os.environ',{'FULL_GRAPHRAG_NEO4J_PASSWORD':'never-send'}):
            result=RankingWorker(runner=runner).rank('quality of life',1)
        self.assertEqual(result['status'],'OK')
        self.assertNotIn('FULL_GRAPHRAG_NEO4J_PASSWORD',runner.call_args.kwargs['env'])
        self.assertEqual(runner.call_args.kwargs['timeout'],180)


if __name__ == '__main__':
    unittest.main()
