"""Four sequential read-only checks; no Ollama generation or benchmark evaluation.

Explicit execution only. Writes exclusively to a new versioned report directory.
"""
import argparse
import json
import signal
from pathlib import Path

from full_cohort_graphrag.src import retrieve as api
from ..identity import ROOT, require
from ..live_validation_v1 import probe, audit, write
from .engine import Demonstration

CASES = (
    ('01_sponsor', 'Who is the lead sponsor of NCT00206232?', 'GROUNDED'),
    ('02_intervention', 'What intervention is registered for clinical trial NCT00206232?', 'GROUNDED'),
    ('03_outcomes', 'What planned outcomes were registered for NCT00206232?', 'COMPLETE_LISTING'),
    ('04_discovery', 'Find trials with registered planned outcomes about quality of life.', 'GROUNDED_CANDIDATE_EVIDENCE'),
)


def preserve():
    """Check recorded file hashes without opening association test truth."""
    checks = []
    old = json.loads((ROOT / 'gnn_graphrag/diagnostics/HTT-GNN-DIAG-66G1-v1/diagnostic_plan.json').read_text())['protected_files_before']
    checks.append(('research', ROOT, old))
    base = ROOT / 'full_cohort_graphrag/semantic_v1'
    checks.append(('existing_semantic', base, json.loads((base / 'results/validation_manifest.json').read_text())['files_sha256']))
    live = base / 'live_validation/HTT-MINILM-GRAPHRAG-LIVE-v1'
    checks.append(('existing_live', live, json.loads((live / 'finalization_manifest.json').read_text())['files_sha256']))
    results = {}
    for name, parent, files in checks:
        require(all(api.sha256(parent / path) == checksum for path, checksum in files.items()),
                'Protected artifact checksum mismatch')
        results[name + '_files_unchanged'] = len(files)
    return results


def deadline(*_):
    raise TimeoutError('Smoke case deadline')


def run(destination):
    destination.mkdir(parents=True, exist_ok=False)
    write(destination / 'plan.json', {'version': 'HTT-DEMO-v2-SMOKE-v1', 'cases': CASES,
          'candidate_count': 2, 'scan_limit': 5, 'model_generation_requests': 0,
          'attempts_per_case': 1, 'case_watchdog_seconds': 210, 'formal_benchmark': False,
          'authorization': 'Project-owner Step 66G-4, bounded live read-only smoke test'})
    before = preserve()
    services = probe()  # Existing identity/privilege checks and Ollama tags only.
    write(destination / 'services.json', services)
    summary = {'services': {'neo4j_read_only_verified': services['neo4j'].get('read_only_verified', False),
                           'ollama_installed': services['ollama'].get('model_installed', False)},
               'cases': [], 'preservation_before': before, 'model_generation_requests': 0}
    if not services['neo4j'].get('connected') or not services['neo4j'].get('read_only_verified'):
        summary['blocked'] = 'Live Neo4j identity/read-only verification failed; no question retrieval attempted.'
        write(destination / 'summary.json', summary)
        print(json.dumps(summary))
        return 2
    with api.FullCohortRetriever(api.load_config()) as retriever:
        for name, question, expected in CASES:
            previous = signal.signal(signal.SIGALRM, deadline)
            signal.alarm(210)
            try:
                trace = Demonstration(retriever).run(question)
                checked = audit(trace, retriever.contract)
                trace['independent_audit'] = checked
                require(trace['model_attempts'] == 0, 'Unexpected generation')
                passed = trace['status'] == expected and checked['citation_validity'] == 'PASS'
                if name == '03_outcomes':
                    require(len(trace['trial_results'][0]['answer_trace']['listed_outcomes']) == 7, 'Unexpected outcome set')
                write(destination / (name + '.json'), trace)
                row = {'case': name, 'result': 'PASS' if passed else 'FAIL', 'status': trace['status'],
                       'elapsed_seconds': trace['elapsed_seconds'], 'selected_nct_ids': trace['selected_nct_ids'],
                       'evidence_counts': {r['nct_id']: r['prepared_evidence']['evidence_record_count'] for r in trace['trial_results']},
                       'skipped_candidates': trace['skipped_candidates'], 'checked_facts': checked['checked_fact_count']}
                summary['cases'].append(row)
                print(json.dumps(row), flush=True)
                if not passed:
                    break  # No repair/retry or unbounded live testing.
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, previous)
    summary['preservation_after'] = preserve()
    # Check actual private credential strings in memory, never print them.
    config = api.load_config()
    content = '\n'.join(path.read_text() for path in destination.glob('*.json'))
    require(config.password not in content, 'Credential protection check failed')
    write(destination / 'summary.json', summary)
    write(destination / 'manifest.json', {'files_sha256': {p.name: api.sha256(p) for p in sorted(destination.glob('*.json'))}})
    return 0 if len(summary['cases']) == 4 and all(v['result'] == 'PASS' for v in summary['cases']) else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New directory; never overwritten')
    args = parser.parse_args()
    raise SystemExit(run(args.output))
