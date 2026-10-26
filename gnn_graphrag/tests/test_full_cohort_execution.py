"""Offline tests for separately authorized features/training, no network calls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from gnn_graphrag.src import full_cohort_access as a
from gnn_graphrag.src import full_cohort_features as f
from gnn_graphrag.src import association_training_data_v2 as original
from gnn_graphrag.src import full_cohort_ranking as ranking
import torch


class FakeEncoder:
    provenance = {'test_only':True}
    def audit(self,texts):
        return {'rows':len(texts),'maximum_tokens_including_specials':10,'truncated_rows':0}
    def encode(self,texts):
        result = np.zeros((len(texts),384),dtype=np.float32)
        result[:,0] = 1
        return result


class ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes,cls.queries,cls.edges,cls.candidates = a.feature_inputs()

    def test_external_authorization_and_fixed_configuration(self):
        cfg = a.authorize('training')
        self.assertEqual(cfg['model']['output_dimension'],64)
        with self.assertRaises(a.IntegrityError):
            a.authorize('arbitrary_operation')

    def test_changed_configuration_fails_closed(self):
        with patch.object(a,'CONFIG_SHA','0'*64):
            with self.assertRaises(a.IntegrityError):
                a.authorize('training')

    def test_default_original_loader_remains_blocked(self):
        with self.assertRaisesRegex(a.protocol.ProtocolError,'training is blocked'):
            original.load_training_data()

    def test_context_excludes_outcome_nodes_and_target_edges(self):
        self.assertEqual(len(self.nodes),9036)
        self.assertEqual(len(self.edges),61218)
        self.assertEqual({r['node_label'] for r in self.nodes},set(a.LABELS[:4]))
        self.assertTrue(all(r['relationship_type'] in a.RELATIONS for r in self.edges))

    def test_feature_reader_never_opens_truth_or_global_catalog(self):
        opened = []
        original_open = Path.open
        def safe(path,*args,**kwargs):
            opened.append(str(path))
            self.assertNotIn('/truth/',str(path))
            self.assertNotIn('query_catalog',str(path))
            self.assertNotIn('positive_associations',str(path))
            self.assertNotIn('/evaluation/',str(path))
            return original_open(path,*args,**kwargs)
        with patch.object(Path,'open',safe):
            _,queries,_,_ = a.feature_inputs()
        self.assertTrue(opened)
        self.assertTrue(all(set(q) == {'query_id','query_text'} for q in queries))

    def test_training_reader_never_opens_heldout_labels(self):
        original_open = Path.open
        def safe(path,*args,**kwargs):
            self.assertNotIn('/truth/',str(path))
            self.assertNotIn('/evaluation/',str(path))
            self.assertNotIn('query_catalog',str(path))
            return original_open(path,*args,**kwargs)
        with patch.object(Path,'open',safe):
            inputs = a.training_inputs()
        allowed = set(inputs['candidate_ids'])
        self.assertEqual(len(allowed),1976)
        self.assertTrue(all(set(q['positive_trial_ids']+q['ambiguous_trial_ids']) <= allowed for q in inputs['queries']))
        self.assertFalse(inputs['frozen_training_permitted'])

    def test_identifier_taint_rejected(self):
        nodes = copy.deepcopy(self.nodes)
        nodes[0]['feature_text'] += ' NCT00206232'
        with self.assertRaises(a.IntegrityError):
            a.check_context(nodes,self.edges)

    def test_target_edge_rejected(self):
        edges = copy.deepcopy(self.edges)
        edges[0]['relationship_type'] = 'HAS_PLANNED_OUTCOME'
        with self.assertRaises(a.IntegrityError):
            a.check_context(self.nodes,edges)

    def test_order_change_rejected(self):
        nodes = list(self.nodes)
        nodes[0],nodes[1] = nodes[1],nodes[0]
        with self.assertRaises(a.IntegrityError):
            a.check_context(nodes,self.edges)

    def test_exact_six_slot_encoding(self):
        nodes = [{'node_label':label} for label in a.LABELS[:4]]
        result = f.combine_types(FakeEncoder().encode(['x']*4),nodes)
        self.assertEqual(result.shape,(4,390))
        np.testing.assert_array_equal(result[:,384:388],np.eye(4))
        self.assertFalse(result[:,388:].any())
        np.testing.assert_allclose(np.linalg.norm(result,axis=1),np.sqrt(2),rtol=1e-6)

    def test_repeat_and_nonfinite_validation(self):
        values,audit = f.encode_repeat(FakeEncoder(),['registered measure'])
        self.assertEqual(audit['repeat_max_absolute_difference'],0)
        values[0,0] = np.nan
        with self.assertRaises(a.IntegrityError):
            f.check_semantic(values,1)

    def test_context_recovery_reuses_verified_values_with_one_fresh_pass(self):
        nodes = [{'node_label':'Trial','feature_text':'approved trial title'},
                 {'node_label':'Sponsor','feature_text':'approved sponsor'}]
        encoder = FakeEncoder()
        previous = f.combine_types(encoder.encode(['a','b']),nodes)
        with patch.object(encoder,'encode',wraps=encoder.encode) as encode:
            recovered,audit = f.verify_recovered_context(encoder,nodes,previous)
        self.assertEqual(encode.call_count,1)
        np.testing.assert_array_equal(previous,recovered)
        self.assertEqual(audit['repeat_max_absolute_difference'],0)
        self.assertIsNone(audit['first_encoding_seconds'])

    def test_context_recovery_does_not_repair_changed_values(self):
        nodes = [{'node_label':'Trial','feature_text':'approved trial title'}]
        previous = f.combine_types(FakeEncoder().encode(['a']),nodes)
        previous[0,384] = 0
        previous[0,385] = 1
        with self.assertRaisesRegex(a.IntegrityError,'not byte-identical'):
            f.verify_recovered_context(FakeEncoder(),nodes,previous)

    def test_bound_recovery_record_is_reused_without_an_encoder_call(self):
        encoder = FakeEncoder()
        cfg = a.authorize('context_train_features')['features']
        encoder.provenance = {'revision':cfg['revision'],'snapshot_sha256':cfg['snapshot_sha256']}
        source = a.FEATURES.parent/'.HTT-GNN-ASSOC-FEATURES-v1.incomplete-jbr_hyxl/context_features.npy'
        with patch.object(encoder,'encode',side_effect=AssertionError('Completed context must not be encoded again')):
            values,audit = f.reuse_recovery_verification(encoder,self.nodes,source,a.RUN/'context_recovery_verification.json')
        self.assertEqual(values.shape,(9036,390))
        self.assertTrue(audit['verification_reused_not_rerun'])
        self.assertEqual(audit['repeat_max_absolute_difference'],0)

    def test_unbound_recovery_record_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = Path(tmp)/'unverified.json'
            a.save_json(record,{'maximum_absolute_difference':0})
            with self.assertRaisesRegex(a.IntegrityError,'Unverified recovery record'):
                f.reuse_recovery_verification(FakeEncoder(),self.nodes,Path(tmp)/'source.npy',record)

    def test_test_queries_locked_before_selection(self):
        with patch.object(a,'selected_checkpoint',side_effect=a.IntegrityError('test locked')):
            with self.assertRaisesRegex(a.IntegrityError,'test locked'):
                a.evaluation_inputs('test')

    def test_atomic_bundle_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)/'bundle'
            with a.atomic_directory(destination) as stage:
                a.save_json(stage/'payload.json',{'value':1})
                a.bundle_manifest(stage,{'test':True})
            self.assertTrue(a.verify_bundle(destination)['test'])
            with self.assertRaises(a.IntegrityError):
                with a.atomic_directory(destination):
                    self.fail('Existing destination admitted')

    def test_failed_staging_is_not_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp)/'bundle'
            with self.assertRaises(RuntimeError):
                with a.atomic_directory(destination):
                    raise RuntimeError('simulated interruption')
            self.assertFalse(destination.exists())

    def test_input_checksum_tampering_is_rejected(self):
        m = a.manifest()
        m['files_sha256']['training/context_nodes.jsonl'] = '0'*64
        with self.assertRaises(a.IntegrityError):
            a.bound_bytes('training/context_nodes.jsonl',m)

    def test_negative_sampling_excludes_positives_ambiguities_and_families(self):
        ids = tuple('NCT'+str(i).zfill(8) for i in range(100))
        inputs = {'candidate_ids':ids,'families':[{'nct_id':n,'family_id':'shared' if i in (1,4) else str(i)} for i,n in enumerate(ids)],
                  'queries':[{'positive_trial_ids':[ids[1],ids[2]],'ambiguous_trial_ids':[ids[3]]}]}
        positives,pools = ranking.prepare_labels(inputs)
        self.assertEqual(positives.tolist(),[[1,2]])
        self.assertFalse(set(pools[0]) & {1,2,3,4})
        negatives = ranking.sample_negatives(pools,123)
        self.assertEqual(negatives.shape,(1,64))
        self.assertEqual(len(set(negatives[0])),64)
        np.testing.assert_array_equal(negatives,ranking.sample_negatives(pools,123))

    def test_multi_positive_probability_mass_and_gradients(self):
        scores = torch.zeros((1,66),requires_grad=True)
        loss = ranking.multi_positive_loss(scores,torch.tensor([[0,1]]),torch.arange(2,66).view(1,-1),0.1)
        self.assertAlmostEqual(float(loss),float(np.log(33)),places=5)
        loss.backward()
        self.assertTrue((scores.grad[0,:2] < 0).all())
        self.assertTrue((scores.grad[0,2:] > 0).all())

    def test_missing_positive_loss_rejected(self):
        with self.assertRaises(a.IntegrityError):
            ranking.multi_positive_loss(torch.zeros(1,4),torch.tensor([[-1]]),torch.tensor([[2,3]]),0.1)

    def test_recall_differs_from_hit_for_multiple_owners(self):
        metrics = ranking.rank_metrics([1,10])
        self.assertEqual(metrics['Hit@1'],1)
        self.assertEqual(metrics['Recall@1'],0.5)
        self.assertEqual(metrics['Recall@10'],1)
        self.assertEqual(metrics['MRR'],1)

    def test_tie_break_is_candidate_order(self):
        ids = ['NCT'+str(i).zfill(8) for i in range(2824)]
        truth = [{'query_id':'synthetic','owner_trial_ids':[ids[5]],'source_associations':[{'evidence_id':'synthetic-source'}]}]
        records,summary = ranking.evaluate_vectors(np.zeros((1,2)),np.zeros((2824,2)),truth,ids,'synthetic')
        self.assertEqual(records[0]['positive_ranks'],[6])
        self.assertEqual(records[0]['top10'][0]['nct_id'],ids[0])
        self.assertEqual(summary['candidate_count'],2824)
        self.assertEqual(summary['informative_query_coverage'],0)
        self.assertEqual(summary['coverage'],1)
        self.assertEqual(records[0]['source_evidence_ids'],['synthetic-source'])
        self.assertAlmostEqual(ranking.validation_mrr(np.zeros((1,2)),np.zeros((2824,2)),truth,ids),1/6)

    def test_graphsage_and_query_projection_receive_gradients(self):
        f.configure()
        model = ranking.AssociationRanker()
        context = torch.randn(4,390)
        edges = torch.tensor([[0,1,2,3],[1,0,3,2]],dtype=torch.long)
        query = torch.randn(2,384)
        scores = model.queries(query) @ model.trials(context,edges).T
        loss = ranking.multi_positive_loss(scores,torch.tensor([[0],[1]]),torch.tensor([[2,3],[2,3]]),0.1)
        loss.backward()
        self.assertIsNotNone(model.query.weight.grad)
        self.assertIsNotNone(model.graph.layer1.linear.weight.grad)
        self.assertTrue(torch.isfinite(loss))

    def test_seeded_ranker_initialization_repeats(self):
        f.configure()
        first = ranking.AssociationRanker().state_dict()
        f.configure()
        second = ranking.AssociationRanker().state_dict()
        self.assertTrue(all(torch.equal(first[k],second[k]) for k in first))

    def test_family_uncertainty_is_paired_and_deterministic(self):
        records = [{'positive_trial_ids':['a'],'metrics':ranking.rank_metrics([2])},
                   {'positive_trial_ids':['b'],'metrics':ranking.rank_metrics([5])}]
        split_rows = [{'nct_id':'a','family_id':'f1'},{'nct_id':'b','family_id':'f2'}]
        summary,first = ranking.macro_and_uncertainty(records,split_rows)
        _,second = ranking.macro_and_uncertainty(records,split_rows)
        self.assertEqual(summary['represented_families'],2)
        np.testing.assert_array_equal(first[1],second[1])

    def test_unrecognized_evaluation_split_rejected(self):
        with self.assertRaises(a.IntegrityError):
            a.evaluation_inputs('arbitrary')


if __name__ == '__main__':
    unittest.main()
