"""Offline historical-label/feature qualification. Never trains or calls services.

Reuses checksum-pinned cached observations and the completed descriptive audit.
Does not load isolated final-test stores, model checkpoints or predictions.
All emitted files stay beside this script. Existing outputs are not overwritten.
"""
from __future__ import annotations
import argparse
import calendar
import csv
import gzip
import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PREV=HERE.parent/'risk_forecasting_feasibility_v1'
HIST=ROOT/'full_system_feasibility/snapshot_strategy'
GNN=ROOT/'gnn_graphrag/protocols/HTT-GNN-ASSOC-PROTOCOL-v2'
FROZEN=ROOT/'step3_manifest/HeartTrialTwin_first_p1_cohort_manifest_HTT-P1-AACT-20260905.csv'
VERSION='HTT-HIST-LABEL-FEATURE-QUALIFICATION-v1'
ASOF=date(2026,9,5)
TABLES=['brief_summaries.txt','conditions.txt','designs.txt','interventions.txt','sponsors.txt','studies.txt']
ONGOING={'NOT_YET_RECRUITING','RECRUITING','ENROLLING_BY_INVITATION','ACTIVE_NOT_RECRUITING'}
TERMINAL={'COMPLETED','TERMINATED','WITHDRAWN'}
HF_TERMS=['heart failure','cardiac failure','left ventricular failure','right ventricular failure','ventricular failure','congestive cardiac failure']


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def rows(p):
    with p.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))


def normalized(s):
    return re.sub(r'[^A-Z0-9]+','_',s.upper()).strip('_')


def phase_key(s):
    return s.upper().replace(' ','').replace('_','').replace('N/A','NA') or 'MISSING'


def interval(s):
    """Conservative bounds from the raw date text, not AACT-imputed days."""
    s=(s or '').strip()
    if not s:return None
    iso_month=re.fullmatch(r'(\d{4})-(\d{2})',s)
    if iso_month:
        y,mo=map(int,iso_month.groups())
        return date(y,mo,1),date(y,mo,calendar.monthrange(y,mo)[1])
    months={calendar.month_name[i].lower():i for i in range(1,13)}
    m=re.fullmatch(r'([A-Za-z]+)\s+(\d{4})',s)
    if m and m[1].lower() in months:
        y=int(m[2]);mo=months[m[1].lower()]
        return date(y,mo,1),date(y,mo,calendar.monthrange(y,mo)[1])
    m=re.fullmatch(r'([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})',s)
    if m and m[1].lower() in months:
        d=date(int(m[3]),months[m[1].lower()],int(m[2]));return d,d
    if re.fullmatch(r'\d{4}',s):return date(int(s),1,1),date(int(s),12,31)
    try:d=date.fromisoformat(s);return d,d
    except ValueError:return None


def positive(s):
    try:return float(s)>0 and float(s)<float('inf')
    except (ValueError,TypeError):return False


def registration_timing(posted,start):
    if start is None:return 'UNKNOWN'
    if posted<start[0]:return 'PRE_START'
    if posted>=start[1]:return 'AFTER_OR_ON_START'
    return 'UNCERTAIN_DATE_PRECISION'


def posting_anchor_status(study,posted,observation):
    native=study.get('study_first_posted_date','')
    if not native:return 'LEGACY_FIELD_ABSENT'
    if native==posted.isoformat():return 'MATCH'
    # An explicitly estimated historical date is not contradictory Actual truth.
    # Keep the original API-anchor rule, but only reconcile if both dates are
    # already public by observation and satisfy the fixed 45-day window.
    if (normalized(study.get('study_first_posted_date_type','')).startswith('ESTIMAT')
        and 0<=(observation-date.fromisoformat(native)).days<=45
        and 0<=(observation-posted).days<=45):
        return 'HISTORICAL_ESTIMATE_DIFFERENCE_RECONCILED_TO_FROZEN_API_ANCHOR'
    return 'MISMATCH_REQUIRES_REVIEW'


def chronology_issues(current,observation):
    bounds=interval(current.get('completion_month_year',''))
    issues=[]
    if current.get('completion_date_type')=='ACTUAL' and bounds:
        if bounds[1]<observation:issues.append('ACTUAL_COMPLETION_BEFORE_OBSERVATION')
        elif bounds[0]<=observation<=bounds[1]:issues.append('ACTUAL_COMPLETION_OVERLAPS_OBSERVATION')
        if bounds[0]>ASOF:issues.append('ACTUAL_COMPLETION_AFTER_ASCERTAINMENT')
        elif bounds[1]>ASOF:issues.append('ACTUAL_COMPLETION_OVERLAPS_ASCERTAINMENT_PRECISION')
    if current['overall_status']=='WITHDRAWN' and positive(current.get('enrollment')):
        issues.append('WITHDRAWN_WITH_POSITIVE_RECORDED_ENROLLMENT')
    return issues


def emit(name,data,fields=None):
    data=list(data)
    with (HERE/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(data[0]));w.writeheader();w.writerows(data)


def save(name,value):
    (HERE/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def family_checks(ids,groups,pairs,temporal):
    crossing=[];weak=set();group_members=defaultdict(list)
    for n in ids:group_members[groups[n]['family_id']].append(n)
    for fid,ns in group_members.items():
        if len({temporal[n] for n in ns})>1:
            crossing.append({'family_id':fid,'nct_ids':sorted(ns),'action':'REVIEW_BEFORE_REVISED_EVALUATION'})
    selected=[]
    for p in pairs:
        left,right=p['left_nct_id'],p['right_nct_id']
        if left not in ids and right not in ids:continue
        both=left in ids and right in ids
        if p['strength']=='WEAK':weak.update({left,right}&ids)
        selected.append({**p,'left_in_historical_subset':left in ids,'right_in_historical_subset':right in ids,
            'crosses_historical_windows':both and temporal[left]!=temporal[right],
            'disposition':'CONSERVATIVE_GROUP_CANDIDATE_NOT_SCIENTIFIC_EQUIVALENCE' if p['strength']=='STRONG' else 'UNRESOLVED_REVIEW_CANDIDATE'})
    return selected,crossing,weak


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--verify-only',action='store_true');ap.add_argument('--refresh-qualification',action='store_true',help='Recompute this new audit only from identical verified cached inputs.');args=ap.parse_args()
    if args.verify_only:
        m=json.loads((HERE/'qualification_manifest.json').read_text())
        for n,h in m['source_sha256'].items():assert sha(ROOT/n)==h,n
        for n,h in m['output_sha256'].items():assert sha(HERE/n)==h,n
        for n,h in m['protected_sha256'].items():assert sha(ROOT/n)==h,n
        print('PASS: sources, qualification outputs and protected artifacts unchanged');return
    if (HERE/'qualification_manifest.json').exists():
        if not args.refresh_qualification:raise SystemExit('Existing qualification preserved; use --verify-only.')
        prior=json.loads((HERE/'qualification_manifest.json').read_text())
        for n,h in prior['source_sha256'].items():assert sha(ROOT/n)==h,n
        for n,h in prior['output_sha256'].items():assert sha(HERE/n)==h,n
        for n,h in prior['protected_sha256'].items():assert sha(ROOT/n)==h,n
    previous=json.loads((PREV/'analysis_results.json').read_text());inputs={}
    def pin(p,expected=None):
        actual=sha(p)
        if expected:assert actual==expected,str(p)
        inputs[str(p.relative_to(ROOT))]=actual
        return actual
    for rel,h in previous['input_sha256'].items():pin(ROOT/rel,h)
    for rel,h in previous['output_sha256'].items():assert sha(PREV/rel)==h,rel
    protected=json.loads((PREV/'preservation_verification.json').read_text())['sha256']
    for p in PREV.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:protected[str(p.relative_to(ROOT))]=sha(p)
    for rel,h in protected.items():assert sha(ROOT/rel)==h,rel
    old_audit_path=HIST/'historical_snapshot_dataset_HTT-P1-AACT-HIST-A45-20260921.audit.json'
    pin(old_audit_path);old=json.loads(old_audit_path.read_text())
    for info in old['outputs'].values():pin(ROOT/info['path'],info['sha256'])
    postpath=HIST/'first_posted_metadata_HTT-P1-AACT-HIST-A45-20260921.json'
    pin(postpath,old['source_selection']['api_audit']['cache_sha256']);posted_meta=json.loads(postpath.read_text())
    pin(FROZEN,'5a2d6bbb0973a45988275efb4e9caff8400438edf4e3c560b1b7c0b1688fe7ab')
    members=rows(FROZEN);assert len(members)==len({r['nct_id'] for r in members})==2824
    source=rows(HIST/'historical_snapshot_source_audit_HTT-P1-AACT-HIST-A45-20260921.csv')
    eligibility=rows(HIST/'historical_snapshot_eligibility_audit_HTT-P1-AACT-HIST-A45-20260921.csv')
    es={r['nct_id']:r for r in eligibility};ss={r['nct_id']:r for r in source}
    selected=[r for r in eligibility if r['eligible_before_family_control']=='True' and r['related_study_purged']!='True']
    ids={r['nct_id'] for r in selected};assert len(ids)==len(selected)==545
    caches={};cache_paths={}
    for p in sorted((HIST/'archive_extracts').glob('*.json.gz')):
        pin(p);d=json.load(gzip.open(p,'rt'));key=d['audit']['snapshot_date'];assert key not in caches
        caches[key]=d;cache_paths[key]=p
    assert len(caches)==47
    for r in eligibility:
        d=caches[r['observation_date']];raw={t:d['tables'][t].get(r['nct_id'],[]) for t in TABLES}
        check=hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        assert check==r['snapshot_record_sha256'],r['nct_id']
    current=json.loads((PREV/'audit_source_extract.json').read_text())
    current_byid={r['nct_id']:r for r in current['studies']}
    frozen_byid={r['nct_id']:r for r in members}
    gpin='b13d662390b687b62a08cc1fb81bd3413f2c9d1fbb3b6ec86438b1a6854cd95b'
    pin(GNN/'split_manifest.json',gpin);gm=json.loads((GNN/'split_manifest.json').read_text())
    for n in ['family_groups.csv','family_pairs.csv']:pin(GNN/n,gm['files_sha256'][n])
    groups={r['nct_id']:r for r in rows(GNN/'family_groups.csv')}
    pairs=rows(GNN/'family_pairs.csv')
    temporal={r['nct_id']:r['temporal_group'] for r in selected}
    family_pairs,crossfamilies,weak=family_checks(ids,groups,pairs,temporal)
    label_ledger=[];features=[];issues=[];feature_summary={};post_matches=Counter()
    for e in sorted(selected,key=lambda r:r['nct_id']):
        n=e['nct_id'];obs=date.fromisoformat(e['observation_date']);posted=date.fromisoformat(e['study_first_posted_date'])
        d=caches[e['observation_date']];tables=d['tables'];study=tables['studies.txt'][n];assert len(study)==1;s=study[0]
        assert 0<=(obs-posted).days<=45
        assert posted_meta['records'][n]==posted.isoformat()
        assert ss[n]['selected_observation_date']==obs.isoformat()
        assert normalized(s['study_type'])=='INTERVENTIONAL' and normalized(s['overall_status']) in ONGOING
        texts=[s.get('brief_title','')]+[r.get('name','') for r in tables['conditions.txt'].get(n,[])]+[r.get('description','') for r in tables['brief_summaries.txt'].get(n,[])]
        assert any(term in text.lower() for text in texts for term in HF_TERMS),n
        c=current_byid[n];f=frozen_byid[n];assert c['overall_status']==f['source_overall_status']
        assert c['overall_status'] in TERMINAL
        label=int(c['overall_status']!='COMPLETED');assert label==int(f['discontinued'])
        conflicts=chronology_issues(c,obs)
        datefields=['study_first_posted_date','last_update_posted_date','study_first_submitted_date','last_update_submitted_date','first_received_date','last_changed_date']
        for field in datefields:
            if s.get(field) and date.fromisoformat(s[field])>obs:conflicts.append('HISTORICAL_TIMESTAMP_AFTER_OBSERVATION:'+field)
        native_post=s.get('study_first_posted_date','')
        native_key=posting_anchor_status(s,posted,obs)
        post_matches[native_key]+=1
        if native_key=='MISMATCH_REQUIRES_REVIEW':conflicts.append('FIRST_POSTED_METADATA_MISMATCH')
        registration=registration_timing(posted,interval(s.get('start_month_year','')))
        completion=interval(c.get('completion_month_year',''))
        supported_date=bool(c['completion_date_type']=='ACTUAL' and completion and completion[0]>obs and completion[1]<=ASOF)
        lead=[r for r in tables['sponsors.txt'].get(n,[]) if r.get('lead_or_collaborator','').lower()=='lead']
        design=tables['designs.txt'].get(n,[]);assert len(design)<=1
        design=design[0] if design else {}
        interventions=tables['interventions.txt'].get(n,[])
        label_ledger.append({'nct_id':n,'dataset_version':VERSION,'observation_date':obs.isoformat(),'first_posted_date':posted.isoformat(),
          'observation_lag_days':(obs-posted).days,'historical_status':s['overall_status'],'terminal_status':c['overall_status'],
          'operational_discontinuation_label':label,'strict_terminated_label':1 if c['overall_status']=='TERMINATED' else 0 if c['overall_status']=='COMPLETED' else '',
          'terminal_status_ascertained':True,'ascertainment_date':ASOF.isoformat(),'observation_to_ascertainment_days':(ASOF-obs).days,
          'actual_completion_date_type':c['completion_date_type'],'actual_completion_raw':c['completion_month_year'],
          'actual_completion_lower':completion[0].isoformat() if completion else '', 'actual_completion_upper':completion[1].isoformat() if completion else '',
          'actual_completion_chronology_supported':supported_date,'exact_terminal_transition_date_verified':False,
          'label_qualification':'REVIEW_REQUIRED' if conflicts else 'PASS_REGISTRY_CONDITIONAL_SCREEN',
          'review_reasons':';'.join(conflicts),'historical_temporal_group':e['temporal_group'],
          'registration_timing_legacy':e['registration_timing'],'registration_timing_precision_aware':registration,
          'first_posted_source_match':native_key,'historical_first_posted_date':native_post,
          'historical_first_posted_type':s.get('study_first_posted_date_type',''),
          'historical_phase':s['phase'],'current_phase':c['phase'],
          'historical_enrollment':s.get('enrollment',''),'historical_enrollment_type':s.get('enrollment_type',''),
          'current_enrollment':c['enrollment'],'current_enrollment_type':c['enrollment_type'],
          'historical_completion_raw':s.get('completion_month_year',''),'historical_completion_type':s.get('completion_date_type',''),
          'snapshot_record_sha256':e['snapshot_record_sha256'],'source_cache':str(cache_paths[e['observation_date']].relative_to(ROOT)),
          'historical_study_family_id':e['study_family_id'],'latest_conservative_family_id':groups[n]['family_id'],
          'latest_family_status':groups[n]['family_status'],'weak_family_review_endpoint':n in weak,
          'why_stopped_present_at_observation':bool(s.get('why_stopped','').strip()),
          'original_registration_payload_verified':False})
        for reason in conflicts:issues.append({'nct_id':n,'issue':reason,'disposition':'QUARANTINE_PROPOSED_NOT_SOURCE_LABEL_CHANGE','current_status':c['overall_status'],'observation_date':obs.isoformat(),'completion_raw':c['completion_month_year']})
        def add(name,value,table,record_ids,qualification,admit,limitation):
            features.append({'nct_id':n,'feature':name,'raw_value':json.dumps(value,ensure_ascii=False),'source_table':table,
                'source_record_ids':';'.join(map(str,record_ids)),'snapshot_date':obs.isoformat(),'source_cache':str(cache_paths[e['observation_date']].relative_to(ROOT)),
                'cache_sha256':inputs[str(cache_paths[e['observation_date']].relative_to(ROOT))],'trial_record_sha256':e['snapshot_record_sha256'],
                'qualification':qualification,'conditionally_admissible_predictor':admit,'limitation':limitation})
        add('phase',s.get('phase',''),'studies.txt',[n],'AVAILABLE_AS_OF_SNAPSHOT' if s.get('phase') else 'MISSING',bool(s.get('phase')),'Categorical; N/A is not missing. Not certified version 1.')
        etype=normalized(s.get('enrollment_type',''));target_ok=etype=='ANTICIPATED' and positive(s.get('enrollment'))
        add('planned_enrollment',{'value':s.get('enrollment',''),'type':s.get('enrollment_type','')},'studies.txt',[n],'EARLY_PLAN_AVAILABLE' if target_ok else 'NOT_A_VALID_PLANNED_TARGET',target_ok,'Early snapshot target, not verified original target; Actual counts excluded.')
        for field in ['allocation','masking','intervention_model','primary_purpose']:
            v=design.get(field,'');add(field,v,'designs.txt',[design['id']] if design else [],'AVAILABLE_AS_OF_SNAPSHOT' if v else 'MISSING',bool(v),'Literal missing/NA distinctions and training-only harmonization required.')
        add('number_of_arms',s.get('number_of_arms',''),'studies.txt',[n],'AVAILABLE_AS_OF_SNAPSHOT' if positive(s.get('number_of_arms')) else 'MISSING_OR_INVALID',positive(s.get('number_of_arms')),'Do not infer arms from later registry groups.')
        itypes=sorted({r.get('intervention_type','') for r in interventions if r.get('intervention_type')})
        add('intervention_types',itypes,'interventions.txt',[r['id'] for r in interventions],'AVAILABLE_AS_OF_SNAPSHOT' if itypes else 'MISSING',bool(itypes),'Versioned associations; category vocabulary fitted on training only.')
        add('lead_sponsor_class',[r.get('agency_class','') for r in lead],'sponsors.txt',[r['id'] for r in lead],'AVAILABLE_UNIQUE_LEAD' if len(lead)==1 and lead[0].get('agency_class') else 'MISSING_OR_AMBIGUOUS',len(lead)==1 and bool(lead[0].get('agency_class')),'Agency class is not a funding amount.')
        add('lead_sponsor_name',[r.get('name','') for r in lead],'sponsors.txt',[r['id'] for r in lead],'AUDIT_ONLY',False,'Retain for provenance/family review, not the initial predictor contract.')
        add('registration_first_posted_date',posted.isoformat(),'frozen_ClinicalTrials.gov_API_metadata',[n],'VERIFIED_TIMESTAMP_ANCHOR',False,'Availability/partition anchor only; raw date and lag not initial model predictors; current metadata retrieval did not retrieve version-1 content.')
        add('registration_submission_date',s.get('study_first_submitted_date') or s.get('first_received_date',''),'studies.txt',[n],'AUDIT_ONLY',False,'Submission is not public posting; legacy field mapped, never substituted as observation time.')
        planned=interval(s.get('completion_month_year',''));ctype=normalized(s.get('completion_date_type',''))
        planok=ctype=='ANTICIPATED' and planned is not None and planned[0]>obs
        add('anticipated_completion',{'raw':s.get('completion_month_year',''),'type':s.get('completion_date_type','')},'studies.txt',[n],
            'EARLY_FUTURE_PLAN_AVAILABLE' if planok else 'MISSING_OR_OVERDUE_OR_NONPLAN',False,'Candidate future duration feature only; raw dates excluded from the initial contract. Requires a reviewed duration/precision transform.')
        if planok:features[-1]['qualification']='EARLY_FUTURE_PLAN_AVAILABLE_DEFERRED'
        pp=interval(s.get('primary_completion_month_year',''));pt=normalized(s.get('primary_completion_date_type',''))
        add('anticipated_primary_completion',{'raw':s.get('primary_completion_month_year',''),'type':s.get('primary_completion_date_type','')},'studies.txt',[n],
            'EARLY_FUTURE_PLAN_AVAILABLE_DEFERRED' if pt=='ANTICIPATED' and pp and pp[0]>obs else 'MISSING_OR_OVERDUE_OR_NONPLAN',False,'Primary completion is distinct from overall completion; new endpoint/feature authorization required.')
    emit('historical_cohort_qualification.csv',label_ledger)
    emit('registration_anchor_reconciliation.csv',[
        {k:r[k] for k in ['nct_id','first_posted_date','historical_first_posted_date','historical_first_posted_type','observation_date','first_posted_source_match']}
        for r in label_ledger if r['first_posted_source_match'] not in ['MATCH','LEGACY_FIELD_ABSENT']])
    emit('prediction_time_feature_records.csv',features)
    emit('label_review_queue.csv',issues,['nct_id','issue','disposition','current_status','observation_date','completion_raw'])
    emit('related_study_review.csv',family_pairs,['left_nct_id','right_nct_id','classification','strength','rule','title_similarity','entity_support','review_source','evidence','left_in_historical_subset','right_in_historical_subset','crosses_historical_windows','disposition'])
    cross_ids={n for r in crossfamilies for n in r['nct_ids']}
    inclusion=[]
    for m in sorted(members,key=lambda r:r['nct_id']):
        n=m['nct_id'];s=ss.get(n);e=es.get(n)
        reason='OUTSIDE_ORIGINAL_2017_2020_CANDIDATE_SCOPE' if not s else s['source_exclusion_reason'] or (e['exclusion_reasons'] if e else 'SOURCE_JOIN_REVIEW')
        chosen=n in ids
        row=next((r for r in label_ledger if r['nct_id']==n),None)
        inclusion.append({'nct_id':n,'historical_candidate':bool(s),'historical_snapshot_found':bool(e),'in_original_historical_545':chosen,
            'historical_exclusion_reason':reason,'new_registry_chronology_screen':row['label_qualification'] if row else 'NOT_EVALUATED',
            'new_review_reasons':row['review_reasons'] if row else '', 'latest_family_crosses_historical_windows':n in cross_ids,
            'weak_family_review_endpoint':n in weak,'current_disposition':'REVIEW_REQUIRED' if chosen and (row['review_reasons'] or n in cross_ids or n in weak) else 'CONDITIONAL_ANALYSIS_CANDIDATE' if chosen else 'NOT_ADMITTED_FROM_EXISTING_HISTORY',
            'source_dataset_changed':False})
    emit('trial_inclusion_exclusion.csv',inclusion)
    fs=[]
    for feature in sorted({r['feature'] for r in features}):
        rr=[r for r in features if r['feature']==feature];cc=Counter(r['qualification'] for r in rr)
        for k,v in sorted(cc.items()):fs.append({'feature':feature,'qualification':k,'n':v,'percent_of_545':100*v/545,'admissible_rows':sum(r['conditionally_admissible_predictor'] for r in rr if r['qualification']==k),'original_version1_verified':0})
    emit('prediction_time_feature_availability.csv',fs)
    comparison=[]
    sets={'FULL2824':set(current_byid),'HISTORICAL545':ids,'NONRETAINED2279':set(current_byid)-ids,
          'SAME_ERA_CANDIDATES651':set(ss),'SAME_ERA_NONRETAINED106':set(ss)-ids}
    inter_byid=defaultdict(set);sponsor_byid=defaultdict(set)
    graph=ROOT/'artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1'
    for line in (graph/'source_cache/interventions.jsonl').read_text().splitlines():
        r=json.loads(line);inter_byid[r['nct_id']].add(r['intervention_type'])
    for line in (graph/'source_cache/sponsors.jsonl').read_text().splitlines():
        r=json.loads(line)
        if r['lead_or_collaborator'].lower()=='lead':sponsor_byid[r['nct_id']].add(r['agency_class'])
    def characteristics(n):
        return {'phase_current':current_byid[n]['phase'],'status_current':current_byid[n]['overall_status'],
            'submission_year':frozen_byid[n]['submission_year'],'drug_present_current':str('DRUG' in inter_byid[n]),
            'industry_lead_current':str('INDUSTRY' in sponsor_byid[n])}
    for group,ns in sets.items():
        for field in ['phase_current','status_current','submission_year','drug_present_current','industry_lead_current']:
            cc=Counter(characteristics(n)[field] for n in ns)
            for val,count in sorted(cc.items()):comparison.append({'population':group,'field':field,'value':val,'n':count,'denominator':len(ns),'percent':100*count/len(ns),'time_basis':'2026_SNAPSHOT_OR_FROZEN_SUBMISSION_DATE_NOT_PREDICTORS'})
    emit('coverage_selection_comparison.csv',comparison)
    phase_counts=[]
    for population in ['ALL_545','CHRONOLOGY_PASS']:
        rr=label_ledger if population=='ALL_545' else [r for r in label_ledger if not r['review_reasons']]
        for phase in sorted({r['historical_phase'] for r in rr}):
            for window in ['ALL','development','validation']:
                group=[r for r in rr if r['historical_phase']==phase and (window=='ALL' or r['historical_temporal_group']==window)]
                phase_counts.append({'population':population,'historical_phase':phase,'window':window,'n':len(group),
                    'COMPLETED':sum(r['terminal_status']=='COMPLETED' for r in group),'TERMINATED':sum(r['terminal_status']=='TERMINATED' for r in group),
                    'WITHDRAWN':sum(r['terminal_status']=='WITHDRAWN' for r in group),'combined_positive':sum(r['operational_discontinuation_label'] for r in group)})
    emit('historical_phase_outcomes.csv',phase_counts)
    passed=[r for r in label_ledger if not r['review_reasons']]
    result={'version':VERSION,'date':'2026-10-28','training_executed':False,'source_records_hash_verified':615,
        'historical_usable':545,'version1_payloads_verified':0,'terminal_status_counts':dict(Counter(r['terminal_status'] for r in label_ledger)),
        'chronology_pass':len(passed),'review_required':len(label_ledger)-len(passed),
        'review_counts':dict(Counter(i['issue'] for i in issues)),
        'chronology_pass_status':dict(Counter(r['terminal_status'] for r in passed)),
        'legacy_registration_timing':dict(Counter(r['registration_timing_legacy'] for r in label_ledger)),
        'precision_aware_registration_timing':dict(Counter(r['registration_timing_precision_aware'] for r in label_ledger)),
        'first_posted_native_matches':dict(post_matches),'temporal_counts':{},
        'source_unavailable':{k:v for k,v in Counter(r['source_exclusion_reason'] for r in source).items() if k},
        'old_eligibility_exclusions':{k:v for k,v in Counter(r['exclusion_reasons'] for r in eligibility).items() if k},
        'observation_lag_days':{'min':min(r['observation_lag_days'] for r in label_ledger),'median':statistics.median(r['observation_lag_days'] for r in label_ledger),'max':max(r['observation_lag_days'] for r in label_ledger)},
        'observation_to_ascertainment_days':{'min':min(r['observation_to_ascertainment_days'] for r in label_ledger),'median':statistics.median(r['observation_to_ascertainment_days'] for r in label_ledger),'max':max(r['observation_to_ascertainment_days'] for r in label_ledger)},
        'actual_completion_chronology_supported':sum(r['actual_completion_chronology_supported'] for r in label_ledger),
        'actual_completion_date_types':dict(Counter(r['actual_completion_date_type'] for r in label_ledger)),
        'actual_completion_missing_raw_date':sum(r['actual_completion_date_type']=='ACTUAL' and not r['actual_completion_raw'] for r in label_ledger),
        'actual_completion_unparseable_raw_date':sum(r['actual_completion_date_type']=='ACTUAL' and bool(r['actual_completion_raw']) and interval(r['actual_completion_raw']) is None for r in label_ledger),
        'historical_why_stopped_present':sum(r['why_stopped_present_at_observation'] for r in label_ledger),
        'family_review':{'overlapping_pairs':len(family_pairs),'crossing_groups':crossfamilies,'crossing_group_endpoints':len(cross_ids),'weak_endpoints':len(weak),
            'unique_pending_family_endpoints':len(cross_ids|weak)},
        'historical_phase_changes':sum(phase_key(r['historical_phase'])!=phase_key(r['current_phase']) for r in label_ledger),
        'original_cohort_modified':False}
    for label,rr in [('ALL_545',label_ledger),('CHRONOLOGY_PASS',passed)]:
        result['temporal_counts'][label]={w:{'n':sum(r['historical_temporal_group']==w for r in rr),
            'completed':sum(r['historical_temporal_group']==w and r['terminal_status']=='COMPLETED' for r in rr),
            'terminated':sum(r['historical_temporal_group']==w and r['terminal_status']=='TERMINATED' for r in rr),
            'withdrawn':sum(r['historical_temporal_group']==w and r['terminal_status']=='WITHDRAWN' for r in rr)} for w in ['development','validation']}
    save('qualification_results.json',result)
    for p,h in protected.items():assert sha(ROOT/p)==h,p
    output_files=list(HERE.glob('*.csv'))+[HERE/'qualification_results.json']
    manifest={'version':VERSION,'training_authorized_by_this_package':False,'source_sha256':inputs,
        'output_sha256':{p.name:sha(p) for p in sorted(output_files)},'protected_sha256':protected,
        'code_sha256':sha(Path(__file__)),'no_live_services':True,'no_test_label_stores_or_model_predictions_loaded':True,
        'scope':'CONDITIONAL_TERMINAL_OUTCOME_LABEL_AND_FEATURE_QUALIFICATION_NOT_A_FROZEN_NEW_MODELING_DATASET'}
    save('qualification_manifest.json',manifest);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
