"""Build an explicit, review-only publication list; never stage or push files."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def selected():
    names={'README.md','.gitignore','vector_rag/requirements.txt','vector_rag/data/index_manifest.json'}
    for folder in ('cohort_scaling','full_cohort_graphrag','gnn_graphrag'):
        for path in (ROOT/folder).rglob('*'):
            if not path.is_file():continue
            rel=path.relative_to(ROOT).as_posix()
            if '__pycache__' in path.parts or '.incomplete-' in rel:continue
            if path.suffix=='.py' or path.suffix=='.md' or path.name.endswith('.env.example') or path.name=='.env.example':
                names.add(rel)
    graph=ROOT/'artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1'
    for name in ('full_cohort_manifest.json','VALIDATION_REPORT.md','COVERAGE_REPORT.md','source_coverage.csv','cohort_membership.csv','SHA256SUMS'):
        if (graph/name).is_file():names.add((graph/name).relative_to(ROOT).as_posix())
    for path in (ROOT/'gnn_graphrag').rglob('*.json'):
        rel=path.relative_to(ROOT).as_posix()
        if '.incomplete-' in rel:continue
        # Immutable metadata and measured summaries, not per-query truth or weights.
        if path.name in {'manifest.json','split_manifest.json','protocol.json','feature_policy.json','experiment_config.json','authorization.json','results.json','selection.json','history.json','diagnostic_report.json'}:
            names.add(rel)
    for path in (ROOT/'gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1').rglob('*.svg'):
        names.add(path.relative_to(ROOT).as_posix())
    for name in ('gnn_graphrag/protocols/HTT-GNN-ASSOC-PROTOCOL-v2/candidate_trials.csv',):
        if (ROOT/name).is_file():names.add(name)
    for folder in ('full_cohort_graphrag/semantic_v1/demo_v2/validation','full_cohort_graphrag/semantic_v1/live_validation'):
        for path in (ROOT/folder).rglob('*.json'):names.add(path.relative_to(ROOT).as_posix())
    audit=ROOT/'reports/final_project/STEP_66G_5_v1'
    for path in audit.rglob('*'):
        if path.is_file() and path.suffix in {'.md','.json','.py','.txt','.jpg','.png'}:names.add(path.relative_to(ROOT).as_posix())
    final=ROOT/'reports/final_project/CHALLENGE_3_FINAL'
    for path in final.iterdir():
        if path.is_file() and path.suffix in {'.md','.pdf','.docx','.pptx','.json'}:names.add(path.relative_to(ROOT).as_posix())
    for path in (final/'assets').rglob('*'):
        if path.is_file() and path.suffix in {'.png','.jpg','.svg'}:names.add(path.relative_to(ROOT).as_posix())
    for path in HERE.iterdir():
        if (path.is_file() and path.suffix in {'.py','.m','.md','.json','.txt'}
                and path.name not in {'scan_results.json','publication_files.json','publication_files.txt','publication_receipt.json'}
                and not path.name.startswith('targeted_checks_')):
            names.add(path.relative_to(ROOT).as_posix())
    return sorted(names)


def main():
    files=[]
    for name in selected():
        path=ROOT/name
        assert not path.is_symlink()
        assert path.is_file()
        assert path.name=='.env.example' or not path.name.startswith('.env')
        assert path.suffix not in {'.npy','.pt','.pkl','.joblib','.parquet','.zip'}
        data=path.read_bytes()
        assert len(data)<10*1024*1024
        files.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    result={'status':'PROPOSED_NOT_STAGED_NOT_COMMITTED_NOT_PUSHED','files':files,
        'total_files':len(files),'total_bytes':sum(v['bytes'] for v in files),
        'excluded':['private .env/configuration','virtual environments and caches','raw AACT ZIP/source_cache','full graph CSV payloads (except membership)','full extraction CSV payloads','protocol labels/query payloads','MiniLM arrays and cached model weights','GraphSAGE checkpoints and fitted baseline weights','report build/render workspaces','unrelated course folders','unfinished Agentic/Vector RAG work'],
        'provisioning':'Pinned external research bundles and model cache are needed for complete runtime/tests; see README.'}
    (HERE/'publication_files.json').write_text(json.dumps(result,indent=2)+'\n')
    (HERE/'publication_files.txt').write_text('\n'.join(v['path'] for v in files)+'\n')
    print(json.dumps({'files':len(files),'bytes':result['total_bytes'],'output':str(HERE/'publication_files.json')}))


if __name__=='__main__':main()
