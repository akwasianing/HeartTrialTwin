"""Association-ranking math: masked GraphSAGE, multi-positive loss and metrics."""
from __future__ import annotations

from collections import defaultdict
import time

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from . import full_cohort_access as a
from .model import TwoLayerGraphSAGE


class AssociationRanker(nn.Module):
    def __init__(self):
        super().__init__()
        self.graph = TwoLayerGraphSAGE(390,128,64)
        self.query = nn.Linear(384,64)

    def trials(self,context,edges):
        return F.normalize(self.graph(context,edges).layer2[:2824],dim=1)

    def queries(self,query_vectors):
        return F.normalize(self.query(query_vectors),dim=1)


def prepare_labels(inputs):
    ids = inputs['candidate_ids']
    position = {n:i for i,n in enumerate(ids)}
    families = {r['nct_id']:r['family_id'] for r in inputs['families']}
    members = defaultdict(set)
    for n,family in families.items():
        members[family].add(n)
    width = max(len(q['positive_trial_ids']) for q in inputs['queries'])
    positives = np.full((len(inputs['queries']),width),-1,dtype=np.int64)
    pools = []
    universe = set(ids)
    for i,q in enumerate(inputs['queries']):
        known = set(q['positive_trial_ids'])
        excluded = known | set(q['ambiguous_trial_ids'])
        for n in known:
            excluded |= members[families[n]]
        a.require(excluded <= universe and known, 'Invalid training-only labels')
        positives[i,:len(known)] = [position[n] for n in sorted(known)]
        pool = np.array([position[n] for n in ids if n not in excluded],dtype=np.int32)
        a.require(len(pool) >= 64, 'Insufficient eligible training negatives')
        pools.append(pool)
    return positives,pools


def sample_negatives(pools,seed,count=64):
    rng = np.random.default_rng(seed)
    a.require(count > 0 and all(len(pool) >= count for pool in pools), 'Insufficient negative pool')
    return np.stack([rng.choice(pool,count,replace=False) for pool in pools]).astype(np.int64)


def multi_positive_loss(scores,positive_indices,negative_indices,temperature):
    a.require(temperature > 0 and positive_indices.shape[0] == scores.shape[0] == negative_indices.shape[0], 'Invalid loss inputs')
    positive_scores = scores.gather(1,positive_indices.clamp(min=0))/temperature
    positive_scores = positive_scores.masked_fill(positive_indices < 0,float('-inf'))
    negative_scores = scores.gather(1,negative_indices)/temperature
    a.require(bool((positive_indices >= 0).any(1).all()), 'Every query must retain a positive')
    return (torch.logsumexp(torch.cat((positive_scores,negative_scores),1),1)-torch.logsumexp(positive_scores,1)).mean()


def rank_metrics(positive_ranks):
    ranks = np.asarray(positive_ranks,dtype=np.int64)
    a.require(len(ranks) > 0 and (ranks >= 1).all(), 'Invalid positive ranks')
    result = {'MRR':float(1/ranks.min())}
    for k in (1,5,10):
        hits = int((ranks <= k).sum())
        result['Recall@'+str(k)] = hits/len(ranks)
        result['Hit@'+str(k)] = float(hits > 0)
    return result


def validation_mrr(query_vectors,trial_vectors,truth,candidate_ids):
    position = {n:i for i,n in enumerate(candidate_ids)}
    values = []
    for start in range(0,len(truth),128):
        scores = query_vectors[start:start+128] @ trial_vectors.T
        a.require(np.isfinite(scores).all(), 'Nonfinite validation scores')
        for row,q in zip(scores,truth[start:start+128]):
            pos = np.array([position[n] for n in q['owner_trial_ids']])
            best_score = row[pos].max()
            best_index = min(i for i in pos if row[i] == best_score)
            rank = int((row > best_score).sum() + ((row == best_score) & (np.arange(len(row)) < best_index)).sum())+1
            values.append(1/rank)
    return float(np.mean(values))


def evaluate_vectors(queries,candidates,truth,candidate_ids,method):
    """Exact fixed-universe ranking. Latencies are actual per-query measurements."""
    position = {n:i for i,n in enumerate(candidate_ids)}
    a.require(candidate_ids == sorted(set(candidate_ids)) and len(candidate_ids) == 2824, 'Wrong candidate universe')
    def row_norms(values):
        if hasattr(values,'multiply'):
            return np.sqrt(np.asarray(values.multiply(values).sum(axis=1)).ravel())
        return np.linalg.norm(values,axis=1)
    query_norms,candidate_norms = row_norms(queries),row_norms(candidates)
    records,score_times,rank_times = [],[],[]
    for i,q in enumerate(truth):
        started = time.perf_counter()
        product = queries[i:i+1] @ candidates.T
        scores = product.toarray().ravel() if hasattr(product,'toarray') else np.asarray(product).ravel()
        score_times.append(time.perf_counter()-started)
        a.require(scores.shape == (2824,) and np.isfinite(scores).all(), 'Invalid evaluation scores')
        started = time.perf_counter()
        ordering = np.argsort(-scores,kind='stable')
        inverse = np.empty(len(ordering),dtype=np.int64)
        inverse[ordering] = np.arange(1,len(ordering)+1)
        ranks = [int(inverse[position[n]]) for n in q['owner_trial_ids']]
        metrics = rank_metrics(ranks)
        rank_times.append(time.perf_counter()-started)
        records.append({'query_id':q['query_id'],'positive_trial_ids':q['owner_trial_ids'],'positive_ranks':ranks,'query_vector_norm':float(query_norms[i]),
                        'metrics':metrics,'top10':[{'nct_id':candidate_ids[j],'score':float(scores[j])} for j in ordering[:10]],
                        'source_evidence_ids':[r['evidence_id'] for r in q['source_associations']]})
    latency = {}
    for label,times in [('scoring',score_times),('ranking',rank_times),('scoring_plus_ranking',np.array(score_times)+rank_times)]:
        latency[label] = {'median_seconds':float(np.median(times)),'p95_seconds':float(np.percentile(times,95)),'total_seconds':float(np.sum(times))}
    return records,{'method':method,'candidate_count':2824,'queries_scored':len(records),'coverage':len(records)/len(truth),
                    'nonzero_query_vectors':int((query_norms > 0).sum()),'nonzero_candidate_vectors':int((candidate_norms > 0).sum()),
                    'informative_query_coverage':float(np.mean(query_norms > 0)),'zero_vector_policy':'rank_all_candidates_with_the_same_NCT_tie_break; not silently omitted',
                    'query_micro':{key:float(np.mean([r['metrics'][key] for r in records])) for key in records[0]['metrics']},'latency':latency}


def macro_and_uncertainty(records,split_rows):
    family = {r['nct_id']:r['family_id'] for r in split_rows}
    by_trial = defaultdict(list)
    for row in records:
        for nct in row['positive_trial_ids']:
            by_trial[nct].append(row['metrics'])
    keys = list(records[0]['metrics'])
    trial_values = {n:{k:float(np.mean([m[k] for m in values])) for k in keys} for n,values in by_trial.items()}
    by_family = defaultdict(list)
    for n,metrics in trial_values.items():
        by_family[family[n]].append(metrics)
    family_values = {fid:{k:float(np.mean([m[k] for m in values])) for k in keys} for fid,values in sorted(by_family.items())}
    family_ids = sorted(family_values)
    values = np.array([family_values[f]['MRR'] for f in family_ids])
    rng = np.random.default_rng(20261023)
    draws = rng.integers(0,len(values),size=(1000,len(values)))
    boot = values[draws].mean(1)
    strata = {}
    for name,subset in [('single_owner',[r for r in records if len(r['positive_trial_ids']) == 1]),
                        ('multi_owner',[r for r in records if len(r['positive_trial_ids']) > 1])]:
        strata[name] = {'queries':len(subset),'MRR':float(np.mean([r['metrics']['MRR'] for r in subset])) if subset else None}
    return {'owner_trial_macro':{k:float(np.mean([v[k] for v in trial_values.values()])) for k in keys},
            'family_macro':{k:float(np.mean([v[k] for v in family_values.values()])) for k in keys},
            'represented_trials':len(trial_values),'represented_families':len(family_ids),'owner_strata':strata,
            'family_macro_MRR_bootstrap_95CI':np.percentile(boot,[2.5,97.5]).tolist()},(family_ids,boot)
