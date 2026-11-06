"""Add final tables/figures without recomputing completed numerical analyses."""
import sys,json
from common import *


def main():
    if (FINAL/'analysis/supplement_manifest.json').exists():raise SystemExit('Completed supplement preserved.')
    pins=verify_sources();studies,designs,iv,leads=load_current();allrows=list(studies.values())
    sponsor_phase=[];design_phase=[]
    classes=sorted({r['agency_class'] for rr in leads.values() for r in rr})
    for p in PHASES:
        group=[s for s in allrows if s['phase']==p]
        for cls in classes:
            sponsor_phase.append({'phase':p,**status_row([s for s in group if any(r['agency_class']==cls for r in leads[s['nct_id']])],'lead_sponsor_class',cls)})
        for field in ['allocation','masking','primary_purpose','intervention_model']:
            for value in sorted({designs.get(s['nct_id'],{}).get(field,'') or 'MISSING' for s in allrows}):
                design_phase.append({'phase':p,**status_row([s for s in group if (designs.get(s['nct_id'],{}).get(field,'') or 'MISSING')==value],field,value)})
    write_csv(FINAL/'analysis/phase_sponsor_status.csv',sponsor_phase)
    write_csv(FINAL/'analysis/phase_design_status.csv',design_phase)
    calendar=[]
    for field in ['study_first_submitted_date','start_month_year']:
        for period in ['before_2000','2000_2009','2010_2016','2017_2020','2021_onward','MISSING']:
            group=[]
            for s in allrows:
                bounds=q.interval(s[field]);year=bounds[0].year if bounds else None
                key='MISSING' if year is None else 'before_2000' if year<2000 else '2000_2009' if year<2010 else '2010_2016' if year<2017 else '2017_2020' if year<2021 else '2021_onward'
                if key==period:group.append(s)
            calendar.append(status_row(group,field,period))
    write_csv(FINAL/'analysis/calendar_period_status.csv',calendar)
    dur=rows(FINAL/'analysis/recorded_duration_intervals.csv');dsummary=[]
    for p in PHASES:
        rr=[r for r in dur if r['phase']==p];valid=[r for r in rr if r['duration_lower_days'] and r['duration_upper_days']]
        actual=[r for r in valid if r['both_actual_types']=='True'];nonnegative=[r for r in actual if float(r['duration_lower_days'])>=0]
        vals=[(float(r['duration_lower_days'])+float(r['duration_upper_days']))/2 for r in nonnegative]
        dsummary.append({'phase':p,'all_trials':len(rr),'both_dates_parseable':len(valid),'both_types_actual':len(actual),
            'actual_negative_lower_bound':len(actual)-len(nonnegative),'actual_nonnegative':len(vals),
            'median_interval_midpoint_days':float(np.median(vals)) if vals else '',
            'meaning':'Descriptive midpoint of recorded date-precision bounds; not delay or original planned duration'})
    write_csv(FINAL/'analysis/duration_summary.csv',dsummary)
    recruitment=rows(FINAL/'recruitment/reason_coding.csv');rtypes=[]
    for t in sorted({r['intervention_type'] for rr in iv.values() for r in rr}):
        rr=[r for r in recruitment if any(x['intervention_type']==t for x in iv[r['nct_id']])]
        for status in ['TERMINATED','WITHDRAWN']:
            ss=[r for r in rr if r['status']==status]
            rtypes.append({'intervention_type':t,'status':status,'n':len(ss),'reason_present':sum(bool(r['why_stopped_verbatim']) for r in ss),
                'explicit_recruitment_coded':sum(r['code']=='EXPLICIT_RECRUITMENT_DIFFICULTY' for r in ss),
                'mention_review':sum(r['code']=='RECRUITMENT_MENTION_REVIEW_REQUIRED' for r in ss),'nonexclusive':True})
    write_csv(FINAL/'recruitment/intervention_summary.csv',rtypes)
    ledger=rows(FINAL/'modeling/eligibility_ledger_651.csv');six=[r for r in ledger if 'ACTUAL_COMPLETION_' in r['reasons']]
    write_csv(FINAL/'modeling/chronology_quarantine_six.csv',six)
    cohort=rows(FINAL/'modeling/analysis_cohort.csv');phasehist=[]
    for w in ['development','exploratory_temporal_evaluation']:
        for phase in sorted({q.phase_key(r['historical_phase']) for r in cohort}):
            rr=[r for r in cohort if r['window']==w and q.phase_key(r['historical_phase'])==phase]
            phasehist.append({'window':w,'phase':phase,'n':len(rr),'completed':sum(r['y']=='0' for r in rr),'terminated':sum(r['y']=='1' for r in rr)})
    write_csv(FINAL/'modeling/phase_event_counts.csv',phasehist)
    m=json.loads((FINAL/'modeling/results.json').read_text());names=list(m['models']);pretty=['Intercept only','Phase only','Metadata without phase','Metadata with phase']
    f=Plot('Historical classification: phase adds no clear benefit','Exploratory 2019–2020 reassessment: n=228, 39 Terminated. Previously inspected period.',
        'Strict Terminated vs Completed. New models remain experimental; not ongoing-trial forecasts.')
    base=39/228;X=lambda z:900+4000*z
    for i,(name,label) in enumerate(zip(names,pretty)):
        y=360+i*230;v=m['models'][name]['exploratory_temporal_evaluation'];lo,hi=m['uncertainty']['model_intervals'][name]['auprc_average_precision']
        f.text(90,y,label,36);f.rect(900,y,4000*v['auprc_average_precision'],65,'#098A88');f.line(X(lo),y+105,X(hi),y+105,'#122B45',7)
        f.text(2400,y,f"AP {v['auprc_average_precision']:.3f}",32,True);f.text(2400,y+60,f"Brier {v['brier']:.4f}",29)
    f.line(X(base),300,X(base),1330,'#BC5A22',5);f.text(900,1430,f'Orange line: evaluation prevalence {base:.3f}. Lower lines: 95% family-bootstrap AP intervals.',29)
    f.text(900,1510,'AP = average precision (PR-AUC summary); larger is better. Brier: smaller is better.',29);f.save('historical_model_comparison')
    f=Plot('Phase associations remain uncertain after adjustment','All 1,319 phase-applicable trials; Terminated/Withdrawn composite. Phase 2 reference.',
        'Snapshot association, noncausal. Adjusted for year, drug presence, sponsor class, allocation and masking; residual confounding remains.')
    rr=[r for r in rows(FINAL/'analysis/adjusted_phase1319.csv') if r['parameter'].startswith('phase_')]
    x=lambda v:1250+600*np.log(float(v));f.line(x(1),260,x(1),1350,'#BC5A22',4)
    for i,r in enumerate(rr):
        y=320+i*165;f.text(90,y,LABELS[r['parameter'][6:]],34)
        f.line(x(r['cluster_95_lower']),y+35,x(r['cluster_95_upper']),y+35,'#098A88',10)
        f.rect(x(r['odds_ratio'])-12,y+22,24,26,'#122B45')
        f.text(2080,y+10,f"OR {float(r['odds_ratio']):.2f} [{float(r['cluster_95_lower']):.2f}, {float(r['cluster_95_upper']):.2f}]",31)
    f.text(800,1490,'Odds ratio on log scale; lines are cluster-robust 95% intervals.',31)
    f.text(800,1550,'Exploratory phase-block likelihood-ratio p=0.629; not evidence of phase equivalence.',31);f.save('adjusted_phase_associations')
    draw_architecture()
    for p,h in pins['protected_sha256'].items():assert sha(ROOT/p)==h,p
    save(FINAL/'analysis/supplement_manifest.json',{'protected_unchanged':True,'source_hashes_verified':len(pins['source_sha256']),
        'new_tables':['phase_sponsor_status.csv','phase_design_status.csv','calendar_period_status.csv','duration_summary.csv'],
        'figures':['historical_model_comparison','adjusted_phase_associations','integrated_architecture']})
    print('PASS: supplemental full-cohort tables, recruitment types, eligibility and three poster figures')


def draw_architecture():
    f=Plot('HeartTrialTwin: separate evidence, description and prediction','Historical risk-study inputs are separate from the current-snapshot graph.',
        'Registered planned outcomes are not observed clinical results. Scenario exploration remains conceptual.')
    boxes=[(100,300,800,300,'Pinned AACT evidence',['2,824 selected trials','2026-09-05 snapshot']),
           (1100,300,800,300,'Neo4j + MiniLM + GraphRAG',['28,777 nodes / 79,125 links','Citations + complete listings']),
           (2100,300,800,300,'Existing research interface',['Read-only Neo4j','Experimental; not clinical advice']),
           (100,1000,800,330,'Full-cohort analysis',['2,824 descriptive records','1,319 phase-applicable / 1,505 NA']),
           (1100,1000,800,330,'Historical AACT experiment',['47 dated extracts; 486 eligible','258 development / 228 reassessment']),
           (2100,1000,800,330,'New offline companion',['Phase / intervention filters','No individual risk or causal twin'])]
    for x0,y,w,h,title,lines in boxes:
        f.rect(x0,y,w,h,'#EDF5F5');f.text(x0+25,y+30,title,34,True)
        for j,line in enumerate(lines):f.text(x0+25,y+125+j*60,line,29)
    for x0,y,xx,yy in [(900,450,1100,450),(1900,450,2100,450),(500,600,500,1000),(1900,1160,2100,1160)]:
        f.line(x0,y,xx,yy,'#53616F',5)
        if xx>x0:f.line(xx-20,yy-15,xx,yy,'#53616F',5);f.line(xx-20,yy+15,xx,yy,'#53616F',5)
        else:f.line(xx-15,yy-20,xx,yy,'#53616F',5);f.line(xx+15,yy-20,xx,yy,'#53616F',5)
    f.text(150,1490,'Current snapshot analysis is NOT backfilled into historical predictors.',38,True)
    f.text(150,1570,'GraphSAGE remains an experimental comparison, not the default retrieval engine.',34);f.save('integrated_architecture')


if __name__=='__main__':main()
