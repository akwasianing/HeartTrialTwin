"""Lightweight diagnostic helper checks; no model fitting or held-out test access."""
from pathlib import Path
import unittest

import numpy as np

from gnn_graphrag.src import diagnose_full_cohort as d


class DiagnosisTests(unittest.TestCase):
    def test_rank_metrics_and_stable_ties(self):
        result = d.rank_stats(np.array([[1.,0.],[0.,0.]]),
                              np.array([[1.,0.],[0.,1.],[1.,0.]]), [[2],[1,2]])
        self.assertAlmostEqual(result['MRR'], (1/2+1/2)/2)
        self.assertEqual(result['Hit@1'],0)

    def test_collapse_statistics(self):
        collapsed = d.geometry(np.ones((8,4)))
        distinct = d.geometry(np.eye(4))
        self.assertEqual(collapsed['unique_vectors'],1)
        self.assertEqual(collapsed['centered_participation_rank'],0)
        self.assertGreater(distinct['centered_participation_rank'],2.9)

    def test_test_files_are_blocked(self):
        with d.no_test_reads():
            for name in ('truth/test.jsonl','evaluation_test/results.json',
                         'HTT-GNN-EVAL-FEATURES-test-v1/query_semantic.npy'):
                with self.assertRaises(d.a.IntegrityError):
                    (d.a.ROOT/name).open('rb')

    def test_tiny_subset_is_sorted_single_owner_and_distinct(self):
        queries = [{'query_id':'c','positive_trial_ids':['b']},
                   {'query_id':'a','positive_trial_ids':['a']},
                   {'query_id':'b','positive_trial_ids':['a']},
                   {'query_id':'d','positive_trial_ids':['a','b']}]
        self.assertEqual(d.tiny_indices(queries,2),[1,0])


if __name__ == '__main__':
    unittest.main()
