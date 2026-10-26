"""Read-only local/Git-object credential checks; no unpickling or network calls.

Only redacted findings are saved. A negative scan is not proof of secrecy, and
cannot revoke an exposed password. Run using bundled Python (pypdf/Pillow/NumPy)
and the separately compiled offline Apple Vision helper. Original artifacts are
never rewritten. No database configuration is changed.
"""
from __future__ import annotations
import argparse
import bz2
import gzip
import hashlib
import io
import json
import lzma
import re
import subprocess
import tempfile
import zipfile
import zlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEXT = {'.py','.md','.json','.jsonl','.csv','.txt','.example','.toml','.yml','.yaml','.xml','.svg','.mjs','.swift','.ipynb','.ndjson','.sh',''}
IMAGE = {'.png','.jpg','.jpeg','.tif','.tiff','.bmp','.webp'}
PATTERNS = {
    'PRIVATE_KEY': rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'API_TOKEN': rb'\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{25,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16})\b',
    'EMBEDDED_CREDENTIAL_URL': rb'(?i)(?:https?|neo4j|bolt)(?:\+s|\+ssc)?://[^\s/@:\"<>]+:[^\s/@\"<>]+@',
}


class Scanner:
    def __init__(self, ocr):
        self.ocr = ocr
        self.secrets = set()
        for name in ('full_cohort_graphrag/.env','graphrag/.env','artifacts/knowledge_graph/.env','cohort_scaling/.env','agentic_graphrag/.env'):
            p = ROOT/name
            if p.is_file():
                for line in p.read_text().splitlines():
                    if '=' not in line or line.lstrip().startswith('#'): continue
                    key,value = line.split('=',1)
                    value=value.strip().strip('"\'')
                    if re.search('PASSWORD|API_KEY|TOKEN|SECRET',key,re.I) and len(value)>=8:
                        self.secrets.add(value)
        self.findings=[]
        self.failures=[]
        self.methods=Counter()
        self.cache={}
        self.seen_images={}
        self.exposure_candidates=[]
        self.literal_candidates=[]

    def match(self, data, name, method):
        kinds=[kind for kind,pattern in PATTERNS.items() if re.search(pattern,data)]
        for value in self.secrets:
            if any(encoded in data for encoded in (value.encode(),value.encode('utf-16le'),value.encode('utf-16be'))):
                kinds.append('KNOWN_PRIVATE_SECRET');break
        if kinds:
            self.findings.append({'location':name,'method':method,'types':sorted(set(kinds))})
        # Review string literals separately: a regex cannot distinguish a mocked
        # test password from an unknown real credential. Never emit their values.
        if method in {'raw_bytes_all_sizes','PDF_text','PDF_decompressed_content'}:
            text=data.decode('utf-8',errors='replace').replace('\\"','"')
            pattern=r'''(?i)(password|api[_-]?key|access[_-]?token|secret)["']?\s*[:=]\s*["']([^"'\\\r\n]{4,120})["']'''
            for match in re.finditer(pattern,text):
                value=match[2].strip()
                if value.startswith(('<','${')):continue
                self.literal_candidates.append({'location':name,'field':match[1].lower(),
                    'line':text.count('\n',0,match.start())+1,'method':method})

    def image(self,data,name):
        digest=hashlib.sha256(data).hexdigest()
        if digest not in self.seen_images:
            suffix=Path(name).suffix.lower() if Path(name).suffix.lower() in IMAGE else '.png'
            with tempfile.NamedTemporaryFile(suffix=suffix) as f:
                f.write(data);f.flush()
                try:
                    run=subprocess.run([self.ocr],input=f.name+'\n',text=True,capture_output=True,timeout=60,check=True)
                    result=json.loads(run.stdout)
                    if result.get('ok') is not True:raise ValueError('OCR unavailable')
                    self.seen_images[digest]=result['text']
                    self.methods['images_OCR_unique']+=1
                except Exception as exc:
                    self.failures.append({'location':name,'method':'offline_OCR','error_type':type(exc).__name__})
                    return
        text=self.seen_images[digest]
        self.match(text.encode(),name,'offline_OCR')
        compact=''.join(text.split())
        if any(''.join(v.split()) in compact for v in self.secrets):
            self.findings.append({'location':name,'method':'OCR_whitespace_normalized','types':['KNOWN_PRIVATE_SECRET']})

    def scan(self,data,name,depth=0):
        if depth>5:
            self.failures.append({'location':name,'method':'container_depth','error_type':'Limit'});return
        self.match(data,name,'raw_bytes_all_sizes')
        suffix=Path(name).suffix.lower()
        if suffix=='.example':
            for line in data.decode('utf-8',errors='replace').splitlines():
                m=re.match(r'\s*([A-Z_]*(?:PASSWORD|API_KEY|TOKEN))\s*=\s*(.*?)\s*$',line)
                if m:
                    value=m[2].strip('"\'')
                    if value and not value.startswith(('<','${')) and not value.lower().startswith(('your','replace','optional','changeme')):
                        self.exposure_candidates.append({'location':name,'variable':m[1],'finding':'NON_PLACEHOLDER_SECRET_ASSIGNMENT'})
        if zipfile.is_zipfile(io.BytesIO(data)):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    for member in z.infolist():
                        if not member.is_dir():self.scan(z.read(member),name+'!'+member.filename,depth+1)
                self.methods['ZIP_containers_decompressed']+=1
            except Exception as exc:self.failures.append({'location':name,'method':'ZIP','error_type':type(exc).__name__})
        elif data.startswith(b'%PDF-'):
            try:
                from pypdf import PdfReader
                reader=PdfReader(io.BytesIO(data))
                if reader.is_encrypted:raise ValueError('Encrypted PDF')
                self.match(str(reader.metadata).encode(),name,'PDF_metadata')
                for number,page in enumerate(reader.pages,1):
                    loc=f'{name}!page-{number}'
                    self.match((page.extract_text() or '').encode(),loc,'PDF_text')
                    contents=page.get_contents()
                    if contents:self.match(contents.get_data(),loc,'PDF_decompressed_content')
                    for image in page.images:self.image(image.data,loc+'!'+image.name)
                self.methods['PDF_text_streams_and_images']+=1
            except Exception as exc:self.failures.append({'location':name,'method':'PDF','error_type':type(exc).__name__})
        elif suffix in IMAGE or data.startswith((b'\x89PNG\r\n',b'\xff\xd8\xff',b'GIF87a',b'GIF89a',b'II*\x00',b'MM\x00*')):
            self.image(data,name)
        elif suffix=='.parquet' or data.startswith(b'PAR1'):
            try:
                import pyarrow.parquet as pq
                table=pq.read_table(io.BytesIO(data))
                for batch in table.to_batches(max_chunksize=500):
                    self.match(json.dumps(batch.to_pylist(),default=str).encode(),name,'Parquet_decoded_rows')
                self.methods['Parquet_decoded']+=1
            except Exception as exc:self.failures.append({'location':name,'method':'Parquet','error_type':type(exc).__name__})
        elif suffix=='.npy' or data.startswith(b'\x93NUMPY'):
            try:
                import numpy as np
                array=np.load(io.BytesIO(data),allow_pickle=False)
                if array.dtype.kind not in 'biufc':raise ValueError('Non-numeric array')
                self.methods['numeric_NPY_no_pickle']+=1
            except Exception as exc:self.failures.append({'location':name,'method':'NPY','error_type':type(exc).__name__})
        elif suffix in {'.joblib','.pkl'} or data.startswith((b'\x80\x04',b'\x80\x05',b'\x78\x9c',b'\x78\x5e',b'\x78\x01',b'\x78\xda')):
            # Never execute deserialization. Examine raw or decompressed bytes.
            expanded=None
            for decoder in (zlib.decompress,gzip.decompress,bz2.decompress,lzma.decompress):
                try:expanded=decoder(data);break
                except Exception:pass
            if expanded is not None:self.match(expanded,name,'compressed_pickle_bytes_no_execution')
            self.methods['pickle_raw_or_decompressed_no_execution']+=1
        else:self.methods['text_or_raw_binary_all_sizes']+=1

    def item(self,data,name):
        digest=hashlib.sha256(data).hexdigest()
        if digest in self.cache:
            previous=self.cache[digest]
            for finding in previous:self.findings.append({**finding,'location':name,'method':'identical_SHA256_to_scanned_payload'})
            self.methods['duplicate_payloads_reused']+=1
            return
        before=len(self.findings)
        self.scan(data,name)
        self.cache[digest]=list(self.findings[before:])


def git(args):return subprocess.check_output(['git',*args],cwd=ROOT)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--ocr',required=True)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    if args.output.exists():raise SystemExit('Refusing to overwrite review output')
    scanner=Scanner(args.ocr)
    # Include all pre-review nonignored files except unrelated course folders.
    names=[n for n in git(['ls-files','--cached','--others','--exclude-standard','-z']).decode().split('\0') if n and not n.startswith('week ')]
    # Explicitly retain the previously oversized/binary payloads in the scan
    # even after publication-only ignore rules exclude them from Git status.
    for directory in ('gnn_graphrag/data','gnn_graphrag/feature_artifacts','gnn_graphrag/protocols',
                      'gnn_graphrag/experiments','artifacts/cohort_scaling'):
        names.extend(p.relative_to(ROOT).as_posix() for p in (ROOT/directory).rglob('*')
                     if p.is_file() and not p.name.startswith('.env') and '__pycache__' not in p.parts)
    inventory=[]
    for i,name in enumerate(sorted(set(names)),1):
        path=ROOT/name
        if not path.is_file():continue
        data=path.read_bytes()
        inventory.append({'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
        scanner.item(data,'working:'+name)
        if i%50==0:print(f'Working files inspected: {i}',flush=True)
    # Scan every stored Git blob, including local Codex checkpoint/unreachable
    # objects, not just current HEAD. This does not imply those refs are public.
    names_by_oid={}
    for line in git(['rev-list','--objects','--all']).decode().splitlines():
        oid,*name=line.split(' ',1);names_by_oid[oid]=name[0] if name else ''
    rows=git(['cat-file','--batch-all-objects','--batch-check=%(objectname) %(objecttype) %(objectsize)']).decode().splitlines()
    process=subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    blobs=0
    try:
        for row in rows:
            oid,kind,size=row.split()
            if kind!='blob':continue
            process.stdin.write((oid+'\n').encode());process.stdin.flush()
            header=process.stdout.readline().decode().split()
            data=process.stdout.read(int(header[2]));process.stdout.read(1)
            scanner.item(data,'git-object:'+oid+':'+names_by_oid.get(oid,''))
            blobs+=1
            if blobs%100==0:print(f'Git blobs inspected: {blobs}',flush=True)
    finally:
        process.stdin.close();process.wait()
    report={'created_utc':datetime.now(timezone.utc).isoformat(),'working_files':inventory,
        'git_blobs_inspected':blobs,'oversize_files_skipped':0,'methods':dict(scanner.methods),
        'findings':scanner.findings,'example_assignment_candidates':scanner.exposure_candidates,
        'literal_assignment_candidates':scanner.literal_candidates,'inspection_failures':scanner.failures,
        'limits':['Pattern/exact-value scans and OCR cannot certify absence of all secrets.','No pickle or model code was executed.','OCR can miss obscured or poorly recognized text.','Exposed credentials remain risky until revoked or rotated.','Local Codex Git objects are distinct from published branch history.']}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'output':str(args.output),'working_files':len(inventory),'git_blobs':blobs,'findings':len(scanner.findings),'inspection_failures':len(scanner.failures),'example_candidates':len(scanner.exposure_candidates)}),flush=True)


if __name__=='__main__':main()
