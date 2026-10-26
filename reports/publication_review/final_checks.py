"""Targeted publication checks reusing completed OCR; never disclose values.

Run in the existing UI environment for its installed PyArrow. No model/database
calls, unpickling, split regeneration, staging, or network access occur here.
"""
import argparse
import hashlib
import io
import json
import re
import subprocess
from pathlib import Path
import pyarrow.parquet as pq

from prepare_selection import selected, ROOT, HERE
from scan_publication import Scanner, PATTERNS


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def inert_test_url(data):
    hits=list(re.finditer(PATTERNS['EMBEDDED_CREDENTIAL_URL'],data))
    return bool(hits) and (b'unittest' in data or b'def test_' in data) and all(
        hit.group().endswith(b'user:password@') and
        data[hit.end():hit.end()+10].startswith(b'localhost:') for hit in hits)


def check_data(scanner, data, name):
    before=len(scanner.findings)
    scanner.match(data,name,'raw_bytes_all_sizes')
    for finding in scanner.findings[before:]:
        if finding['types']==['EMBEDDED_CREDENTIAL_URL'] and inert_test_url(data):
            finding['disposition']='VERIFIED_INERT_REJECTION_TEST'
        else:
            finding['disposition']='BLOCK'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--staged',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise SystemExit('Refusing to overwrite a check record')
    broad=json.loads((HERE/'scan_results.json').read_text())
    old={r['path']:r for r in broad['working_files']}
    scanner=Scanner('NOT_USED_NO_OCR_REPEATED')
    refs=[r for r in git('for-each-ref','--format=%(refname)','refs/remotes/origin').decode().splitlines() if not r.endswith('/HEAD')]
    objects={}
    for line in git('rev-list','--objects',*refs).decode().splitlines():
        oid,*name=line.split(' ',1);objects[oid]=name[0] if name else ''
    # Only inspect published branch objects as bytes; previous OCR is retained.
    process=subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    published_blobs=0
    try:
        for oid,name in objects.items():
            process.stdin.write((oid+'\n').encode());process.stdin.flush()
            header=process.stdout.readline().decode().split()
            data=process.stdout.read(int(header[2]));process.stdout.read(1)
            if header[1]=='blob':
                check_data(scanner,data,'published-history:'+name)
                published_blobs+=1
    finally:
        process.stdin.close();process.wait()
    known=[f for f in broad['findings'] if 'KNOWN_PRIVATE_SECRET' in f['types']]
    assert len(known)==1,'Unexpected number of private-secret object findings'
    oid=known[0]['location'].split(':')[1]
    local_exposure_published=oid in objects
    excluded_ocr=[f for f in broad['inspection_failures'] if f['method']=='offline_OCR']
    assert len(excluded_ocr)==1 and excluded_ocr[0]['location'].startswith('git-object:')
    assert excluded_ocr[0]['location'].split(':')[1] not in objects,'Unresolved OCR object is in published history'
    # Original failure slots: decode only these Parquet payloads, no OCR rerun.
    parquet=[]
    for failure in broad['inspection_failures']:
        if failure['method']!='Parquet':continue
        location=failure['location']
        data=(ROOT/location.removeprefix('working:')).read_bytes() if location.startswith('working:') else git('cat-file','blob',location.split(':')[1])
        table=pq.read_table(io.BytesIO(data))
        for batch in table.to_batches(max_chunksize=500):
            check_data(scanner,json.dumps(batch.to_pylist(),default=str).encode(),'parquet-supplement:'+location)
        parquet.append({'location':location,'rows':table.num_rows,'status':'DECODED_AND_SCANNED'})
    names=selected()
    whitespace='NOT_STAGED_YET'
    if args.staged:
        staged=git('diff','--cached','--name-only','--diff-filter=ACM').decode().splitlines()
        assert staged==names,'Staged paths differ from reviewed allowlist'
        # Preserve immutable source hashes and intentional Markdown hard breaks.
        # Recognize the original CSV CRLF endings; reject every other warning
        # except these six exact, pre-existing lines in four verified artifacts.
        expected={
            ('gnn_graphrag/reviews/STEP_66C_3T_V2_PROTOCOL_REVIEW.md',3),
            ('gnn_graphrag/reviews/STEP_66C_3U_V2_FREEZE_APPROVAL.md',3),
            ('gnn_graphrag/reviews/STEP_66C_3U_V2_FREEZE_APPROVAL.md',4),
            ('gnn_graphrag/src/prepare_association_protocol_v2.py',435),
            ('reports/final_project/CHALLENGE_3_FINAL/HeartTrialTwin_Challenge3_Final_Report.md',5),
            ('reports/final_project/CHALLENGE_3_FINAL/HeartTrialTwin_Challenge3_Final_Report.md',6),
        }
        diff=subprocess.run(['git','-c','core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol',
                             'diff','--cached','--check'],cwd=ROOT,capture_output=True,text=True)
        found=set()
        for line in diff.stdout.splitlines():
            m=re.match(r'^(.*?):(\d+): (.*)$',line)
            if m:
                assert m[3]=='trailing whitespace.','Unexpected whitespace warning type'
                found.add((m[1],int(m[2])))
        assert diff.returncode==2 and found==expected,'Unexpected whitespace warnings'
        for name,_ in expected:
            assert hashlib.sha256(git('show',':'+name)).hexdigest()==old[name]['sha256'],'Frozen whitespace-exception file changed'
        whitespace='ONLY_SIX_VERIFIED_FROZEN_LINES_AFTER_RECOGNIZING_CSV_CRLF'
    reused=[];new=[];files=[]
    for name in names:
        path=ROOT/name
        assert not path.is_symlink()
        assert path.suffix not in {'.npy','.pt','.pkl','.joblib','.parquet','.zip','.db','.sqlite','.sqlite3'}
        assert path.name=='.env.example' or not path.name.startswith('.env')
        data=git('show',':'+name) if args.staged else path.read_bytes()
        digest=hashlib.sha256(data).hexdigest()
        assert len(data)<10*1024*1024
        check_data(scanner,data,'selected:'+name)
        if name in old and old[name]['sha256']==digest:
            reused.append(name)
        else:
            assert path.suffix not in {'.pdf','.docx','.pptx','.png','.jpg'},'Changed binary requires focused review'
            new.append(name)
        for failure in broad['inspection_failures']:
            assert not failure['location'].startswith('working:'+name+'!') and failure['location']!='working:'+name,'Selected binary had an unresolved broad-scan failure'
        files.append({'path':name,'sha256':digest,'bytes':len(data)})
    # Review complete literal candidates as test fixtures, without emitting values.
    assert all('/tests/' in f['location'] or '/test_' in f['location'] or f['location'].startswith('git-object:')
               for f in broad['literal_assignment_candidates'])
    blocked=[f for f in scanner.findings if f.get('disposition')=='BLOCK']
    result={'status':'PASS' if not blocked and not local_exposure_published else 'BLOCKED',
        'checked_staged':args.staged,'published_refs':refs,'published_history_blobs_checked':published_blobs,
        'whitespace_check':whitespace,
        'known_local_exposure_reachable_from_published_refs':local_exposure_published,
        'prior_scan_blobs':broad['git_blobs_inspected'],'prior_unique_images_OCR':broad['methods']['images_OCR_unique'],
        'cached_document_checks_reused':len(reused),'new_or_changed_text_files_checked':new,
        'parquet_supplement':parquet,'findings':scanner.findings,
        'remaining_historical_exception':'One excluded, non-published render-cache image timed out during OCR; not selected.',
        'limitations':['No proof against deleted public refs, forks, external copies or unknown/obfuscated secrets.',
            'OCR is imperfect; no OCR reruns were performed.','The unchanged exposed password is not certified uncompromised.'],
        'selected_count':len(files),'selected_bytes':sum(f['bytes'] for f in files),'selected_files':files}
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','checked_staged','published_history_blobs_checked','known_local_exposure_reachable_from_published_refs','selected_count','selected_bytes')}))
    if result['status']!='PASS':raise SystemExit(1)


if __name__=='__main__':main()
