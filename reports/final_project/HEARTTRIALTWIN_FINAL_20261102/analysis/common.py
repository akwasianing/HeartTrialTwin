"""Pinned, read-only inputs and small deterministic scientific graphics."""
import csv, hashlib, importlib.util, json, math, re
from collections import Counter, defaultdict
from pathlib import Path
from xml.sax.saxutils import escape
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FINAL=Path(__file__).resolve().parents[1]
ROOT=FINAL.parents[2]
QUAL=ROOT/'reports/project_review/historical_label_feature_qualification_v1'
AUDIT=ROOT/'reports/project_review/risk_forecasting_feasibility_v1'
GRAPH=ROOT/'artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1'
HIST=ROOT/'full_system_feasibility/snapshot_strategy'
spec=importlib.util.spec_from_file_location('historical_qualification',QUAL/'qualify_historical.py')
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
PHASES=['EARLY_PHASE1','PHASE1','PHASE1/PHASE2','PHASE2','PHASE2/PHASE3','PHASE3','PHASE4','NA']
LABELS={'EARLY_PHASE1':'Early Phase 1','PHASE1':'Phase 1','PHASE1/PHASE2':'Phase 1/2','PHASE2':'Phase 2','PHASE2/PHASE3':'Phase 2/3','PHASE3':'Phase 3','PHASE4':'Phase 4','NA':'Not Applicable'}
COLORS={'COMPLETED':'#098A88','TERMINATED':'#BC5A22','WITHDRAWN':'#795AA6'}

def sha(p):return q.sha(Path(p))
def rows(p):return q.rows(Path(p))
def save(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False,default=lambda x:x.item() if isinstance(x,np.generic) else str(x))+'\n')
def write_csv(p,values,fields=None):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);values=list(values)
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(values[0]));w.writeheader();w.writerows(values)
def num(v):
    try:n=float(v);return n if math.isfinite(n) and n>=0 else None
    except (TypeError,ValueError):return None
def wilson(k,n):
    if not n:return None,None
    p=k/n;z=1.96;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return c-h,c+h
def status_row(group,field,value):
    c=Counter(r['overall_status'] for r in group);n=len(group);lo,hi=wilson(c['TERMINATED']+c['WITHDRAWN'],n)
    return {'field':field,'value':value,'n':n,**{s:c[s] for s in COLORS},'discontinued':c['TERMINATED']+c['WITHDRAWN'],
        'discontinued_fraction':(c['TERMINATED']+c['WITHDRAWN'])/n if n else None,'wilson_lower':lo,'wilson_upper':hi}

def verify_sources():
    m=json.loads((QUAL/'qualification_manifest.json').read_text())
    for path,h in m['source_sha256'].items():assert sha(ROOT/path)==h,path
    for path,h in m['output_sha256'].items():assert sha(QUAL/path)==h,path
    for path,h in m['protected_sha256'].items():assert sha(ROOT/path)==h,path
    protected=dict(m['protected_sha256'])
    for base in [QUAL,ROOT/'reports/challenge4/FINAL_SUBMISSION/deliverables',ROOT/'reports/final_project/CHALLENGE_3_FINAL']:
        for p in base.glob('*'):
            if p.is_file():protected[str(p.relative_to(ROOT))]=sha(p)
    return {'source_sha256':m['source_sha256'],'protected_sha256':protected}

def load_current():
    data=json.loads((AUDIT/'audit_source_extract.json').read_text())
    studies={r['nct_id']:r for r in data['studies']};assert len(studies)==2824
    trial={r['nct_id']:r for r in rows(GRAPH/'nodes_trial.csv')}
    designs={r['nct_id']:r for r in data['designs']}
    interventions=defaultdict(list);leads=defaultdict(list)
    for line in (GRAPH/'source_cache/interventions.jsonl').read_text().splitlines():
        r=json.loads(line);interventions[r['nct_id']].append(r)
    for line in (GRAPH/'source_cache/sponsors.jsonl').read_text().splitlines():
        r=json.loads(line)
        if r['lead_or_collaborator'].lower()=='lead':leads[r['nct_id']].append(r)
    for n,s in studies.items():
        assert s['phase']==trial[n]['phase'];s['brief_title']=trial[n]['brief_title'];s['study_type']=trial[n]['study_type']
    return studies,designs,interventions,leads

class Plot:
    """Identical data geometry to PNG/SVG; no synthetic clinical visuals."""
    W,H=3000,1850
    def __init__(self,title,subtitle,footer='AACT 2026-09-05. Selected terminal-outcome cohort. Descriptive, noncausal findings.'):
        self.im=Image.new('RGB',(self.W,self.H),'white');self.d=ImageDraw.Draw(self.im)
        self.svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.W}" height="{self.H}" viewBox="0 0 {self.W} {self.H}"><rect width="100%" height="100%" fill="white"/><title>{escape(title)}</title>']
        self.text(90,50,title,54,True);self.text(90,133,subtitle,30,color='#53616F')
        self.text(90,1750,footer,26,color='#53616F')
    def text(self,x,y,t,size=32,bold=False,color='#122B45'):
        f=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial'+(' Bold' if bold else '')+'.ttf',size)
        self.d.text((x,y),str(t),font=f,fill=color)
        self.svg.append(f'<text x="{x}" y="{y+size*.91}" font-family="Arial" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{escape(str(t))}</text>')
    def rect(self,x,y,w,h,fill):
        self.d.rectangle((x,y,x+w,y+h),fill=fill);self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"/>')
    def line(self,x,y,xx,yy,color='#BCC8D1',width=2):
        self.d.line((x,y,xx,yy),fill=color,width=width);self.svg.append(f'<line x1="{x}" y1="{y}" x2="{xx}" y2="{yy}" stroke="{color}" stroke-width="{width}"/>')
    def save(self,name):
        p=FINAL/'poster/figures'/name;p.parent.mkdir(parents=True,exist_ok=True)
        self.im.save(p.with_suffix('.png'),dpi=(300,300));p.with_suffix('.svg').write_text(''.join(self.svg)+'</svg>')

def bars(name,title,subtitle,labels,values,denominators=None):
    f=Plot(title,subtitle);mx=max(values) or 1
    step=min(150,1340/max(len(labels),1));top=260
    for i,(label,n) in enumerate(zip(labels,values)):
        y=top+i*step;f.text(90,y,label,32);w=1500*n/mx;f.rect(830,y,w,60,'#098A88')
        suffix=f' ({100*n/denominators[i]:.2f}%)' if denominators else ''
        f.text(850+w,y+8,f'{n:,}'+suffix,31)
    f.save(name)

def stacked(name,title,subtitle,records,labels=None):
    f=Plot(title,subtitle);step=min(150,1300/max(len(records),1));top=260
    for i,r in enumerate(records):
        y=top+i*step;f.text(90,y,labels[i] if labels else str(r['value']),32);x=830
        for s,col in COLORS.items():
            w=1650*r[s]/r['n'] if r['n'] else 0
            if w:f.rect(x,y,w,60,col)
            if w>60:f.text(x+12,y+10,str(r[s]),28,True,'white')
            x+=w
        f.text(2540,y+10,f"n={r['n']:,}",30)
    for i,(s,col) in enumerate(COLORS.items()):
        f.rect(830+i*570,1630,40,40,col);f.text(885+i*570,1628,s.title(),29)
    f.save(name)
