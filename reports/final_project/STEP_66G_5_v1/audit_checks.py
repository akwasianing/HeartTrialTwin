"""Read-only evidence audit. No training, encoding, database or model service calls.

Results/logs are exclusive new files in this documentation package. Hashing
frozen truth files checks preservation only; their labels are not parsed.
"""
import argparse
import ast
import hashlib
import importlib.metadata
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def read(path):
    return json.loads(path.read_text())


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def verify_map(parent, files):
    for name, expected in files.items():
        path = parent / name
        assert path.resolve().is_relative_to(parent.resolve()), 'Unsafe manifest path'
        assert sha(path) == expected, 'Checksum mismatch: ' + name
    return len(files)


def security_inventory():
    """Never emit credential values, matching text, or private environment content."""
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    names = sorted(set(n for n in names if n and not n.startswith('week ')))
    secrets = set()
    for name in ('full_cohort_graphrag/.env', 'graphrag/.env', 'artifacts/knowledge_graph/.env',
                 'agentic_graphrag/.env', 'cohort_scaling/.env'):
        path = ROOT / name
        if path.exists():
            for line in path.read_text().splitlines():
                if '=' in line and not line.lstrip().startswith('#'):
                    key, value = line.split('=', 1)
                    value = value.strip().strip('"\'')
                    if any(t in key.upper() for t in ('PASSWORD', 'API_KEY', 'TOKEN')) and len(value) >= 8:
                        secrets.add(value)
    findings, oversized, skipped, examples = [], [], [], []
    for name in names:
        path = ROOT / name
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size > 50 * 1024 * 1024:
            oversized.append({'path': name, 'bytes': size})
        if path.suffix not in {'.py', '.md', '.json', '.jsonl', '.txt', '.toml', '.yaml', '.yml', '.ipynb', '.mjs', '.sh', '.example'}:
            continue
        if size > 5 * 1024 * 1024:
            skipped.append({'path': name, 'reason': 'Text exceeds bounded 5 MiB credential scan'})
            continue
        text = path.read_text(errors='replace')
        if secrets and any(value in text for value in secrets):
            findings.append({'path': name, 'kind': 'KNOWN_PRIVATE_SECRET_MATCH', 'value': 'REDACTED'})
        if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bsk-(?:proj-)?[A-Za-z0-9_-]{25,}', text):
            findings.append({'path': name, 'kind': 'POTENTIAL_KEY_PATTERN', 'value': 'REDACTED'})
        if path.name == '.env.example':
            examples.append(name)
            for i, line in enumerate(text.splitlines(), 1):
                if re.match(r'\w*(?:PASSWORD|API_KEY|TOKEN)\s*=', line):
                    value = line.split('=', 1)[1].strip().strip('"\'')
                    if (value and not value.startswith('<')
                            and not value.casefold().startswith(('your_', 'your-', 'replace_', 'optional_'))
                            and value.casefold() not in {'changeme', 'replace_me'}):
                        findings.append({'path': name, 'line': i, 'kind': 'REVIEW_EXAMPLE_SECRET_ASSIGNMENT', 'value': 'REDACTED'})
    return {'scope': 'Tracked and nonignored untracked text <=5 MiB, excluding course week folders; exact known private passwords/API keys and limited key patterns',
            'files_considered': len(names), 'findings': findings, 'example_files': examples,
            'large_files': oversized, 'text_scan_exclusions': skipped,
            'limitation': 'Not an exhaustive secret/history/binary scan. Do not publish unreviewed untracked directories.'}


def collect():
    from full_cohort_graphrag.semantic_v1.demo_v2.smoke import preserve
    graph = ROOT / 'artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1'
    proto = ROOT / 'gnn_graphrag/protocols/HTT-GNN-ASSOC-PROTOCOL-v2'
    feature = ROOT / 'gnn_graphrag/feature_artifacts/HTT-GNN-ASSOC-FEATURES-v1'
    run = ROOT / 'gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1'
    assert sha(graph / 'full_cohort_manifest.json') == '3ef82624d131b36abc1eb9ad4e89b3439fed9f9600b92262c21bbcbfe6cf8757'
    assert sha(proto / 'split_manifest.json') == 'b13d662390b687b62a08cc1fb81bd3413f2c9d1fbb3b6ec86438b1a6854cd95b'
    assert sha(feature / 'manifest.json') == 'e2f167b01b2e83aef1f11ef6e4dba673d741246927a43f30936888beecf99a17'
    assert sha(run / 'training/selected_model.pt') == '58bac20f20d15349063ef36079d204714052b48bb4332c6622e68c43d0d7b936'
    g, p, f = read(graph / 'full_cohort_manifest.json'), read(proto / 'split_manifest.json'), read(feature / 'manifest.json')
    checks = {'graph_files': verify_map(graph, g['files_sha256']),
              'protocol_files': verify_map(proto, p['files_sha256']),
              'protocol_sources': verify_map(ROOT, p['source_sha256'])}
    for directory in (feature, feature.parent / 'HTT-GNN-EVAL-FEATURES-validation-v1',
                      feature.parent / 'HTT-GNN-EVAL-FEATURES-test-v1', run / 'training',
                      run / 'evaluation_validation', run / 'evaluation_test'):
        checks[str(directory.relative_to(ROOT))] = verify_map(directory, read(directory / 'manifest.json')['files_sha256'])
    assert p['training_permitted'] is False and p['status'] == 'PROVISIONAL_FAMILY_AUDIT_REVIEW_REQUIRED'
    assert f['context_shape'] == [9036, 390] and f['query_shape'] == [11712, 384]
    assert f['edge_count'] == 61218 and f['encoder']['max_seq_length'] == 256
    metrics = {}
    for split in ('validation', 'test'):
        saved = read(run / ('evaluation_' + split) / 'results.json')
        assert saved['candidate_count'] == 2824 and saved['selected_epoch'] == 60
        metrics[split] = {'eligible_queries': saved['eligible_queries'], 'queries_before_embargo': saved['queries_before_embargo'],
                         'methods': {name: {'query_micro': result['query_micro'], 'coverage': result['coverage'],
                            'family_macro_MRR_bootstrap_95CI': result['family_macro_MRR_bootstrap_95CI'],
                            'latency': result['latency']} for name, result in saved['methods'].items()}}
    compile_count = 0
    for directory in ('full_cohort_graphrag', 'gnn_graphrag/src', 'graphrag/src'):
        for path in (ROOT / directory).rglob('*.py'):
            ast.parse(path.read_text(), filename=str(path.relative_to(ROOT)))
            compile_count += 1
    return {'scope': 'Read-only saved-result reconciliation; no model inference or model selection',
            'preservation': preserve(), 'verified_hash_entries': checks, 'python_syntax_files': compile_count,
            'graph_counts': g['validation'], 'source_coverage': {k: {a: v[a] for a in ('cohort_rows', 'cohort_nct_coverage')}
                for k, v in g['archive']['tables'].items()},
            'protocol': {'manifest_sha256': sha(proto / 'split_manifest.json'), 'status': p['status'],
                         'training_permitted': p['training_permitted'], 'counts': p['actual_counts']},
            'features': {key: f[key] for key in ('context_shape', 'query_shape', 'edge_count', 'encoder')},
            'checkpoint_sha256': sha(run / 'training/selected_model.pt'), 'saved_benchmark_metrics': metrics,
            'security': security_inventory()}


TESTS = (
    ('full_cohort', '.venv-graphrag/bin/python', ['-m', 'unittest', 'discover', '-s', 'full_cohort_graphrag/tests', '-p', 'test_*.py', '-q']),
    ('integration_demo', '.venv-graphrag/bin/python', ['-m', 'unittest', 'full_cohort_graphrag.semantic_v1.test_pipeline', 'full_cohort_graphrag.semantic_v1.demo_v2.test_demo', '-q']),
    ('streamlit_ui', '.venv-full-system/bin/python', ['-m', 'unittest', 'full_cohort_graphrag.semantic_v1.demo_v2.test_app', '-q']),
    ('ranking_gnn', '.venv-vector-rag/bin/python', ['-m', 'unittest', 'full_cohort_graphrag.semantic_v1.test_ranking', 'gnn_graphrag.tests.test_full_cohort_diagnosis', 'gnn_graphrag.tests.test_full_cohort_execution', '-q']),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-tests', action='store_true')
    parser.add_argument('--output', type=Path, required=True, help='New JSON path; log destinations must also be new')
    args = parser.parse_args()
    assert not args.output.exists(), 'Refusing to overwrite audit record'
    started = time.perf_counter()
    result = collect()
    if args.run_tests:
        result['regression_runs'] = []
        for label, interpreter, options in TESTS:
            command = [str(ROOT / interpreter), '-B', *options]
            run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=150, check=False)
            log = args.output.parent / (label + '_tests.txt')
            with log.open('x') as handle:
                handle.write(run.stdout + run.stderr)
            match = re.search(r'Ran (\d+) tests? in', run.stdout + run.stderr)
            result['regression_runs'].append({'suite': label, 'exit_code': run.returncode,
                'tests_run': int(match[1]) if match else None, 'log': log.name})
            print(json.dumps(result['regression_runs'][-1]), flush=True)
        assert all(r['exit_code'] == 0 for r in result['regression_runs']), 'Regression failure; inspect safe offline logs'
    result['elapsed_seconds'] = time.perf_counter() - started
    with args.output.open('x') as handle:
        json.dump(result, handle, sort_keys=True, indent=2, ensure_ascii=False)
    print(json.dumps({'output': str(args.output.resolve().relative_to(ROOT)), 'security_findings': result['security']['findings'],
                      'preservation': result['preservation']}))


if __name__ == '__main__':
    main()
