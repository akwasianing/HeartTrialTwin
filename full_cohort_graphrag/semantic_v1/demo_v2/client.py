"""Stdlib boundary between installed Streamlit and Neo4j environments."""
import json
import os
import subprocess
import time

from ..identity import ROOT

DEMO_WALL_TIMEOUT = 240


def run_question(question, *, candidate_count=2, scan_limit=5, answer_mode='deterministic', runner=None):
    started = time.perf_counter()
    request = dict(question=question, candidate_count=candidate_count, scan_limit=scan_limit, answer_mode=answer_mode)
    allowed = {'HOME', 'PATH', 'LANG', 'LC_ALL', 'TMPDIR', 'HF_HOME', 'HF_HUB_CACHE', 'TRANSFORMERS_CACHE'}
    env = {k: v for k, v in os.environ.items() if k in allowed or k in {
        'FULL_GRAPHRAG_NEO4J_URI', 'FULL_GRAPHRAG_NEO4J_USERNAME',
        'FULL_GRAPHRAG_NEO4J_PASSWORD', 'FULL_GRAPHRAG_NEO4J_DATABASE'}}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    try:
        response = (runner or subprocess.run)(
            [str(ROOT / '.venv-graphrag/bin/python'), '-B', '-m',
             'full_cohort_graphrag.semantic_v1.demo_v2.worker'],
            input=json.dumps(request), capture_output=True, text=True, cwd=ROOT, env=env,
            timeout=DEMO_WALL_TIMEOUT, check=False)
        if response.returncode != 0 or len(response.stdout.encode()) > 10_000_000:
            raise ValueError('Backend unavailable or response too large')
        result = json.loads(response.stdout)
        if not isinstance(result, dict) or not isinstance(result.get('answer'), str) or 'status' not in result:
            raise ValueError('Invalid result')
    except subprocess.TimeoutExpired:
        result = {'status': 'ABSTAIN', 'answer': 'ABSTAIN: The demonstration exceeded its 240-second overall limit. '
                  'No unsupported answer or automatic retry was produced.', 'errors': ['DEMO_WALL_TIMEOUT']}
    except Exception:
        result = {'status': 'ABSTAIN', 'answer': 'ABSTAIN: The local backend failed safely. Check the documented '
                  'environments, read-only Neo4j configuration and service availability.', 'errors': ['BACKEND_FAILURE']}
    result['client_elapsed_seconds'] = round(time.perf_counter() - started, 6)
    result['question'] = question
    return result
