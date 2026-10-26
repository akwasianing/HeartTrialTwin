"""Step 66G-1 diagnostics only: frozen train/validation, never test evaluation.

One prespecified 16-query, 200-step training-only overfit check is NOT a new
benchmark model. Frozen production modules, bundles and checkpoints are read only.
"""
from __future__ import annotations

from . import full_cohort_features as f
from . import full_cohort_access as a
from . import full_cohort_experiment as e
from . import full_cohort_ranking as r
from .model import mean_aggregate

import builtins
from contextlib import contextmanager
import io
import json
from pathlib import Path
import time
from unittest.mock import patch

import numpy as np
import torch
from torch.nn import functional as F

OUTPUT = a.ROOT/'gnn_graphrag/diagnostics/HTT-GNN-DIAG-66G1-v1'


@contextmanager
def no_test_reads():
    """Fail closed on test truth/features/results and global association catalogs."""
    opened = set()
    original_open, original_io = builtins.open, io.open
    def guarded(original):
        def call(file, *args, **kwargs):
            if isinstance(file, (str, bytes, Path)):
                name = str(file)
                forbidden = ('/truth/test.', '/evaluation/test_', '/evaluation_test/',
                             'HTT-GNN-EVAL-FEATURES-test-', '/query_catalog.',
                             '/positive_associations.')
                a.require(not any(part in name for part in forbidden), 'Diagnostic test/global-truth read blocked')
                if str(a.ROOT) in name:
                    opened.add(name)
            return original(file, *args, **kwargs)
        return call
    with patch('builtins.open', guarded(original_open)), patch('io.open', guarded(original_io)):
        yield opened


def rank_stats(query, candidates, positives):
    """Cosine-space ranking, deterministic candidate-order tie break; bounded blocks."""
    rr, hits = [], []
    for start in range(0, len(query), 128):
        scores = query[start:start+128] @ candidates.T
        for row, ids in zip(scores, positives[start:start+128]):
            ids = np.asarray(ids, dtype=int)
            best_score = row[ids].max()
            best_index = min(i for i in ids if row[i] == best_score)
            rank = int((row > best_score).sum()+((row == best_score) & (np.arange(len(row)) < best_index)).sum())+1
            rr.append(1/rank)
            hits.append(rank == 1)
    return {'MRR': float(np.mean(rr)), 'Hit@1': float(np.mean(hits)),
            'queries': len(rr), 'candidates': len(candidates)}


def geometry(vectors):
    """Centered spectrum and fixed training-pair cosines; not a collapse threshold."""
    x = np.asarray(vectors, dtype=np.float64)
    norms = np.linalg.norm(x, axis=1)
    unit = x/np.maximum(norms[:, None], 1e-12)
    eigen = np.maximum(np.linalg.eigvalsh(np.cov(unit, rowvar=False)), 0)
    effective = float(eigen.sum()**2/max(float(eigen@eigen), 1e-30))
    rng = np.random.default_rng(20261023)
    i = rng.integers(0, len(x), 4096)
    j = rng.integers(0, len(x)-1, 4096)
    j += j >= i
    pairs = (unit[i]*unit[j]).sum(1)
    return {'rows': len(x), 'dimensions': x.shape[1], 'zero_vectors': int((norms == 0).sum()),
            'unique_vectors': len(np.unique(x, axis=0)), 'mean_norm': float(norms.mean()),
            'min_norm': float(norms.min()), 'max_norm': float(norms.max()),
            'centered_participation_rank': effective, 'centered_variance_trace': float(eigen.sum()),
            'pair_cosine_mean': float(pairs.mean()), 'pair_cosine_p05_p50_p95': np.percentile(pairs, [5,50,95]).tolist(),
            'coordinate_zero_fraction': float(np.mean(x == 0))}


def snapshot():
    directories = [a.FEATURES, a.FEATURES.parent/'HTT-GNN-EVAL-FEATURES-validation-v1',
                   a.RUN/'training', a.RUN/'evaluation_validation', a.PROTOCOL/'training']
    paths = [p for directory in directories for p in directory.rglob('*') if p.is_file() and p.suffix != '.pyc']
    paths += [a.PROTOCOL/'split_manifest.json', a.PROTOCOL.parent/'HTT-GNN-ASSOC-PROTOCOL-v1/split_manifest.json',
              a.PROTOCOL/'evaluation/validation_queries.jsonl', a.PROTOCOL/'truth/validation.jsonl',
              a.PROTOCOL/'candidate_trials.csv', a.PROTOCOL/'trial_splits.csv',
              a.RUN/'authorization.json', a.RUN/'experiment_config.json']
    paths += [Path(m.__file__) for m in (a,f,e,r)]
    paths += [Path(__file__).with_name('model.py')]
    return {str(p.relative_to(a.ROOT)): a.sha(p) for p in sorted(set(paths))}


def tiny_indices(queries, count=16):
    """First query IDs with a single known positive and distinct positive owners."""
    chosen, owners = [], set()
    for i in sorted(range(len(queries)), key=lambda j: queries[j]['query_id']):
        ids = queries[i]['positive_trial_ids']
        if len(ids) == 1 and ids[0] not in owners:
            chosen.append(i)
            owners.add(ids[0])
            if len(chosen) == count:
                return chosen
    raise a.IntegrityError('Insufficient training-only sanity examples')


def tiny_overfit(inputs, context, queries, edges, positions, positives, pools, cfg):
    """Fresh seeded weights; fixed 200 steps, no validation access or selection."""
    selected = tiny_indices(inputs['queries'])
    target = torch.from_numpy(positives[selected])
    chosen_pools = [pools[i] for i in selected]
    projected = queries[selected]
    f.configure(cfg['seed'])
    model = r.AssociationRanker()
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg['optimization']['learning_rate'],
                                 weight_decay=cfg['optimization']['weight_decay'])
    start = time.perf_counter()
    history = []
    for step in range(201):
        if step % 25 == 0:
            model.eval()
            with torch.inference_mode():
                metrics = rank_stats(model.queries(projected).numpy(), model.trials(context,edges)[positions].numpy(),
                                     [[int(positives[i,0])] for i in selected])
            history.append({'step':step, **metrics})
            print(json.dumps({'event':'tiny_training_only_sanity', **history[-1]}), flush=True)
        if step == 200:
            break
        model.train()
        optimizer.zero_grad(set_to_none=True)
        negative = torch.from_numpy(r.sample_negatives(chosen_pools, cfg['seed']+step+1))
        scores = model.queries(projected) @ model.trials(context, edges)[positions].T
        loss = r.multi_positive_loss(scores, target, negative, cfg['optimization']['temperature'])
        loss.backward()
        grad = torch.nn.utils.clip_grad_norm_(model.parameters(), cfg['optimization']['gradient_clip_norm'])
        a.require(bool(torch.isfinite(loss)) and bool(torch.isfinite(grad)), 'Tiny sanity nonfinite state')
        optimizer.step()
        if step % 25 == 0 or step == 199:
            history[-1].update(loss_before_next_update=float(loss.detach()), gradient_norm=float(grad))
    return {'selection_rule':'first sorted query IDs, single known owner, distinct training owners; no performance selection',
            'query_ids':[inputs['queries'][i]['query_id'] for i in selected],
            'owner_ids':[inputs['queries'][i]['positive_trial_ids'][0] for i in selected],
            'steps':200, 'candidate_count':1976, 'configuration':'same architecture/Adam/lr/temperature/clip/seed; only 16 training queries',
            'history':history, 'seconds':time.perf_counter()-start,
            'all_training_examples_top1_at_final_step':history[-1]['Hit@1'] == 1,
            'validation_or_test_used':False, 'checkpoint_saved':False}


def run(destination=OUTPUT):
    destination = Path(destination)
    a.require(not destination.exists(), 'Never overwrite diagnostic outputs')
    destination.mkdir(parents=True)
    with no_test_reads() as accessed:
        protected = snapshot()
        cfg = a.authorize('training')
        a.save_json(destination/'diagnostic_plan.json', {
            'version':'HTT-GNN-DIAG-66G1-v1', 'authorization':'Project owner Step 66G-1: train-only tiny fit and fixed-weight train/validation ablation',
            'frozen_protocol_sha256':a.PROTOCOL_SHA, 'frozen_config_sha256':a.CONFIG_SHA,
            'fixed_weight_checkpoints':['untrained_model.pt','selected_model.pt','last_model.pt'],
            'tiny_fit':{'queries':16,'steps':200,'seed':cfg['seed'],'candidate_universe':'1976 training trials',
                        'selection':'sorted query ID; single owner; distinct training owners','hyperparameters':'unchanged',
                        'validation_or_test_selection':False},
            'ablation':'selected checkpoint, empty message edges only; no fitting',
            'test_access':False, 'protected_files_before':protected})
        f.configure()
        a.verify_bundle(a.RUN/'training')
        a.verify_bundle(a.RUN/'evaluation_validation')
        inputs,context,queries,edges = e.load_features_and_context()
        val_vectors = torch.from_numpy(f.load_arrays('validation'))
        val_truth,_ = a.evaluation_inputs('validation',truth=True)
        val_projection = a.evaluation_inputs('validation')
        import csv
        with (a.FEATURES.parent/'HTT-GNN-EVAL-FEATURES-validation-v1/query_index.csv').open() as handle:
            a.require([q['query_id'] for q in csv.DictReader(handle)] == [q['query_id'] for q in val_projection]
                      == [q['query_id'] for q in val_truth], 'Validation query/feature mapping mismatch')
        candidates = [n['node_id'] for n in inputs['nodes'][:2824]]
        a.require(candidates == sorted(set(candidates)) and len(candidates) == 2824, 'Trial order mismatch')
        full_position = {n:i for i,n in enumerate(candidates)}
        positions = torch.tensor([full_position[n] for n in inputs['candidate_ids']])
        positives,pools = r.prepare_labels(inputs)
        full_positives = [[full_position[n] for n in q['positive_trial_ids']] for q in inputs['queries']]
        negatives = r.sample_negatives(pools,cfg['seed']+60)
        families = {v['nct_id']:v['family_id'] for v in inputs['families']}
        for i,q in enumerate(inputs['queries']):
            forbidden = set(q['positive_trial_ids']+q['ambiguous_trial_ids'])
            fs = {families[n] for n in q['positive_trial_ids']}
            forbidden |= {n for n in inputs['candidate_ids'] if families[n] in fs}
            a.require(not {inputs['candidate_ids'][j] for j in pools[i]} & forbidden, 'Invalid negative pool')
            a.require(set(negatives[i]) <= set(pools[i]) and len(set(negatives[i])) == 64, 'Invalid sampled negatives')
        aggregated = mean_aggregate(context,edges)
        errors = []
        for target in (0,1,50,500,1975,2823,4567,9035):
            neighbors = edges[0,edges[1] == target]
            reference = context[neighbors].mean(0) if len(neighbors) else torch.zeros(390)
            errors.append(float((reference-aggregated[target]).abs().max()))
        a.require(max(errors) < 1e-6, 'Aggregation does not match independent means')
        pair_edges = set(map(tuple, edges.T.tolist()))
        report = {'schema_version':'HTT-GNN-DIAG-66G1-v1', 'test_accessed':False,
            'aggregation':{'max_absolute_manual_mean_error':max(errors), 'nodes_checked':8,
                           'typed_message_edges':edges.shape[1], 'unique_source_target_pairs':len(pair_edges)},
            'mapping_checks':{'context_feature_and_node_order':True, 'training_candidate_mapping':True,
                              'validation_query_feature_order':True, 'full_candidates':len(candidates)},
            'negative_checks':{'queries':len(pools),'sampled_negatives':int(negatives.size),
                'positive_ambiguous_and_known_family_exclusion_passed':True,
                'multi_positive_queries':sum(len(q['positive_trial_ids']) > 1 for q in inputs['queries']),
                'pool_size_min':min(map(len,pools)), 'pool_size_max':max(map(len,pools))},
            'models':{}}
        initial,_ = e.load_checkpoint(a.RUN/'training/untrained_model.pt')
        initial_state = {k:v.clone() for k,v in initial.state_dict().items()}
        for name in ('untrained','selected','last'):
            model,payload = e.load_checkpoint(a.RUN/'training'/({'untrained':'untrained_model','selected':'selected_model','last':'last_model'}[name]+'.pt'))
            with torch.inference_mode():
                representations = model.graph(context,edges)
                cv = model.trials(context,edges)
                qv = model.queries(queries)
                vq = model.queries(val_vectors)
                aligned = (qv[:,None,:]*cv[torch.from_numpy(positions.numpy()[positives.clip(min=0)])]).sum(2).numpy()
                neg_scores = (qv[:,None,:]*cv[positions[torch.from_numpy(negatives)]]).sum(2).numpy()
                qraw = model.query(queries).numpy()
                loss = r.multi_positive_loss(qv@cv[positions].T,torch.from_numpy(positives),torch.from_numpy(negatives),0.1)
            result = {'epoch':payload['epoch'], 'checkpoint_sha256':a.sha(a.RUN/'training'/({'untrained':'untrained_model','selected':'selected_model','last':'last_model'}[name]+'.pt')),
                'training_all2824':rank_stats(qv.numpy(),cv.numpy(),full_positives),
                'training_only1976':rank_stats(qv.numpy(),cv[positions].numpy(),[[int(j) for j in row if j >= 0] for row in positives]),
                'validation_MRR':r.validation_mrr(vq.numpy(),cv.numpy(),val_truth,candidates),
                'training_fixed_negative_loss':float(loss),
                'trial_geometry_training_only':geometry(cv[positions].numpy()),
                'query_geometry_training_only':geometry(qv.numpy()),
                'layer1_geometry_training_only':geometry(representations.layer1[positions].numpy()),
                'raw_layer2_geometry_training_only':geometry(representations.layer2[positions].numpy()),
                'mean_positive_cosine':float(aligned[positives >= 0].mean()),
                'mean_sampled_unlinked_cosine':float(neg_scores.mean()),
                'query_raw_mean_norm':float(np.linalg.norm(qraw,axis=1).mean()),
                'parameter_delta_norms':{k:float((v-initial_state[k]).norm()) for k,v in model.state_dict().items()}}
            if name == 'selected':
                model.zero_grad(set_to_none=True)
                scores = model.queries(queries) @ model.trials(context,edges)[positions].T
                gradient_loss = r.multi_positive_loss(scores,torch.from_numpy(positives),torch.from_numpy(negatives),0.1)
                gradient_loss.backward()
                result['gradients'] = {k:{'norm':float(p.grad.norm()),'finite':bool(torch.isfinite(p.grad).all()),
                                         'nonzero_fraction':float((p.grad != 0).float().mean())}
                                       for k,p in model.named_parameters()}
                with torch.inference_mode():
                    empty = torch.empty((2,0),dtype=torch.long)
                    no_cv = model.trials(context,empty)
                    result['fixed_weight_no_messages'] = {
                        'training_all2824':rank_stats(qv.numpy(),no_cv.numpy(),full_positives),
                        'validation_MRR':r.validation_mrr(vq.numpy(),no_cv.numpy(),val_truth,candidates),
                        'mean_same_trial_full_vs_empty_cosine':float((cv[positions]*no_cv[positions]).sum(1).mean()),
                        'caveat':'Inference distribution shift; not a retrained MLP comparison or proof that graph information is harmful.'}
            report['models'][name] = result
            print(json.dumps({'event':'frozen_checkpoint_checked','name':name,'training':result['training_all2824'],
                              'validation_MRR':result['validation_MRR']}),flush=True)
        report['semantic_geometry_training_trials'] = geometry(context[positions,:384].numpy())
        report['tiny_training_only_overfit'] = tiny_overfit(inputs,context,queries,edges,positions,positives,pools,cfg)
        history = json.loads((a.RUN/'training/history.json').read_text())
        report['history'] = {'updates':len(history)-1,'selected_epoch':60,'final_epoch':history[-1]['epoch'],
            'first_loss':history[1]['training_loss'],'last_loss':history[-1]['training_loss'],
            'nonfinite_gradients':sum(not np.isfinite(v['gradient_norm_before_clipping']) for v in history[1:]),
            'updates_clipped':sum(v['gradient_norm_before_clipping'] > 1 for v in history[1:]),
            'maximum_gradient_norm':max(v['gradient_norm_before_clipping'] for v in history[1:])}
        after = snapshot()
        a.require(protected == after, 'Frozen files changed during diagnosis')
        report['preservation'] = {'protected_file_count':len(after),'before_sha256':a.object_sha(protected),
                                  'after_sha256':a.object_sha(after),'unchanged':True,
                                  'scope':'train, validation, features, configuration, model/code, V1/V2 manifests; test artifacts not opened'}
        report['files_opened'] = sorted(accessed)
        a.save_json(destination/'diagnostic_results.json',report)
        a.bundle_manifest(destination, {'schema_version':'HTT-GNN-DIAG-66G1-v1',
            'diagnostic_code_sha256':a.sha(__file__),'test_accessed':False,'no_production_modules_modified':True})
    print(json.dumps({'output':str(destination),'protected_files_unchanged':True}),flush=True)


if __name__ == '__main__':
    run()
