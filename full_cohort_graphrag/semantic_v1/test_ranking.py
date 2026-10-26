"""Offline numeric tests, run only in .venv-vector-rag; no database/model service."""
import builtins
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from . import ranking as r
from .identity import SemanticError, FEATURE_SHA


class RankingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ranker = r.MiniLMRanker()

    def test_real_shape_order_normalization(self):
        x = self.ranker
        self.assertEqual(x.vectors.shape,(2824,384))
        self.assertEqual(list(x.ids),sorted(set(x.ids)))
        self.assertFalse(x.vectors.flags.writeable)
        np.testing.assert_allclose(np.linalg.norm(x.vectors,axis=1),1,atol=1e-5)

    def test_actual_scores_and_determinism(self):
        x = self.ranker
        query = x.vectors[0]
        first = x.rank_vector(query,10)
        self.assertEqual(first,x.rank_vector(query,10))
        scores = np.clip(x.vectors@query,-1,1)
        expected = np.argsort(-scores,kind='stable')[:10]
        self.assertEqual([v['nct_id'] for v in first['ranked_trials']],[x.ids[i] for i in expected])
        for row in first['ranked_trials']:
            self.assertEqual(row['similarity'],float(scores[row['candidate_index']]))

    def test_equal_scores_use_nct_order(self):
        x = object.__new__(r.MiniLMRanker)
        x.vectors = np.zeros((2824,384),np.float32)
        x.vectors[:,0] = 1
        x.ids = self.ranker.ids
        x.provenance = self.ranker.provenance
        vector = x.vectors[0]
        self.assertEqual([v['nct_id'] for v in x.rank_vector(vector,5)['ranked_trials']],list(x.ids[:5]))

    def test_invalid_vectors_and_k(self):
        for query in (np.zeros(384),np.ones(384),np.zeros(64),np.full(384,np.nan)):
            with self.assertRaises(SemanticError):
                self.ranker.rank_vector(query)
        for k in (0,21,True,1.5):
            with self.assertRaises(SemanticError):
                self.ranker.rank_vector(self.ranker.vectors[0],k)

    def test_manifest_mismatch_rejected(self):
        with patch.object(r,'FEATURE_SHA','0'*64),self.assertRaisesRegex(SemanticError,'manifest checksum'):
            r.MiniLMRanker()
        with patch.object(r,'PROTOCOL_SHA','0'*64),self.assertRaises(SemanticError):
            r.MiniLMRanker()

    def test_context_file_hash_mismatch_rejected(self):
        original = r.sha
        def changed(path):
            return '0'*64 if Path(path).name == 'context_features.npy' else original(path)
        with patch.object(r,'sha',changed),self.assertRaisesRegex(SemanticError,'feature checksum'):
            r.MiniLMRanker()

    def test_invalid_dimensions_rejected(self):
        with patch.object(np,'load',return_value=np.zeros((2824,390),np.float32)),self.assertRaisesRegex(SemanticError,'context matrix'):
            r.MiniLMRanker()

    def test_ordering_mismatch_rejected(self):
        original = r.csv.DictReader
        def changed(handle):
            rows = list(original(handle))
            if Path(handle.name).name == 'context_index.csv':
                rows[0],rows[1] = rows[1],rows[0]
            return iter(rows)
        with patch.object(r.csv,'DictReader',changed),self.assertRaisesRegex(SemanticError,'index mismatch'):
            r.MiniLMRanker()

    def test_no_label_or_query_array_reads(self):
        real = io.open
        def guarded(path,*args,**kwargs):
            if isinstance(path,(str,Path)):
                name=str(path)
                self.assertFalse(any(s in name for s in ('/truth/','train_query','/evaluation_','/training/queries','/training/families')))
            return real(path,*args,**kwargs)
        with patch('io.open',guarded):
            x = r.MiniLMRanker()
        self.assertEqual(x.provenance['feature_manifest_sha256'],FEATURE_SHA)
        self.assertFalse(x.provenance['association_labels_used'])

    def test_worker_rejects_unexpected_requests(self):
        from .worker import execute
        with self.assertRaises(SemanticError):
            execute({'operation':'validate','query_text':'unexpected'})

    def test_encoder_rejects_silent_truncation_without_running_model(self):
        from unittest.mock import Mock
        from types import SimpleNamespace
        encoder = object.__new__(r.LocalQueryEncoder)
        encoder.tokenizer = Mock()
        encoder.tokenizer.encode.return_value = SimpleNamespace(ids=list(range(257)))
        encoder.model = Mock()
        with self.assertRaisesRegex(SemanticError,'256-token'):
            encoder.encode('permitted query')
        encoder.model.encode.assert_not_called()

    def test_query_normalization_matches_frozen_policy(self):
        self.assertEqual(r.normalize_query('  Quality   OF Life '),'quality of life')
        with self.assertRaises(SemanticError):
            r.normalize_query('query\nsecond instruction')


if __name__ == '__main__':
    unittest.main()
