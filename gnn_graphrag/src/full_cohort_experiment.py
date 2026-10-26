"""One prespecified supervised run and locked fixed-universe baseline evaluation."""
from __future__ import annotations

from . import full_cohort_features as f  # fixes CPU/offline environment before torch
from . import full_cohort_access as a
from . import full_cohort_ranking as r

import argparse
import copy
import csv
import hashlib
import html
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np
import torch
from torch.nn import functional as F


def code_hashes():
    return {Path(module.__file__).name:a.sha(module.__file__) for module in (a,f,r,__import__(__name__,fromlist=['']))}


def environment():
    return {'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),
            'packages':{n:importlib.metadata.version(n) for n in ('torch','numpy','scikit-learn','scipy','joblib','sentence-transformers')},
            'torch_threads':torch.get_num_threads(),'torch_interop_threads':torch.get_num_interop_threads(),
            'deterministic_algorithms':torch.are_deterministic_algorithms_enabled()}


def load_features_and_context():
    inputs = a.training_inputs()
    context,queries = f.load_arrays()
    manifest = a.verify_bundle(a.FEATURES)
    original = a.manifest()
    a.require(all(original['files_sha256'][name] == digest for name,digest in manifest['input_sha256'].items()), 'Feature/source binding mismatch')
    with (a.FEATURES/'context_index.csv').open() as handle:
        index = list(csv.DictReader(handle))
    a.require([v['node_id'] for v in index] == [v['node_id'] for v in inputs['nodes']], 'Feature node mapping mismatch')
    with (a.FEATURES/'train_query_index.csv').open() as handle:
        query_index = list(csv.DictReader(handle))
    a.require([v['query_id'] for v in query_index] == [v['query_id'] for v in inputs['queries']], 'Feature query mapping mismatch')
    edge_index = torch.tensor([[int(e['source_node_index']),int(e['target_node_index'])] for e in inputs['edges']],dtype=torch.long).T.contiguous()
    return inputs,torch.from_numpy(context),torch.from_numpy(queries),edge_index


def checkpoint_payload(model,optimizer,epoch,validation_mrr):
    return {'model_state':copy.deepcopy(model.state_dict()),'optimizer_state':copy.deepcopy(optimizer.state_dict()) if optimizer else None,
            'epoch':epoch,'validation_MRR':validation_mrr,'protocol_sha256':a.PROTOCOL_SHA,'config_sha256':a.CONFIG_SHA,
            'authorization_sha256':a.AUTH_SHA,'feature_manifest_sha256':a.sha(a.FEATURES/'manifest.json'),
            'code_sha256':code_hashes(),'seed':20261023,'torch_version':str(torch.__version__),'environment':environment()}


def save_checkpoint(path,payload):
    with Path(path).open('xb') as handle:
        torch.save(payload,handle)


def load_checkpoint(path):
    payload = torch.load(path,map_location='cpu',weights_only=True)
    a.require(payload['protocol_sha256'] == a.PROTOCOL_SHA and payload['config_sha256'] == a.CONFIG_SHA
              and payload['authorization_sha256'] == a.AUTH_SHA
              and payload['feature_manifest_sha256'] == a.sha(a.FEATURES/'manifest.json'), 'Checkpoint provenance mismatch')
    model = r.AssociationRanker()
    model.load_state_dict(payload['model_state'],strict=True)
    model.eval()
    return model,payload


def validate_model(model,context,edges,validation_vectors,truth,candidates):
    model.eval()
    with torch.inference_mode():
        q = model.queries(validation_vectors).numpy()
        trials = model.trials(context,edges).numpy()
    return r.validation_mrr(q,trials,truth,candidates)


def train(destination=a.RUN/'training'):
    cfg = a.authorize('training')
    f.configure(cfg['seed'])
    with a.atomic_directory(destination) as stage:
        inputs,context,queries,edges = load_features_and_context()
        validation_features = torch.from_numpy(f.load_arrays('validation'))
        # Evaluation-only labels: never passed to loss, sampler or optimizer.
        validation_truth,_ = a.evaluation_inputs('validation',truth=True)
        candidates = [v['node_id'] for v in inputs['nodes'][:2824]]
        positives,pools = r.prepare_labels(inputs)
        positive_tensor = torch.from_numpy(positives)
        full_position = {n:i for i,n in enumerate(candidates)}
        training_trial_indices = torch.tensor([full_position[n] for n in inputs['candidate_ids']],dtype=torch.long)
        model = r.AssociationRanker()
        optimization,selection = cfg['optimization'],cfg['selection']
        optimizer = torch.optim.Adam(model.parameters(),lr=optimization['learning_rate'],weight_decay=optimization['weight_decay'])
        started = time.perf_counter()
        initial_mrr = validate_model(model,context,edges,validation_features,validation_truth,candidates)
        best = checkpoint_payload(model,None,0,initial_mrr)
        save_checkpoint(stage/'untrained_model.pt',best)
        best_mrr,best_epoch,stale = initial_mrr,0,0
        history = [{'epoch':0,'training_loss':None,'validation_MRR':initial_mrr,'elapsed_seconds':time.perf_counter()-started}]
        print(json.dumps({'event':'training_started','initial_validation_MRR':initial_mrr,'maximum_epochs':optimization['epochs']}),flush=True)
        for epoch in range(1,optimization['epochs']+1):
            model.train()
            negatives = r.sample_negatives(pools,cfg['seed']+epoch,optimization['negative_count'])
            optimizer.zero_grad(set_to_none=True)
            trial_vectors = model.trials(context,edges)[training_trial_indices]
            query_vectors = model.queries(queries)
            scores = query_vectors @ trial_vectors.T
            loss = r.multi_positive_loss(scores,positive_tensor,torch.from_numpy(negatives),optimization['temperature'])
            a.require(bool(torch.isfinite(loss)), 'Nonfinite training loss')
            loss.backward()
            grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(),optimization['gradient_clip_norm'])
            a.require(bool(torch.isfinite(grad_norm)), 'Nonfinite gradients')
            optimizer.step()
            entry = {'epoch':epoch,'training_loss':float(loss.detach()),'gradient_norm_before_clipping':float(grad_norm),
                     'validation_MRR':None,'elapsed_seconds':time.perf_counter()-started,'negative_seed':cfg['seed']+epoch}
            if epoch % selection['evaluate_every_epochs'] == 0:
                mrr = validate_model(model,context,edges,validation_features,validation_truth,candidates)
                entry['validation_MRR'] = mrr
                if mrr > best_mrr+selection['minimum_absolute_improvement']:
                    best_mrr,best_epoch,stale = mrr,epoch,0
                    best = checkpoint_payload(model,optimizer,epoch,mrr)
                else:
                    stale += 1
                print(json.dumps({'event':'validation','epoch':epoch,'training_loss':entry['training_loss'],'validation_MRR':mrr,'best_epoch':best_epoch}),flush=True)
            history.append(entry)
            if stale >= selection['patience_evaluations']:
                break
        save_checkpoint(stage/'selected_model.pt',best)
        save_checkpoint(stage/'last_model.pt',checkpoint_payload(model,optimizer,epoch,history[-1]['validation_MRR']))
        a.save_json(stage/'history.json',history)
        a.save_json(stage/'selection.json',{'schema_version':'HTT-GNN-CHECKPOINT-SELECTION-v1','checkpoint_sha256':a.sha(stage/'selected_model.pt'),
            'selected_epoch':best_epoch,'validation_MRR':best_mrr,'epochs_completed':epoch,'test_accessed':False,
            'protocol_sha256':a.PROTOCOL_SHA,'authorization_sha256':a.AUTH_SHA,'config_sha256':a.CONFIG_SHA,
            'code_sha256':code_hashes(),'training_seconds':time.perf_counter()-started,'selection_rule':selection})
        write_training_svg(stage/'training_curves.svg',history)
        a.bundle_manifest(stage,{'schema_version':'HTT-GNN-TRAINING-v1','training_queries':11712,'training_candidates':1976,
            'feature_manifest_sha256':a.sha(a.FEATURES/'manifest.json'),'mask_sha256':a.manifest()['files_sha256']['training/message_edges.csv'],
            'validation_queries':2068,'code_sha256':code_hashes(),'training_permitted_in_frozen_artifacts':False})
    print(json.dumps(json.loads((Path(destination)/'selection.json').read_text()),indent=2))


def write_training_svg(path,history):
    charts = [('Training multi-positive loss','training_loss',40),('Validation MRR (selection only)','validation_MRR',390)]
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="740" viewBox="0 0 1100 740"><rect width="1100" height="740" fill="white"/>']
    for title,key,top in charts:
        values = [(h['epoch'],h[key]) for h in history if h[key] is not None]
        lo,hi = min(y for _,y in values),max(y for _,y in values)
        span = max(hi-lo,1e-8)
        points = ' '.join(f'{80+x/max(history[-1]["epoch"],1)*940:.2f},{top+260-(y-lo)/span*210:.2f}' for x,y in values)
        svg.extend([f'<text x="80" y="{top+15}" font-size="22" font-family="sans-serif">{title}</text>',
                    f'<path d="M80 {top+45} V{top+260} H1020" fill="none" stroke="#555"/>',
                    f'<polyline points="{points}" fill="none" stroke="#1865a3" stroke-width="3"/>',
                    f'<text x="8" y="{top+55}" font-size="14">{hi:.5f}</text>',f'<text x="8" y="{top+260}" font-size="14">{lo:.5f}</text>',
                    f'<text x="80" y="{top+290}" font-size="16">Epoch 0 → {history[-1]["epoch"]}; registered association ranking, not clinical prediction</text>'])
    svg.append('</svg>')
    with Path(path).open('x') as handle:
        handle.write('\n'.join(svg))


def evaluation(split):
    a.authorize('validation_evaluation' if split == 'validation' else 'test_evaluation_after_selection')
    selection = a.selected_checkpoint()
    a.require(selection['code_sha256'] == code_hashes(), 'Code changed after selection; evaluation blocked')
    f.configure()
    with a.atomic_directory(a.RUN/('evaluation_'+split)) as stage:
        inputs,context,train_queries,edges = load_features_and_context()
        query_features = f.load_arrays(split)
        truth,split_rows = a.evaluation_inputs(split,truth=True)
        projected = a.evaluation_inputs(split,truth=False)
        a.require([q['query_id'] for q in truth] == [q['query_id'] for q in projected], 'Query/truth ordering mismatch')
        directory = a.FEATURES.parent/('HTT-GNN-EVAL-FEATURES-'+split+'-v1')
        with (directory/'query_index.csv').open() as handle:
            a.require([q['query_id'] for q in csv.DictReader(handle)] == [q['query_id'] for q in truth], 'Evaluation feature ordering mismatch')
        candidates = [v['node_id'] for v in inputs['nodes'][:2824]]
        model,_ = load_checkpoint(a.RUN/'training/selected_model.pt')
        initial,_ = load_checkpoint(a.RUN/'training/untrained_model.pt')
        summaries,boots = {},{}
        methods = ['tfidf','minilm','context_pooling','untrained_graphsage','trained_graphsage']
        for method in methods:
            started = time.perf_counter()
            if method == 'tfidf':
                from sklearn.feature_extraction.text import TfidfVectorizer
                params = a.authorize('training')['baselines']['tfidf']
                vectorizer = TfidfVectorizer(ngram_range=tuple(params['ngram_range']),min_df=params['min_df'],sublinear_tf=params['sublinear_tf'],norm=params['norm'])
                training_ids = set(inputs['candidate_ids'])
                fit_text = [v['feature_text'] for v in inputs['nodes'][:2824] if v['node_id'] in training_ids]+[q['query_text'] for q in inputs['queries']]
                vectorizer.fit(fit_text)
                cv = vectorizer.transform([v['feature_text'] for v in inputs['nodes'][:2824]])
                qv = vectorizer.transform([q['query_text'] for q in projected])
                import joblib
                with (stage/'tfidf_vectorizer.joblib').open('xb') as handle:
                    joblib.dump(vectorizer,handle)
                a.save_json(stage/'tfidf_fit_provenance.json',{'training_trials':len(training_ids),'training_queries':len(inputs['queries']),
                    'fit_text_sha256':a.object_sha(fit_text),'vocabulary_size':len(vectorizer.vocabulary_),'heldout_fit':False})
            elif method == 'minilm':
                qv,cv = query_features,context[:2824,:384].numpy()
            elif method == 'context_pooling':
                from .model import mean_aggregate
                semantic = context[:,:384]
                neighbors = mean_aggregate(semantic,edges)
                cv = F.normalize((semantic+neighbors)*0.5,dim=1)[:2824].numpy()
                qv = query_features
            else:
                chosen = initial if method == 'untrained_graphsage' else model
                with torch.inference_mode():
                    cv = chosen.trials(context,edges).numpy()
                    qv = chosen.queries(torch.from_numpy(query_features)).numpy()
            prep = time.perf_counter()-started
            records,summary = r.evaluate_vectors(qv,cv,truth,candidates,method)
            aggregate,boot = r.macro_and_uncertainty(records,split_rows)
            summary.update(aggregate)
            summary['one_time_representation_preparation_seconds'] = prep
            summaries[method],boots[method] = summary,boot
            with (stage/(method+'_rankings.jsonl')).open('x') as handle:
                for record in records:
                    handle.write(a.canonical(record)+'\n')
            print(json.dumps({'event':'evaluation','split':split,'method':method,'query_micro':summary['query_micro']}),flush=True)
        for method in methods[:-1]:
            a.require(boots[method][0] == boots['trained_graphsage'][0], 'Bootstrap families differ across methods')
            delta = boots['trained_graphsage'][1]-boots[method][1]
            summaries[method]['paired_trained_minus_baseline_family_MRR_95CI'] = np.percentile(delta,[2.5,97.5]).tolist()
        tokenization = json.loads((directory/'tokenization_audit.json').read_text())
        results = {'schema_version':'HTT-GNN-FORMAL-RANKING-v1','split':split,'formal_evaluation_status':'COMPLETE',
                   'scope':'Observed-graph registered-association ranking; not unseen-trial induction or clinical prediction',
                   'candidate_count':2824,'eligible_queries':len(truth),'queries_before_embargo':{'validation':2651,'test':2652}[split],
                   'methods':summaries,'selected_epoch':selection['selected_epoch'],'query_encoding':tokenization,
                   'model_selection_using_this_evaluation':False,'checkpoint_sha256':selection['checkpoint_sha256'],'environment':environment()}
        a.save_json(stage/'results.json',results)
        write_comparison_svg(stage/'ranking_comparison.svg',results)
        a.bundle_manifest(stage,{'schema_version':'HTT-GNN-EVALUATION-v1','split':split,'selection_sha256':a.sha(a.RUN/'training/selection.json'),
            'feature_manifest_sha256':a.sha(directory/'manifest.json'),'context_manifest_sha256':a.sha(a.FEATURES/'manifest.json'),
            'code_sha256':code_hashes(),'test_evaluations_in_this_bundle':int(split == 'test')})


def write_comparison_svg(path,results):
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="470"><rect width="1000" height="470" fill="white"/>',
           '<text x="30" y="35" font-family="sans-serif" font-size="23">Frozen 2,824-candidate association ranking — '+results['split']+'</text>']
    for i,(name,summary) in enumerate(results['methods'].items()):
        y = 70+i*65
        value = summary['query_micro']['MRR']
        svg.extend([f'<text x="20" y="{y+25}" font-family="sans-serif" font-size="17">{html.escape(name)}</text>',
                    f'<rect x="240" y="{y}" width="{value*620:.3f}" height="35" fill="#1865a3"/>',
                    f'<text x="{250+value*620:.3f}" y="{y+25}" font-size="18">MRR {value:.4f}</text>'])
    svg.append('<text x="30" y="440" font-size="16">Registered measures, not observed clinical results; no inductive or clinical claim.</text></svg>')
    with Path(path).open('x') as handle:
        handle.write('\n'.join(svg))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['train','evaluate-validation','evaluate-test'])
    parser.add_argument('--output',type=Path,help='New non-overwriting destination for training reproduction only')
    args = parser.parse_args()
    if args.operation == 'train':
        train(args.output or a.RUN/'training')
    else:
        a.require(args.output is None,'Evaluation destination is fixed to enforce a single test bundle')
        evaluation(args.operation.removeprefix('evaluate-'))


if __name__ == '__main__':
    main()
