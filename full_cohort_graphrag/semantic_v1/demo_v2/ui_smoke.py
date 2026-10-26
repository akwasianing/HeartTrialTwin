"""Explicit one-question live AppTest through the real subprocess backend."""
import argparse
import json
import urllib.request
from pathlib import Path

from streamlit.testing.v1 import AppTest
from ..identity import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; no calls made')
    with urllib.request.urlopen('http://127.0.0.1:8502/_stcore/health', timeout=5) as response:
        health = response.read(100).decode()
    assert health == 'ok', 'Streamlit health check failed'
    app = AppTest.from_file(str(ROOT / 'full_cohort_graphrag/semantic_v1/demo_v2/app.py'), default_timeout=240).run()
    app.selectbox[0].select('planned outcomes').run()
    app.button[0].click().run()
    assert not app.exception, 'Live UI exception'
    result = app.session_state['demo_result']
    assert result['status'] == 'COMPLETE_LISTING' and result['model_attempts'] == 0
    outcomes = result['trial_results'][0]['answer_trace']['listed_outcomes']
    assert len(outcomes) == len({r['evidence_id'] for r in outcomes}) == 7
    with args.output.open('x') as handle:
        json.dump({'streamlit_health': health, 'ui_exceptions': 0,
                   'execution': 'Actual AppTest UI -> existing Neo4j environment subprocess -> live read-only Neo4j',
                   'trace': result}, handle, sort_keys=True, indent=2, ensure_ascii=False)
    print(json.dumps({'status': result['status'], 'outcomes': len(outcomes), 'model_attempts': result['model_attempts'],
                      'client_elapsed_seconds': result['client_elapsed_seconds'], 'streamlit_health': health}))


if __name__ == '__main__':
    main()
