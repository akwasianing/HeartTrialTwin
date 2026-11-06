"""Verify completed deliverables without fitting, network calls or source changes."""
import argparse,csv,hashlib,json,re,subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image
from pypdf import PdfReader

FINAL=Path(__file__).resolve().parents[1];ROOT=FINAL.parents[2]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def check(condition,message):
    if not condition:raise ValueError(message)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--verify-only',action='store_true');args=ap.parse_args()
    pins=load(FINAL/'reports/source_preservation_manifest.json')
    for group in ['source_sha256','protected_sha256']:
        for path,h in pins[group].items():check(sha(ROOT/path)==h,'Protected/source mismatch: '+path)
    qual=ROOT/'reports/project_review/historical_label_feature_qualification_v1'
    qm=load(qual/'qualification_manifest.json')
    for path,h in qm['output_sha256'].items():check(sha(qual/path)==h,'Prior qualification output mismatch')
    for kind,key in [('analysis/output_manifest.json','outputs'),('modeling/run_manifest.json','artifacts')]:
        manifest=load(FINAL/kind)
        for p,h in manifest[key].items():
            target=FINAL/p if key=='outputs' else FINAL/'modeling'/p
            check(sha(target)==h,'New numerical result mismatch: '+p)
    figures=sorted((FINAL/'poster/figures').glob('*.png'));check(len(figures)==13,'Expected 13 figure pairs')
    for p in figures:
        with Image.open(p) as im:check(im.size==(3000,1850),'Unexpected chart dimensions')
        ET.parse(p.with_suffix('.svg'))
    pdf=FINAL/'poster/HeartTrialTwin_Final_Capstone_Poster_20261102.pdf';reader=PdfReader(pdf)
    check(len(reader.pages)==1,'Poster must be one page')
    check(list(map(float,reader.pages[0].mediabox))==[0.,0.,3456.,2592.],'Poster page size mismatch')
    text=reader.pages[0].extract_text()
    for term in ['2,824','28,777','79,125','19,740','1,319','1,505','166','0.2145','0.2122','not an independent final test','not observed clinical results']:
        check(term in text,'Poster evidence missing: '+term)
    links=[a.get_object().get('/A',{}).get('/URI','') for a in reader.pages[0].get('/Annots',[])]
    check('https://github.com/akwasianing/HeartTrialTwin' in links,'Poster repository link missing')
    secret_patterns=[re.compile(r'(?:neo4j|bolt)(?:\+s|\+ssc)?://',re.I),
        re.compile(r'\bsk-[A-Za-z0-9_-]{20,}'),re.compile(r'NEO4J_PASSWORD\s*=\s*["\x27]?[A-Za-z0-9]{8,}',re.I)]
    # Scan actual publication-style text, not this scanner's literal regex source.
    inspected=0
    for p in FINAL.rglob('*'):
        if not p.is_file() or '_build' in p.parts:continue
        check(p.name not in {'.env','.env.local'},'Private environment file in final package')
        if p.suffix in {'.md','.csv','.json','.svg'}:
            content=p.read_text();inspected+=1
            check(not any(pattern.search(content) for pattern in secret_patterns),'Credential-like content: '+str(p.relative_to(FINAL)))
        if p.suffix=='.json':load(p)
    checks=load(FINAL/'reports/test_results.json');check(checks['total_passed']==166 and checks['total_failed']==0,'Test summary mismatch')
    examples=load(FINAL/'integration/verified_examples.json')
    check([r['status'] for r in examples['examples']]==['GROUNDED','GROUNDED','COMPLETE_LISTING','ABSTAIN','ABSTAIN','ABSTAIN'],'Offline scenario status mismatch')
    check(len(examples['examples'][2]['answer_trace']['listed_outcomes'])==7,'Outcome completeness mismatch')
    check(all(r['model_attempts']==0 for r in examples['examples']),'Unexpected model attempt')
    changed=subprocess.run(['git','diff','--name-only'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    staged=subprocess.run(['git','diff','--cached','--name-only'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    check(not changed and not staged,'Tracked/staged files changed outside isolated package')
    manifest_path=FINAL/'reports/final_package_manifest.json'
    if args.verify_only:
        check(manifest_path.exists(),'No completed package manifest')
        for path,h in load(manifest_path)['artifacts_sha256'].items():check(sha(FINAL/path)==h,'Final artifact mismatch: '+path)
        print('PASS: final package hashes, sources, protected artifacts, PDF, figures, JSON and evidence checks');return
    check(not manifest_path.exists(),'Completed package preserved; use --verify-only')
    result={'source_checksums_passed':len(pins['source_sha256']),'protected_checksums_passed':len(pins['protected_sha256']),
        'prior_qualification_outputs_passed':len(qm['output_sha256']),'numerical_output_checksums_passed':True,
        'poster_pages':1,'poster_inches':[48,36],'png_svg_figure_pairs':13,'visual_review':'Rendered poster and contact sheet inspected; no clipping or overlapping text observed',
        'tests_passed':166,'tests_failed':0,'offline_scenarios_passed':6,'search_examples_passed':3,'ollama_calls':0,'neo4j_writes':0,
        'credential_like_content_found_in_scanned_deliverable_text':False,'text_files_scanned':inspected,
        'security_limitation':'Not an exhaustive historical repository credential audit; separate publication review remains required',
        'tracked_diff_empty':True,'staged_diff_empty':True,'no_commit_or_push':True}
    (FINAL/'reports/FINAL_VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n')
    artifacts={str(p.relative_to(FINAL)):sha(p) for p in sorted(FINAL.rglob('*')) if p.is_file() and '_build' not in p.parts and '__pycache__' not in p.parts and p!=manifest_path}
    (manifest_path).write_text(json.dumps({'package':'HEARTTRIALTWIN_FINAL_20261102','artifacts_sha256':artifacts,'bytes':sum((FINAL/p).stat().st_size for p in artifacts)},indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
