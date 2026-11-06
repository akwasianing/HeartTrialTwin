"""New conservative risk-study cohort; original 545/2,824 artifacts untouched."""
import gzip,hashlib,json,sys
from collections import Counter,defaultdict
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'analysis'))
from common import *

NUMERIC=['log_planned_enrollment','number_of_arms','intervention_record_count','posting_year']
INTERVENTION_TYPES=['DRUG','DEVICE','BEHAVIORAL','PROCEDURE','BIOLOGICAL','DIETARY_SUPPLEMENT','DIAGNOSTIC_TEST','OTHER','COMBINATION_PRODUCT','GENETIC','RADIATION']
CATEGORICAL=['allocation','masking','intervention_model','primary_purpose','lead_sponsor_class']

def assemble():
    verify_sources()
    es=rows(HIST/'historical_snapshot_eligibility_audit_HTT-P1-AACT-HIST-A45-20260921.csv')
    source=rows(HIST/'historical_snapshot_source_audit_HTT-P1-AACT-HIST-A45-20260921.csv')
    oldids={r['nct_id'] for r in es if r['eligible_before_family_control']=='True'}
    current,_,_,_=load_current();cache={}
    for p in sorted((HIST/'archive_extracts').glob('*.gz')):
        with gzip.open(p,'rt') as f:cache[p.name[:10]]=json.load(f)['tables']
    family={r['nct_id']:r for r in rows(ROOT/'gnn_graphrag/protocols/HTT-GNN-ASSOC-PROTOCOL-v2/family_groups.csv')}
    weak={n for r in rows(ROOT/'gnn_graphrag/protocols/HTT-GNN-ASSOC-PROTOCOL-v2/family_pairs.csv') if r['strength']=='WEAK' for n in [r['left_nct_id'],r['right_nct_id']]}
    candidates=[];ledger=[];stage=Counter();recovered=[]
    for e in sorted(es,key=lambda r:r['nct_id']):
        n=e['nct_id'];tables=cache[e['observation_date']];raw={t:tables[t].get(n,[]) for t in q.TABLES}
        assert hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':')).encode()).hexdigest()==e['snapshot_record_sha256']
        s=raw['studies.txt'][0];obs=date.fromisoformat(e['observation_date']);posted=date.fromisoformat(e['study_first_posted_date']);c=current[n];reasons=[]
        if q.normalized(s['study_type'])!='INTERVENTIONAL':reasons.append('NOT_INTERVENTIONAL')
        txt=' '.join([s.get('brief_title','')]+[r.get('name','') for r in raw['conditions.txt']]+[r.get('description','') for r in raw['brief_summaries.txt']]).lower()
        if not any(term in txt for term in q.HF_TERMS):reasons.append('HF_NOT_ESTABLISHED_HISTORICALLY')
        if q.normalized(s['overall_status']) not in q.ONGOING:reasons.append('HISTORICAL_STATUS_NOT_ONGOING')
        if not 0<=(obs-posted).days<=45:reasons.append('OBSERVATION_WINDOW_INVALID')
        if q.posting_anchor_status(s,posted,obs)=='MISMATCH_REQUIRES_REVIEW':reasons.append('POSTING_METADATA_CONFLICT')
        historically_eligible=not reasons
        if historically_eligible:
            stage['historically_eligible_after_normalization']+=1
            if n not in oldids:recovered.append(n)
            reasons+=q.chronology_issues(c,obs)
            if not reasons:stage['chronology_eligible']+=1
            if n in weak:reasons.append('WEAK_FAMILY_ENDPOINT_QUARANTINE')
            if c['overall_status']=='WITHDRAWN':reasons.append('WITHDRAWN_SEPARATE_NOT_PRIMARY_TERMINATION')
            elif c['overall_status'] not in {'COMPLETED','TERMINATED'}:reasons.append('UNRESOLVED_LABEL')
        row={'nct_id':n,'observation_date':e['observation_date'],'historical_status_raw':s['overall_status'],'historical_status_normalized':q.normalized(s['overall_status']),
            'terminal_status':c['overall_status'],'family_id':family[n]['family_id'],'from_original_545':n in oldids,
            'historically_eligible_after_normalization':historically_eligible,'reasons':';'.join(reasons),'included_primary':not reasons,
            'window':'development' if obs<=date(2018,12,31) else 'exploratory_temporal_evaluation',
            'snapshot_record_sha256':e['snapshot_record_sha256'],'old_dataset_modified':False}
        ledger.append(row)
        if reasons:continue
        d=raw['designs.txt'][0] if raw['designs.txt'] else {};lead=[r for r in raw['sponsors.txt'] if r['lead_or_collaborator'].lower()=='lead'];iv=raw['interventions.txt']
        planned=num(s.get('enrollment')) if q.normalized(s.get('enrollment_type',''))=='ANTICIPATED' else None
        if planned is not None and planned<=0:planned=None
        types={q.normalized(r['intervention_type']) for r in iv}
        candidate={'nct_id':n,'y':int(c['overall_status']=='TERMINATED'),'terminal_status':c['overall_status'],'observation_date':obs.isoformat(),
            'window':row['window'],'family_id':row['family_id'],'from_original_545':n in oldids,'historical_phase':s['phase'] or '__MISSING__',
            'log_planned_enrollment':float(np.log1p(planned)) if planned is not None else '', 'number_of_arms':num(s.get('number_of_arms')) if s.get('number_of_arms') else '',
            'intervention_record_count':len(iv),'posting_year':posted.year,
            'allocation':d.get('allocation') or '__MISSING__','masking':d.get('masking') or '__MISSING__',
            'intervention_model':d.get('intervention_model') or '__MISSING__','primary_purpose':d.get('primary_purpose') or '__MISSING__',
            'lead_sponsor_class':lead[0].get('agency_class') if len(lead)==1 else '__MISSING__',
            'source_record_sha256':e['snapshot_record_sha256'],
            **{'type_'+t:int(t in types) for t in INTERVENTION_TYPES}}
        candidates.append(candidate)
    windows=defaultdict(set)
    for r in candidates:windows[r['family_id']].add(r['window'])
    crossed={fid for fid,ww in windows.items() if len(ww)>1};purged=[]
    for r in ledger:
        if r['included_primary'] and r['family_id'] in crossed and r['window']=='exploratory_temporal_evaluation':
            r['included_primary']=False;r['reasons']='STRONG_FAMILY_LATER_WINDOW_PURGE';purged.append(r['nct_id'])
    candidates=[r for r in candidates if r['nct_id'] not in purged]
    for r in source:
        if r['nct_id'] not in {e['nct_id'] for e in es}:
            ledger.append({'nct_id':r['nct_id'],'observation_date':'','historical_status_raw':'','historical_status_normalized':'','terminal_status':'NOT_JOINED_NO_SOURCE',
                'family_id':'','from_original_545':False,'historically_eligible_after_normalization':False,'reasons':r['source_exclusion_reason'],
                'included_primary':False,'window':'','snapshot_record_sha256':'','old_dataset_modified':False})
    assert len(ledger)==651 and len({r['nct_id'] for r in ledger})==651
    dev={r['family_id'] for r in candidates if r['window']=='development'};ev={r['family_id'] for r in candidates if r['window']!='development'};assert not dev&ev
    return candidates,ledger,{'stages':dict(stage),'normalization_recovered_nct_ids':recovered,'outer_family_purged_nct_ids':purged,
        'primary_n':len(candidates),'windows':{w:{'n':sum(r['window']==w for r in candidates),'terminated':sum(r['window']==w and r['y'] for r in candidates)} for w in ['development','exploratory_temporal_evaluation']},
        'all_exclusion_reason_counts':dict(Counter(reason for r in ledger for reason in r['reasons'].split(';') if reason)),
        'feature_names':NUMERIC+['type_'+t for t in INTERVENTION_TYPES]+CATEGORICAL+['historical_phase'],
        'primary_target':'TERMINATED=1, COMPLETED=0; WITHDRAWN excluded and separately described',
        'not_an_independent_test':True,'original_dataset_modified':False}


def main():
    if (FINAL/'modeling/cohort_manifest.json').exists():raise SystemExit('Existing new cohort preserved.')
    candidates,ledger,result=assemble();write_csv(FINAL/'modeling/analysis_cohort.csv',candidates);write_csv(FINAL/'modeling/eligibility_ledger_651.csv',ledger)
    save(FINAL/'modeling/cohort_manifest.json',{**result,'version':'HTT-RISK-EARLY-STRICT-20261102-v1',
        'analysis_cohort_sha256':sha(FINAL/'modeling/analysis_cohort.csv'),'eligibility_sha256':sha(FINAL/'modeling/eligibility_ledger_651.csv'),
        'protocol':'ELIGIBILITY_PROTOCOL.md','known_validation_reused_as_exploratory':True})
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
