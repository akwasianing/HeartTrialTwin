"""All 2,824 records, all 1,319 applicable phases, and source-coded recruitment."""
import json, re
from collections import Counter,defaultdict
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from scipy.stats import chi2
from common import *


def adjusted(group,name,designs,interventions,leads,families):
    """Exploratory snapshot association; never a prospective risk model."""
    phase_levels=[p for p in PHASES if p!='PHASE2' and any(s['phase']==p for s in group)]
    names=['intercept','submission_year_centered','drug_present','industry_lead','randomized','open_masking','design_missing']
    X=[];y=[];cluster=[]
    for s in group:
        n=s['nct_id'];d=designs.get(n,{})
        base=[1,int(s['study_first_submitted_date'][:4])-2010,int(any(r['intervention_type']=='DRUG' for r in interventions[n])),
            int(any(r['agency_class']=='INDUSTRY' for r in leads[n])),int(d.get('allocation')=='RANDOMIZED'),int(d.get('masking')=='NONE'),int(not d.get('allocation') or not d.get('masking'))]
        X.append(base+[int(s['phase']==p) for p in phase_levels]);y.append(int(s['overall_status']!='COMPLETED'));cluster.append(families[n])
    X=np.asarray(X,float);y=np.asarray(y,float);names+=['phase_'+p for p in phase_levels]
    def fit(x):
        def fg(b):
            z=x@b;return np.logaddexp(0,z).sum()-y@z,x.T@(expit(z)-y)
        return minimize(fg,np.zeros(x.shape[1]),jac=True,method='BFGS',options={'maxiter':1000,'gtol':1e-6})
    full=fit(X);null=fit(X[:,:7]);p=expit(X@full.x)
    bread=np.linalg.pinv(X.T@((p*(1-p))[:,None]*X));scores=defaultdict(lambda:np.zeros(X.shape[1]))
    for g,s in zip(cluster,X*(y-p)[:,None]):scores[g]+=s
    meat=sum(np.outer(v,v) for v in scores.values());G=len(scores);N=len(y);P=X.shape[1]
    cov=bread@meat@bread*(G/(G-1))*((N-1)/(N-P));se=np.sqrt(np.maximum(np.diag(cov),0))
    rank=int(np.linalg.matrix_rank(X));gradient=float(np.linalg.norm(X.T@(p-y),ord=np.inf))
    ok=rank==P and gradient<1e-3 and np.max(np.abs(full.x))<15
    out=[]
    for j,param in enumerate(names):
        lo,hi=full.x[j]-1.96*se[j],full.x[j]+1.96*se[j]
        out.append({'analysis':name,'parameter':param,'coefficient':float(full.x[j]),'odds_ratio':float(np.exp(full.x[j])),
            'cluster_95_lower':float(np.exp(lo)),'cluster_95_upper':float(np.exp(hi)),'n':N,'positive_composite':int(y.sum()),'reference_phase':'PHASE2','fit_qualified':ok})
    write_csv(FINAL/'analysis'/f'adjusted_{name}.csv',out)
    return {'n':N,'positive_composite':int(y.sum()),'cluster_count':G,'design_rank':rank,'parameters':P,
        'max_gradient':gradient,'numerically_qualified':ok,'optimizer_message':str(full.message),
        'phase_block_likelihood_ratio':float(2*(null.fun-full.fun)),'phase_block_df':len(phase_levels),
        'phase_block_exploratory_p':float(chi2.sf(2*(null.fun-full.fun),len(phase_levels))),
        'interpretation':'Current-snapshot conditional cross-sectional association, not prediction or causal adjustment. Actual enrollment and duration excluded.'}


def recruitment(studies):
    # Positive requires an explicit operational difficulty phrase, not recruitment mention alone.
    patterns=[r'\b(?:poor|slow|low|inadequate|insufficient|limited|difficult\w*|lack of)\s+(?:patient\s+|subject\s+|participant\s+)?(?:recruit\w*|accru\w*|enroll?\w*)',
       r'\b(?:recruit\w*|accru\w*|enroll?\w*)\s+(?:was\s+|is\s+|were\s+)?(?:too\s+)?(?:slow|poor|low|difficult|insufficient|inadequate)',
       r'\b(?:unable|failed|failure|not able)\s+to\s+(?:recruit|accrue|enroll?)\w*',
       r'\b(?:recruitment|accrual|enrollment|enrolment)\s+(?:difficulties|difficulty|challenges|problems|failure)',
       r'\b(?:insufficient|inadequate|not enough|lack of)\s+(?:eligible\s+)?(?:patients|subjects|participants)',
       r'\b(?:could not|cannot)\s+(?:enroll?|recruit|accrue)\w*']
    deny=r'\b(?:not|no)\s+(?:due to\s+|related to\s+)?(?:poor\s+|slow\s+)?(?:recruitment|accrual|enrollment|enrolment)\s*(?:issues|problems|difficulties)?'
    records=[]
    for n,s in sorted(studies.items()):
        if s['overall_status'] not in {'TERMINATED','WITHDRAWN'}:continue
        text=s['why_stopped'].strip();matches=[m.group(0) for p in patterns for m in re.finditer(p,text,re.I)]
        mention=bool(re.search(r'recruit|accru|enroll|enrol',text,re.I));neg=bool(re.search(deny,text,re.I))
        code='MISSING_REASON' if not text else 'EXPLICIT_RECRUITMENT_DIFFICULTY' if matches and not neg else 'RECRUITMENT_MENTION_REVIEW_REQUIRED' if mention or matches else 'OTHER_REASON_NOT_RECRUITMENT_CODED'
        records.append({'nct_id':n,'status':s['overall_status'],'phase':s['phase'],'why_stopped_verbatim':text,'code':code,
            'matched_spans':'; '.join(sorted(set(matches))),'explicit_negation_flag':neg,
            'source_table':'studies.txt','source_record_id':n,'snapshot':'2026-09-05','adjudication':'DETERMINISTIC_SOURCE_TEXT_RULE_NOT_INDEPENDENTLY_ADJUDICATED'})
    write_csv(FINAL/'recruitment/reason_coding.csv',records)
    save(FINAL/'recruitment/coding_rules.json',{'version':'HTT-RECRUITMENT-CUES-v2','positive_patterns':patterns,'negation_pattern':deny,
        'target':'Registry-reported recruitment difficulty among stopped trials; not objective recruitment failure or clinical causation.',
        'unknown_not_negative':True,'all_stopped_trials':len(records)})
    summary=[]
    for phase in PHASES:
        rr=[r for r in records if r['phase']==phase and r['status']=='TERMINATED']
        summary.append({'phase':phase,'terminated_n':len(rr),'reason_present':sum(bool(r['why_stopped_verbatim']) for r in rr),
            'explicit_recruitment_coded':sum(r['code']=='EXPLICIT_RECRUITMENT_DIFFICULTY' for r in rr),
            'mention_review':sum(r['code']=='RECRUITMENT_MENTION_REVIEW_REQUIRED' for r in rr)})
    write_csv(FINAL/'recruitment/phase_summary.csv',summary)
    bars('recruitment_by_phase','Explicit recruitment difficulty in recorded stopping reasons','Terminated records only. Rule-coded text, not independently adjudicated failure labels.',
         [LABELS[r['phase']] for r in summary],[r['explicit_recruitment_coded'] for r in summary])
    return {'stopped_total':len(records),'nonblank_reasons':sum(bool(r['why_stopped_verbatim']) for r in records),
        'status_code_counts':{s:dict(Counter(r['code'] for r in records if r['status']==s)) for s in ['TERMINATED','WITHDRAWN']}}


def main():
    if (FINAL/'analysis/results.json').exists():raise SystemExit('Completed results preserved; no automatic overwrite.')
    for name in ['analysis','modeling','recruitment','integration','simulation','poster/figures','poster/_build','reports']:(FINAL/name).mkdir(parents=True,exist_ok=True)
    pins=verify_sources();save(FINAL/'reports/source_preservation_manifest.json',pins)
    studies,designs,interventions,leads=load_current();allrows=[studies[n] for n in sorted(studies)];app=[s for s in allrows if s['phase']!='NA'];na=[s for s in allrows if s['phase']=='NA']
    assert len(app)==1319 and len(na)==1505
    phase=[status_row([s for s in allrows if s['phase']==p],'phase',p) for p in PHASES]
    write_csv(FINAL/'analysis/phase_status_full.csv',phase);write_csv(FINAL/'analysis/phase_status_applicable.csv',phase[:-1])
    bars('phase_distribution_full','Recorded phases across all 2,824 trials','Exact source categories, with combined phases retained.',[LABELS[r['value']] for r in phase],[r['n'] for r in phase],[2824]*8)
    bars('phase_distribution_applicable','All 1,319 trials with applicable phase','Not Applicable excluded only for this separately defined analysis.',[LABELS[r['value']] for r in phase[:-1]],[r['n'] for r in phase[:-1]],[1319]*7)
    stacked('phase_status_full','Recorded operational outcomes across all phases','Full cohort. A snapshot proportion is not prospective individual risk.',phase,[LABELS[r['value']] for r in phase])
    stacked('phase_status_applicable','Recorded outcomes in all phase-classified trials','n=1,319. Completed, Terminated and Withdrawn remain separate.',phase[:-1],[LABELS[r['value']] for r in phase[:-1]])
    types=sorted({r['intervention_type'] for rr in interventions.values() for r in rr});typetrials={t:{n for n,rr in interventions.items() if any(r['intervention_type']==t for r in rr)} for t in types}
    composition=[];itstatus=[];itapp=[]
    for t in types:
        nct=typetrials[t];count=len(nct&{s['nct_id'] for s in na});composition.append({'intervention_type':t,'na_trials':count,'denominator':1505,'percent':100*count/1505,'nonexclusive':True})
        itstatus.append(status_row([studies[n] for n in sorted(nct)],'intervention_type',t));itapp.append(status_row([studies[n] for n in sorted(nct) if studies[n]['phase']!='NA'],'intervention_type',t))
    write_csv(FINAL/'analysis/na_intervention_composition.csv',composition);write_csv(FINAL/'analysis/intervention_status_full.csv',itstatus);write_csv(FINAL/'analysis/intervention_status_applicable.csv',itapp)
    bars('na_intervention_composition','What Phase Not Applicable trials investigate','All 1,505 NA trials. Multiple registered types per trial; percentages can sum above 100%.',
         [r['intervention_type'].replace('_',' ').title() for r in composition],[r['na_trials'] for r in composition],[1505]*len(types))
    stacked('intervention_status_full','Intervention types and recorded status','All 2,824 eligible records considered. Types overlap; do not add category counts.',itstatus,[t.replace('_',' ').title() for t in types])
    drug_na=[s for s in na if s['nct_id'] in typetrials['DRUG']];drugcases=[];exercise=[]
    exercise_pattern=r'\bexercise\w*|\brehabilitat\w*|\baerobic\b|\bresistance training\b|\bphysical (?:training|activit)\w*|\byoga\b|\btai chi\b'
    for n,s in sorted(studies.items()):
        for r in interventions[n]:
            if re.search(exercise_pattern,r['name'],re.I):exercise.append({'nct_id':n,'phase':s['phase'],'intervention_type':r['intervention_type'],'intervention_name':r['name'],'source_record_id':r['id'],'source_table':'interventions.txt','rule':'LEXICAL_NAME_CUE_NOT_CLINICAL_TAXONOMY'})
    for s in drug_na:
        n=s['nct_id'];rr=interventions[n];drugcases.append({'nct_id':n,'title':s['brief_title'],'phase':s['phase'],'study_type':s['study_type'],
            'drug_names':'; '.join(r['name'] for r in rr if r['intervention_type']=='DRUG'),
            'drug_source_record_ids':';'.join(r['id'] for r in rr if r['intervention_type']=='DRUG'),
            'intervention_types':';'.join(sorted({r['intervention_type'] for r in rr})),
            'primary_purpose':designs.get(n,{}).get('primary_purpose',''),'allocation':designs.get(n,{}).get('allocation',''),
            'interpretation':'Registered NA retained; individual regulatory/design rationale not adjudicated.'})
    write_csv(FINAL/'analysis/na_drug_trial_audit.csv',drugcases);write_csv(FINAL/'analysis/exercise_rehabilitation_cues.csv',exercise)
    sponsor=[];design=[]
    for cls in sorted({r['agency_class'] for rr in leads.values() for r in rr}):sponsor.append(status_row([s for s in allrows if any(r['agency_class']==cls for r in leads[s['nct_id']])],'lead_agency_class',cls))
    for field in ['allocation','masking','primary_purpose','intervention_model']:
        for val in sorted({designs.get(s['nct_id'],{}).get(field,'') or 'MISSING' for s in allrows}):
            design.append(status_row([s for s in allrows if (designs.get(s['nct_id'],{}).get(field,'') or 'MISSING')==val],field,val))
    write_csv(FINAL/'analysis/sponsor_status.csv',sponsor);write_csv(FINAL/'analysis/design_status.csv',design)
    stacked('sponsor_status','Lead-sponsor class and recorded status','All 2,824 trials. Agency class does not measure funding amount.',sponsor)
    stacked('allocation_status','Registered allocation and recorded status','Current snapshot categories, not guaranteed registration-time covariates.',[r for r in design if r['field']=='allocation'])
    characteristics=[]
    for s in allrows:
        n=s['nct_id'];d=designs.get(n,{})
        characteristics.append({**s,'intervention_types':';'.join(sorted({r['intervention_type'] for r in interventions[n]})),
            'lead_sponsor_classes':';'.join(sorted({r['agency_class'] for r in leads[n]})),**{f:d.get(f,'') for f in ['allocation','masking','primary_purpose','intervention_model']}})
    write_csv(FINAL/'analysis/all_trial_characteristics.csv',characteristics)
    # Separate phase-classified enrollment summary. Actual is not relabeled planned.
    enroll=[];duration=[]
    for p in PHASES:
        for kind in ['ACTUAL','ESTIMATED','']:
            rr=[s for s in allrows if s['phase']==p and s['enrollment_type']==kind];vals=[num(s['enrollment']) for s in rr];vals=[v for v in vals if v is not None]
            enroll.append({'phase':p,'enrollment_type':kind,'n_records':len(rr),'n_numeric':len(vals),'median':float(np.median(vals)) if vals else '', 'q1':float(np.percentile(vals,25)) if vals else '', 'q3':float(np.percentile(vals,75)) if vals else ''})
    write_csv(FINAL/'analysis/enrollment_full.csv',enroll);write_csv(FINAL/'analysis/enrollment_applicable.csv',[r for r in enroll if r['phase']!='NA'])
    for s in allrows:
        st=q.interval(s['start_month_year']);en=q.interval(s['completion_month_year'])
        duration.append({'nct_id':s['nct_id'],'phase':s['phase'],'start_type':s['start_date_type'],'completion_type':s['completion_date_type'],
            'start_raw':s['start_month_year'],'completion_raw':s['completion_month_year'],'duration_lower_days':(en[0]-st[1]).days if st and en else '',
            'duration_upper_days':(en[1]-st[0]).days if st and en else '', 'both_actual_types':s['start_date_type']=='ACTUAL' and s['completion_date_type']=='ACTUAL',
            'interpretation':'Recorded start/end interval; not original planned duration or a validated delay label.'})
    write_csv(FINAL/'analysis/recorded_duration_intervals.csv',duration)
    f=Plot('Enrollment among phase-classified trials','Current ACTUAL enrollment medians and interquartile ranges. Not original planned enrollment.')
    vals=[r for r in enroll if r['phase']!='NA' and r['enrollment_type']=='ACTUAL'];mx=max(r['q3'] for r in vals)
    for i,r in enumerate(vals):
        y=280+i*170;f.text(90,y,LABELS[r['phase']],34);x=lambda v:850+1400*np.log1p(v)/np.log1p(mx)
        f.line(x(r['q1']),y+30,x(r['q3']),y+30,'#098A88',15);f.line(x(r['median']),y+5,x(r['median']),y+55,'#122B45',5)
        f.text(2350,y+10,f"median {r['median']:g}, n={r['n_numeric']}",28)
    f.text(850,1570,'Horizontal position uses log1p enrollment; line Q1-Q3, mark median.',29);f.save('enrollment_applicable')
    families={r['nct_id']:r['family_id'] for r in rows(ROOT/'gnn_graphrag/protocols/HTT-GNN-ASSOC-PROTOCOL-v2/family_groups.csv')}
    adjusted_results={name:adjusted(group,name,designs,interventions,leads,families) for name,group in [('full2824',allrows),('phase1319',app)]}
    recruit=recruitment(studies)
    result={'dataset':'HTT-P1-AACT-20260905','snapshot':'2026-09-05','n_full':len(allrows),'n_phase_applicable':len(app),'n_not_applicable':len(na),
        'all_interventional':all(s['study_type']=='INTERVENTIONAL' for s in allrows),'status_counts':dict(Counter(s['overall_status'] for s in allrows)),
        'phase_applicable_status':dict(Counter(s['overall_status'] for s in app)),
        'na_drug_trials':len(drug_na),'na_drug_only':sum(r['intervention_types']=='DRUG' for r in drugcases),'na_drug_mixed':sum(r['intervention_types']!='DRUG' for r in drugcases),
        'na_drug_primary_purposes':dict(Counter(r['primary_purpose'] for r in drugcases)),
        'exercise_cue_trials_all':len({r['nct_id'] for r in exercise}),'exercise_cue_trials_na':len({r['nct_id'] for r in exercise if r['phase']=='NA'}),
        'missingness':{f:sum(not s.get(f) for s in allrows) for f in ['phase','enrollment','enrollment_type','start_month_year','completion_month_year','number_of_arms']},
        'designs_missing':2824-len(designs),'adjusted':adjusted_results,'recruitment':recruit,
        'no_new_predictive_model_in_this_script':True}
    save(FINAL/'analysis/results.json',result)
    for p,h in pins['protected_sha256'].items():assert sha(ROOT/p)==h,p
    save(FINAL/'analysis/output_manifest.json',{'source_pins':'../reports/source_preservation_manifest.json','outputs':{str(p.relative_to(FINAL)):sha(p) for directory in [FINAL/'analysis',FINAL/'recruitment',FINAL/'poster/figures'] for p in directory.iterdir() if p.is_file() and p.suffix not in ['.py']},'protected_unchanged':True})
    # Display the already serialized result; numpy booleans need not be encoded twice.
    print((FINAL/'analysis/results.json').read_text())


if __name__=='__main__':main()
