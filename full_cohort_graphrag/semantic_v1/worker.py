"""Bounded JSON stdin/stdout worker, run in the existing MiniLM environment."""
import json
import sys
import os
import time
import hashlib

# Configure BLAS before NumPy is imported, including validate-only operations.
for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key] = '1'
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')

from .identity import check_text, check_k, require, normalize_query


def execute(request):
    from .ranking import MiniLMRanker, LocalQueryEncoder
    require(isinstance(request,dict), 'Worker object required')
    operation = request.get('operation')
    require(operation in ('validate','rank') and set(request) ==
            ({'operation'} if operation == 'validate' else {'operation','query_text','top_k'}), 'Invalid worker contract')
    ranker = MiniLMRanker()
    if operation == 'validate':
        # Existing vector only: no model load, no new text or corpus embedding.
        result = ranker.rank_vector(ranker.vectors[0],1)
        result['validation_only'] = True
        return result
    check_text(request['query_text'])
    check_k(request['top_k'])
    started = time.perf_counter()
    encoder = LocalQueryEncoder(ranker.encoder_spec)
    text = normalize_query(request['query_text'])
    result = ranker.rank_vector(encoder.encode(text),request['top_k'])
    result['query_encoding'] = {'normalization':'NFKC_casefold_whitespace',
        'text_sha256':hashlib.sha256(text.encode()).hexdigest(),
        'token_count':len(encoder.tokenizer.encode(text).ids),
        'model_load_encode_rank_seconds':time.perf_counter()-started}
    return result


def main():
    try:
        raw = sys.stdin.buffer.read(16001)
        require(len(raw) <= 16000, 'Worker input budget exceeded')
        result = execute(json.loads(raw))
    except Exception:
        # No raw cache paths, credentials, remote errors or prompts in errors.
        result = {'status':'ERROR','error':'MiniLM worker failed input, cache, dependency or artifact checks'}
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return 0 if result['status'] == 'OK' else 1


if __name__ == '__main__':
    raise SystemExit(main())
