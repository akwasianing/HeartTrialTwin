"""Frozen MiniLM cosine adapter. Only context vectors and candidate metadata read."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from .identity import (FEATURES, PROTOCOL, FEATURE_SHA, PROTOCOL_SHA, MODEL, REVISION,
                       SNAPSHOT_SHA, DIMENSION, TRIAL_COUNT, VERSION, require, sha,
                       check_k, check_text, normalize_query, DATASET, GRAPH, SNAPSHOT)


class MiniLMRanker:
    def __init__(self, feature_directory=FEATURES, protocol_directory=PROTOCOL):
        import numpy as np
        feature_directory, protocol_directory = Path(feature_directory), Path(protocol_directory)
        require(sha(feature_directory/'manifest.json') == FEATURE_SHA, 'Feature manifest checksum mismatch')
        require(sha(protocol_directory/'split_manifest.json') == PROTOCOL_SHA, 'Protocol manifest checksum mismatch')
        feature = json.loads((feature_directory/'manifest.json').read_text())
        protocol = json.loads((protocol_directory/'split_manifest.json').read_text())
        encoder = feature['encoder']
        require(feature['schema_version'] == 'HTT-GNN-ASSOC-FEATURES-v1'
                and feature['protocol_sha256'] == PROTOCOL_SHA and protocol['training_permitted'] is False,
                'Frozen feature/protocol identity mismatch')
        require((encoder['model'], encoder['revision'], encoder['snapshot_sha256'], encoder['max_seq_length'])
                == (MODEL, REVISION, SNAPSHOT_SHA, 256), 'Encoder identity mismatch')
        # Deliberately do not verify/open query arrays, training labels or held-out truth.
        for name in ('context_features.npy', 'context_index.csv', 'feature_policy.json'):
            require(sha(feature_directory/name) == feature['files_sha256'][name], 'Runtime feature checksum mismatch')
        require(sha(protocol_directory/'candidate_trials.csv') == protocol['files_sha256']['candidate_trials.csv']
                == feature['input_sha256']['candidate_trials.csv'], 'Candidate checksum mismatch')
        with (feature_directory/'context_index.csv').open(newline='') as handle:
            index = list(csv.DictReader(handle))
        require(len(index) == 9036 and set(index[0]) == {'row_index','original_node_index','node_id','node_label','feature_text_sha256'},
                'Context index schema mismatch')
        counts = [('Trial',2824),('ConditionTerm',1743),('Intervention',3417),('Sponsor',1052)]
        start = 0
        for label,count in counts:
            group = index[start:start+count]
            require(all(v['node_label'] == label and int(v['row_index']) == start+i
                        and int(v['original_node_index']) == start+i for i,v in enumerate(group)), 'Node index mismatch')
            ids = [v['node_id'] for v in group]
            require(ids == sorted(set(ids)), 'Nonunique or unordered node IDs')
            start += count
        ids = [v['node_id'] for v in index[:TRIAL_COUNT]]
        with (protocol_directory/'candidate_trials.csv').open(newline='') as handle:
            candidates = list(csv.DictReader(handle))
        require(len(candidates) == TRIAL_COUNT and all(set(v) == {'candidate_index','nct_id'}
                and int(v['candidate_index']) == i and v['nct_id'] == ids[i]
                and re.fullmatch(r'NCT\d{8}',v['nct_id']) for i,v in enumerate(candidates)), 'Candidate ordering mismatch')
        values = np.load(feature_directory/'context_features.npy', allow_pickle=False)
        require(values.shape == (9036,390) and values.dtype == np.float32 and np.isfinite(values).all(), 'Invalid context matrix')
        require(hashlib.sha256(np.asarray(values,dtype='<f4',order='C').tobytes()).hexdigest()
                == feature['context_matrix_sha256'], 'Context payload checksum mismatch')
        require(np.allclose(np.linalg.norm(values[:,:384],axis=1),1,atol=1e-5,rtol=1e-5), 'Non-normalized context semantics')
        types = np.zeros((9036,6),dtype=np.float32)
        start = 0
        for slot,(_,count) in enumerate(counts):
            types[start:start+count,slot] = 1
            start += count
        require(np.array_equal(values[:,384:],types), 'Invalid six-slot type encoding')
        self.vectors = values[:TRIAL_COUNT,:DIMENSION].copy()
        self.vectors.flags.writeable = False
        self.ids = tuple(ids)
        self.encoder_spec = encoder
        self.provenance = {'version':VERSION, 'protocol_sha256':PROTOCOL_SHA, 'feature_manifest_sha256':FEATURE_SHA,
            'dataset_version':DATASET,'graph_version':GRAPH,'snapshot_date':SNAPSHOT,
            'context_file_sha256':feature['files_sha256']['context_features.npy'],
            'context_index_sha256':feature['files_sha256']['context_index.csv'], 'candidate_count':TRIAL_COUNT,
            'model':MODEL, 'revision':REVISION, 'dimensions':DIMENSION, 'normalized':True,
            'metric':'cosine', 'tie_break':'ascending_NCT_ID', 'max_seq_length':256,
            'association_labels_used':False, 'feature_policy':'Approved trial semantic text only; no node-type slots or planned-outcome ownership'}

    def rank_vector(self, query, top_k=3):
        import numpy as np
        check_k(top_k)
        vector = np.asarray(query,dtype=np.float32)
        require(vector.shape == (DIMENSION,) and np.isfinite(vector).all(), 'Query must be a finite 384-D vector')
        norm = float(np.linalg.norm(vector))
        require(norm > 0 and abs(norm-1) <= 1e-5, 'Query must be normalized and nonzero')
        scores = np.clip(self.vectors @ vector,-1,1)
        ordering = np.argsort(-scores,kind='stable')[:top_k]
        return {'status':'OK', 'ranked_trials':[{'rank':rank+1,'nct_id':self.ids[i],
                  'similarity':float(np.clip(scores[i],-1,1)), 'candidate_index':int(i)} for rank,i in enumerate(ordering)],
                'provenance':dict(self.provenance)}


class LocalQueryEncoder:
    """Load the pinned existing CPU model offline, encode questions only."""
    def __init__(self, spec):
        import os
        for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
            os.environ[name] = '1'
        os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
        from importlib.metadata import version
        require(all(version(k) == v for k,v in spec['packages'].items()), 'Query encoder package version mismatch')
        from huggingface_hub import snapshot_download
        from sentence_transformers import SentenceTransformer
        from tokenizers import Tokenizer
        import torch
        torch.manual_seed(20261023)
        torch.set_num_threads(1)
        if torch.get_num_interop_threads() != 1:
            torch.set_num_interop_threads(1)
        torch.use_deterministic_algorithms(True)
        path = Path(snapshot_download(repo_id=MODEL,revision=REVISION,local_files_only=True))
        require(path.name == REVISION, 'Cached model revision mismatch')
        digest = hashlib.sha256()
        files = sorted(p for p in path.rglob('*') if p.is_file())
        require({p.relative_to(path).as_posix() for p in files} == set(spec['files']), 'Cached model file set mismatch')
        for file in files:
            name = file.relative_to(path).as_posix()
            require(sha(file) == spec['files'][name]['sha256'], 'Cached model checksum mismatch')
            encoded = name.encode()
            digest.update(len(encoded).to_bytes(8,'big'))
            digest.update(encoded)
            with file.open('rb') as handle:
                for block in iter(lambda:handle.read(1048576),b''):
                    digest.update(block)
        require(digest.hexdigest() == SNAPSHOT_SHA, 'Cached model snapshot mismatch')
        self.tokenizer = Tokenizer.from_file(str(path/'tokenizer.json'))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.model = SentenceTransformer(str(path), device='cpu',local_files_only=True,trust_remote_code=False)
        self.model.float().eval()
        require(self.model.max_seq_length == 256 and self.model.get_sentence_embedding_dimension() == DIMENSION
                and str(self.model.device) == 'cpu', 'Local model dimensions/context mismatch')

    def encode(self, text):
        text = normalize_query(text)
        require(len(self.tokenizer.encode(text).ids) <= 256, 'Query exceeds 256-token limit; no silent truncation')
        import torch
        with torch.inference_mode():
            return self.model.encode([text], normalize_embeddings=True,convert_to_numpy=True,
                                     show_progress_bar=False,device='cpu')[0]
