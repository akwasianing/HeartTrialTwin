"""Stdlib-only subprocess boundary; no dependency installation or ABI mixing."""
import json
import math
import os
import subprocess

from .identity import (ROOT, MODEL, REVISION, FEATURE_SHA, PROTOCOL_SHA, VERSION,
                       DATASET, GRAPH, SNAPSHOT, require, check_k, check_text)


def validate_ranking(result, top_k, membership):
    require(isinstance(result,dict) and result.get('status') == 'OK', 'MiniLM ranking unavailable')
    p = result.get('provenance',{})
    require(p.get('version') == VERSION and p.get('revision') == REVISION and p.get('model') == MODEL
            and p.get('dataset_version') == DATASET and p.get('graph_version') == GRAPH and p.get('snapshot_date') == SNAPSHOT
            and p.get('feature_manifest_sha256') == FEATURE_SHA and p.get('protocol_sha256') == PROTOCOL_SHA
            and p.get('dimensions') == 384 and p.get('candidate_count') == 2824
            and p.get('association_labels_used') is False, 'Ranking provenance mismatch')
    rows = result.get('ranked_trials')
    require(isinstance(rows,list) and len(rows) == top_k, 'Ranking length mismatch')
    ids = []
    for i,row in enumerate(rows):
        require(isinstance(row,dict) and set(row) == {'rank','nct_id','similarity','candidate_index'}, 'Unexpected ranking fields')
        require(type(row['rank']) is int and row['rank'] == i+1 and row['nct_id'] in membership
                and type(row['candidate_index']) is int and 0 <= row['candidate_index'] < 2824
                and row['nct_id'] == sorted(membership)[row['candidate_index']], 'Ranked trial mapping mismatch')
        require(type(row['similarity']) in (int,float) and math.isfinite(row['similarity'])
                and -1 <= row['similarity'] <= 1, 'Invalid similarity')
        ids.append(row['nct_id'])
    require(len(set(ids)) == len(ids) and rows == sorted(rows,key=lambda v:(-v['similarity'],v['nct_id'])), 'Invalid ranking order/duplicates')
    return result


class RankingWorker:
    def __init__(self, *, runner=subprocess.run):
        self.runner = runner

    def call(self, request):
        # Child never receives Neo4j passwords or unrelated project environment.
        allow = {'HOME','PATH','LANG','LC_ALL','HF_HOME','HF_HUB_CACHE','TRANSFORMERS_CACHE','TMPDIR'}
        env = {k:v for k,v in os.environ.items() if k in allow}
        env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1')
        try:
            response = self.runner([str(ROOT/'.venv-vector-rag/bin/python'),'-B','-m',
                'full_cohort_graphrag.semantic_v1.worker'],input=json.dumps(request),capture_output=True,
                text=True,cwd=ROOT,env=env,timeout=180,check=False)
            require(response.returncode == 0 and len(response.stdout.encode()) <= 100_000, 'MiniLM worker failed')
            return json.loads(response.stdout)
        except Exception:
            from .identity import SemanticError
            raise SemanticError('MiniLM worker unavailable, timed out, or failed integrity checks') from None

    def rank(self, text, top_k):
        check_text(text)
        check_k(top_k)
        return self.call({'operation':'rank','query_text':text,'top_k':top_k})
