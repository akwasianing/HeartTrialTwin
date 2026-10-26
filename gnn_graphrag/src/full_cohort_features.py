"""Authorized offline MiniLM features; evaluation queries have a separate path."""
from __future__ import annotations

import os
for _key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key] = '1'
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')

import argparse
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import random
import shutil
import time

import numpy as np

from . import full_cohort_access as a


def configure(seed=20261023):
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    return torch


def snapshot_hash(directory):
    digest = hashlib.sha256()
    files = {}
    for path in sorted(p for p in Path(directory).rglob('*') if p.is_file()):
        name = path.relative_to(directory).as_posix()
        encoded = name.encode()
        digest.update(len(encoded).to_bytes(8,'big'))
        digest.update(encoded)
        with path.open('rb') as handle:
            for block in iter(lambda:handle.read(1048576),b''):
                digest.update(block)
        files[name] = {'sha256':a.sha(path),'bytes':path.stat().st_size}
    return digest.hexdigest(),files


def matrix_hash(values):
    return hashlib.sha256(np.asarray(values,dtype='<f4',order='C').tobytes()).hexdigest()


def check_semantic(values,count):
    a.require(values.shape == (count,384) and values.dtype == np.float32 and np.isfinite(values).all(), 'Invalid semantic matrix')
    a.require(np.allclose(np.linalg.norm(values,axis=1),1,rtol=1e-5,atol=1e-5), 'Non-normalized semantic features')


def combine_types(semantic,nodes):
    check_semantic(semantic,len(nodes))
    types = np.zeros((len(nodes),6),dtype='<f4')
    for i,node in enumerate(nodes):
        a.require(node['node_label'] in a.LABELS[:4], 'Excluded context node type')
        types[i,a.LABELS.index(node['node_label'])] = 1
    return np.ascontiguousarray(np.concatenate((semantic,types),axis=1),dtype='<f4')


class LocalEncoder:
    def __init__(self):
        cfg = a.authorize('context_train_features')['features']
        configure()
        from huggingface_hub import snapshot_download
        from sentence_transformers import SentenceTransformer
        from tokenizers import Tokenizer
        path = Path(snapshot_download(repo_id=cfg['model'],revision=cfg['revision'],local_files_only=True)).resolve()
        digest,files = snapshot_hash(path)
        a.require(digest == cfg['snapshot_sha256'], 'Pinned encoder snapshot mismatch')
        self.tokenizer = Tokenizer.from_file(str(path/'tokenizer.json'))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.model = SentenceTransformer(str(path),device='cpu',local_files_only=True,trust_remote_code=False)
        self.model.float().eval()
        a.require(self.model.max_seq_length == 256 and self.model.get_sentence_embedding_dimension() == 384
                  and str(self.model.device) == 'cpu' and self.model.tokenizer.is_fast, 'Encoder configuration mismatch')
        a.require(self.model.tokenizer.truncation_side == 'right', 'Unexpected truncation side')
        self.provenance = {'model':cfg['model'],'revision':cfg['revision'],'snapshot_sha256':digest,'files':files,
                           'packages':{name:importlib.metadata.version(name) for name in ('torch','numpy','sentence-transformers','transformers','tokenizers','huggingface-hub','safetensors')},
                           'device':'cpu','threads':1,'max_seq_length':256,'batch_size':16,'pooling':'attention_mask_mean_then_L2_normalization'}

    def audit(self,texts):
        counts = []
        for i in range(0,len(texts),128):
            counts.extend(len(r.ids) for r in self.tokenizer.encode_batch(texts[i:i+128],add_special_tokens=True))
        a.require(counts and max(counts) <= 256, 'Input truncation would occur; no publication')
        return {'rows':len(texts),'maximum_tokens_including_specials':max(counts),'truncated_rows':0}

    def encode(self,texts):
        import torch
        with torch.inference_mode():
            values = self.model.encode(texts,batch_size=16,normalize_embeddings=True,convert_to_numpy=True,
                                       show_progress_bar=False,device='cpu',precision='float32')
        return np.asarray(values,dtype='<f4',order='C')


def encode_repeat(encoder,texts):
    a.require(all(isinstance(t,str) and t.strip() and not a.protocol.extraction.NCT_TOKEN.search(t) for t in texts), 'Unsafe encoder text')
    audit = encoder.audit(texts)
    started = time.perf_counter()
    first = encoder.encode(texts)
    seconds = time.perf_counter()-started
    check_semantic(first,len(texts))
    print(json.dumps({'event':'first_encoding_complete','rows':len(texts),'seconds':seconds}),flush=True)
    repeated = encoder.encode(texts)
    check_semantic(repeated,len(texts))
    difference = float(np.max(np.abs(first-repeated)))
    a.require(matrix_hash(first) == matrix_hash(repeated) and difference == 0, 'Repeated encoding not byte-identical')
    return first,{'tokenization':audit,'first_encoding_seconds':seconds,'amortized_encoding_seconds_per_row':seconds/len(texts),
                  'repeat_max_absolute_difference':difference,'canonical_matrix_sha256':matrix_hash(first),'repeat_sha256':matrix_hash(repeated)}


def write_mapping(path,items,fields):
    with Path(path).open('x',newline='') as handle:
        writer = csv.DictWriter(handle,fields,lineterminator='\n')
        writer.writeheader()
        writer.writerows(items)


def save_array(path,values):
    with Path(path).open('xb') as handle:
        np.save(handle,np.asarray(values,dtype='<f4',order='C'),allow_pickle=False)


def verify_recovered_context(encoder,nodes,previous):
    """Compare preserved output to a fresh pass; never relax exact repeat checks."""
    a.require(previous.shape == (len(nodes),390), 'Recovered context shape mismatch')
    check_semantic(previous[:,:384],len(nodes))
    texts = [r['feature_text'] for r in nodes]
    audit = encoder.audit(texts)
    started = time.perf_counter()
    fresh = encoder.encode(texts)
    check_semantic(fresh,len(nodes))
    combined = combine_types(fresh,nodes)
    difference = float(np.max(np.abs(previous-combined)))
    a.require(difference == 0 and matrix_hash(previous) == matrix_hash(combined), 'Recovered context repeat not byte-identical')
    seconds = time.perf_counter()-started
    print(json.dumps({'event':'recovered_context_verified','rows':len(nodes),'seconds':seconds,'maximum_difference':difference}),flush=True)
    return previous,{'tokenization':audit,'recovery_verification_seconds':seconds,'first_encoding_seconds':None,
                     'first_encoding_timing_not_retained_in_partial_bundle':True,'repeat_max_absolute_difference':difference,
                     'canonical_matrix_sha256':matrix_hash(previous[:,:384]),'repeat_sha256':matrix_hash(fresh)}


def reuse_recovery_verification(encoder,nodes,source,record):
    """Reuse only the hash-bound successful execution record, not an unchecked cache."""
    record = Path(record).resolve()
    a.require(record == (a.RUN/'context_recovery_verification.json').resolve()
              and a.sha(record) == 'bfbcd9ec58b79173dfb4d9c83e80b38c682e88369104b8bed85e7e761bf93f01', 'Unverified recovery record')
    proof = json.loads(record.read_text())
    a.require(proof['protocol_sha256'] == a.PROTOCOL_SHA and proof['authorization_sha256'] == a.AUTH_SHA
              and proof['config_sha256'] == a.CONFIG_SHA and proof['input_context_sha256'] == a.manifest()['files_sha256']['training/context_nodes.jsonl']
              and proof['maximum_absolute_difference'] == 0 and proof['rows'] == len(nodes) == 9036, 'Recovery evidence binding mismatch')
    a.require(proof['model_revision'] == encoder.provenance['revision'] and proof['model_snapshot_sha256'] == encoder.provenance['snapshot_sha256'], 'Recovery encoder mismatch')
    a.require(a.sha(source) == proof['context_file_sha256'], 'Recovered context checksum changed')
    previous = np.load(source,allow_pickle=False)
    check_semantic(previous[:,:384],len(nodes))
    a.require(matrix_hash(previous) == proof['context_matrix_sha256'] and matrix_hash(previous[:,:384]) == proof['semantic_matrix_sha256']
              and np.array_equal(previous,combine_types(previous[:,:384],nodes)), 'Recovery array/type mismatch')
    audit = encoder.audit([r['feature_text'] for r in nodes])
    print(json.dumps({'event':'reuse_successful_recovery_verification','record_sha256':a.sha(record),'maximum_difference':0.0}),flush=True)
    return previous,{'tokenization':audit,'recovery_verification_seconds':proof['recovery_verification_seconds'],
                     'verification_reused_not_rerun':True,'verification_record_sha256':a.sha(record),'first_encoding_seconds':None,
                     'first_encoding_timing_not_retained_in_partial_bundle':True,'repeat_max_absolute_difference':0.0,
                     'canonical_matrix_sha256':proof['semantic_matrix_sha256'],'repeat_sha256':proof['semantic_matrix_sha256']}


def generate_context_train(destination=a.FEATURES,encoder=None,resume_context=None,recovery_verification=None):
    cfg = a.authorize('context_train_features')
    nodes,queries,edges,candidates = a.feature_inputs()
    with a.atomic_directory(destination) as stage:
        encoder = encoder or LocalEncoder()
        if resume_context is None:
            semantic,node_audit = encode_repeat(encoder,[r['feature_text'] for r in nodes])
            combined = combine_types(semantic,nodes)
            save_array(stage/'context_features.npy',combined)
        else:
            source = Path(resume_context)
            a.require(source.name == 'context_features.npy' and source.parent.parent.resolve() == a.FEATURES.parent.resolve()
                      and source.parent.name.startswith('.HTT-GNN-ASSOC-FEATURES-v1.incomplete-') and not source.is_symlink(), 'Unexpected recovery input')
            expected = '477a4b7ec0a3f2177e08761dcd22f8ada867fd9ff4f13be69f55c40c4367f494'
            a.require(a.sha(source) == expected, 'Recovered context file checksum mismatch')
            if recovery_verification is None:
                combined,node_audit = verify_recovered_context(encoder,nodes,np.load(source,allow_pickle=False))
            else:
                combined,node_audit = reuse_recovery_verification(encoder,nodes,source,recovery_verification)
            with source.open('rb') as original,(stage/'context_features.npy').open('xb') as copied:
                shutil.copyfileobj(original,copied)
            a.require(a.sha(stage/'context_features.npy') == expected, 'Recovery copy changed bytes')
            node_audit['recovered_file_sha256'] = expected
            node_audit['recovered_from'] = str(source.resolve().relative_to(a.ROOT))
        query_values,query_audit = encode_repeat(encoder,[r['query_text'] for r in queries])
        save_array(stage/'train_query_semantic.npy',query_values)
        write_mapping(stage/'context_index.csv',[{'row_index':i,'original_node_index':r['node_index'],'node_id':r['node_id'],'node_label':r['node_label'],
            'feature_text_sha256':hashlib.sha256(r['feature_text'].encode()).hexdigest()} for i,r in enumerate(nodes)],
            ['row_index','original_node_index','node_id','node_label','feature_text_sha256'])
        write_mapping(stage/'train_query_index.csv',[{'row_index':i,'query_id':r['query_id'],'query_text_sha256':hashlib.sha256(r['query_text'].encode()).hexdigest()} for i,r in enumerate(queries)],
                      ['row_index','query_id','query_text_sha256'])
        policy = {'schema_version':'HTT-GNN-ASSOC-FEATURES-v1','encoder':cfg['features'],'context_field':'feature_text','query_field':'query_text',
                  'training_only_queries':True,'no_id_embeddings':True,'context_shape':[9036,390],'query_shape':[11712,384],
                  'combined_vector_renormalized':False,'context_order':'original_indices_0_to_9035','heldout_truth_access':False}
        a.save_json(stage/'feature_policy.json',policy)
        a.save_json(stage/'tokenization_audit.json',{'context':node_audit,'training_queries':query_audit})
        m = a.manifest()
        inputs = ['training/manifest.json','training/context_nodes.jsonl','training/queries.jsonl','training/message_edges.csv','candidate_trials.csv']
        a.bundle_manifest(stage,{'schema_version':'HTT-GNN-ASSOC-FEATURES-v1','policy_sha256':a.object_sha(policy),'encoder':encoder.provenance,
            'context_shape':list(combined.shape),'query_shape':list(query_values.shape),'context_matrix_sha256':matrix_hash(combined),
            'query_matrix_sha256':matrix_hash(query_values),'input_sha256':{n:m['files_sha256'][n] for n in inputs},
            'implementation_sha256':a.sha(__file__),'access_implementation_sha256':a.sha(a.__file__),'edge_count':len(edges),'candidate_count':len(candidates)})
    return a.verify_bundle(destination)


def generate_evaluation(split,encoder=None):
    queries = a.evaluation_inputs(split,truth=False)
    destination = a.FEATURES.parent/('HTT-GNN-EVAL-FEATURES-'+split+'-v1')
    with a.atomic_directory(destination) as stage:
        encoder = encoder or LocalEncoder()
        values,audit = encode_repeat(encoder,[r['query_text'] for r in queries])
        save_array(stage/'query_semantic.npy',values)
        write_mapping(stage/'query_index.csv',[{'row_index':i,'query_id':r['query_id'],'query_text_sha256':hashlib.sha256(r['query_text'].encode()).hexdigest()} for i,r in enumerate(queries)],
                      ['row_index','query_id','query_text_sha256'])
        a.save_json(stage/'tokenization_audit.json',audit)
        name = 'evaluation/'+split+'_queries.jsonl'
        a.bundle_manifest(stage,{'schema_version':'HTT-GNN-EVAL-FEATURES-v1','split':split,'encoder':encoder.provenance,'shape':list(values.shape),
            'matrix_sha256':matrix_hash(values),'query_input_sha256':a.manifest()['files_sha256'][name],'implementation_sha256':a.sha(__file__),
            'selection_sha256':a.sha(a.RUN/'training/selection.json') if split == 'test' else None,'heldout_truth_access':False})
    return a.verify_bundle(destination)


def load_arrays(split=None):
    directory = a.FEATURES if split is None else a.FEATURES.parent/('HTT-GNN-EVAL-FEATURES-'+split+'-v1')
    m = a.verify_bundle(directory)
    if split is None:
        context = np.load(directory/'context_features.npy',allow_pickle=False)
        queries = np.load(directory/'train_query_semantic.npy',allow_pickle=False)
        a.require(context.shape == (9036,390) and queries.shape == (11712,384), 'Feature shape mismatch')
        check_semantic(context[:,:384],9036)
        check_semantic(queries,11712)
        a.require(matrix_hash(context) == m['context_matrix_sha256'] and matrix_hash(queries) == m['query_matrix_sha256'], 'Feature payload mismatch')
        types = context[:,384:]
        a.require(np.isin(types,[0,1]).all() and (types.sum(1) == 1).all() and not types[:,4:].any(), 'Invalid type encoding')
        return context,queries
    query = np.load(directory/'query_semantic.npy',allow_pickle=False)
    check_semantic(query,{'validation':2068,'test':2219}[split])
    a.require(matrix_hash(query) == m['matrix_sha256'], 'Evaluation payload mismatch')
    return query


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generate',choices=['context-train','validation','test'])
    parser.add_argument('--resume-context',type=Path,help='Verified context-only incomplete bundle from the interrupted run')
    parser.add_argument('--recovery-verification',type=Path,help='Hash-bound record of the already successful recovery comparison')
    args = parser.parse_args()
    a.require(args.resume_context is None or args.generate == 'context-train', 'Recovery applies only to context/train features')
    a.require(args.recovery_verification is None or args.resume_context is not None, 'Recovery record requires a context source')
    if not args.generate:
        nodes,queries,edges,_ = a.feature_inputs()
        print(json.dumps({'mode':'validate_only','nodes':len(nodes),'training_queries':len(queries),'edges':len(edges),'encoder_instantiated':False}))
    elif args.generate == 'context-train':
        print(json.dumps(generate_context_train(resume_context=args.resume_context,recovery_verification=args.recovery_verification),indent=2))
    else:
        print(json.dumps(generate_evaluation(args.generate),indent=2))


if __name__ == '__main__':
    main()
