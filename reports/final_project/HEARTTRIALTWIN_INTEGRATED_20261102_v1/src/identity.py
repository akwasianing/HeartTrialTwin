"""Pinned previous deliverables; all additions are isolated in this package."""
import csv,hashlib,json,sys
from pathlib import Path

PACKAGE=Path(__file__).resolve().parents[1]
ROOT=PACKAGE.parents[2]
BASE=ROOT/'reports/final_project/HEARTTRIALTWIN_FINAL_20261102'
BASE_MANIFEST_SHA='29c54f92e4720271d6d103ddce0c7bf44abaf724a88703c59092c902c36f4c0a'
VERSION='HTT-INTEGRATED-RESEARCH-v1'
DATASET='HTT-P1-AACT-20260905'
GRAPH='HTT-KG-AACT-20260905-FULL2824-v1'
SNAPSHOT='2026-09-05'

def require(condition,message):
    if not condition:raise ValueError(message)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def read_csv(path):
    with Path(path).open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))

def load(path):return json.loads(Path(path).read_text())

def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def csv_save(path,records):
    records=list(records);path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)

def verify_base():
    path=BASE/'reports/final_package_manifest.json'
    require(sha(path)==BASE_MANIFEST_SHA,'Prior final-package manifest integrity failure')
    manifest=load(path)
    for name,expected in manifest['artifacts_sha256'].items():
        require(sha(BASE/name)==expected,'Prior final artifact integrity failure: '+name)
    return manifest

def verify_source(path):
    pins=load(BASE/'reports/source_preservation_manifest.json')
    name=str(Path(path).relative_to(ROOT));expected=pins['source_sha256'].get(name) or pins['protected_sha256'].get(name)
    require(expected and sha(path)==expected,'Pinned source integrity failure: '+name)

def legacy_paths():
    for path in [ROOT,BASE/'analysis',BASE/'modeling',BASE/'integration']:
        if str(path) not in sys.path:sys.path.insert(0,str(path))
