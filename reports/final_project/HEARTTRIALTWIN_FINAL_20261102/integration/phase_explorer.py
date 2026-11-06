"""Opt-in phase/intervention explorer over verified CSVs; zero network/model calls."""
import argparse, csv, hashlib, json, re, sys, time
from pathlib import Path

FINAL=Path(__file__).resolve().parents[1]
ROOT=FINAL.parents[2]
sys.path.insert(0,str(ROOT))
from reports.challenge4.ai_design.pilot_v1.run_pilot import CsvEvidence
from full_cohort_graphrag.semantic_v1.demo_v2.facts import factual_answer


class PhaseExplorer:
    def __init__(self):
        self.source=CsvEvidence()  # Reuses verified source hashes and original evidence contract.

    def search(self,phase=None,intervention_type=None,limit=20):
        if type(limit) is not int or not 1<=limit<=50:raise ValueError('Limit must be 1–50')
        phases=sorted({r['phase'] for r in self.source.trials.values()})
        types=sorted({r['intervention_type'] for r in self.source.nodes['Intervention'].values()})
        if phase is not None and phase not in phases:raise ValueError('Unknown registered phase')
        if intervention_type is not None and intervention_type not in types:raise ValueError('Unknown registered intervention type')
        records=[]
        for nct,trial in sorted(self.source.trials.items()):
            iv=[r for r in self.source.records[nct] if r['category']=='interventions']
            matches=[r for r in iv if intervention_type is None or r['properties']['intervention_type']==intervention_type]
            if (phase is None or trial['phase']==phase) and (intervention_type is None or matches):
                records.append({'nct_id':nct,'title':trial['brief_title'],'phase':trial['phase'],
                    'intervention_types':sorted({r['properties']['intervention_type'] for r in iv}),
                    'match_evidence_ids':[r['evidence_id'] for r in matches],
                    'match_source_references':[ref for r in matches for ref in r['source_references']],
                    'trial_source_record_id':trial['source_record_id']})
        return {'mode':'OFFLINE_PINNED_CSV','dataset_version':'HTT-P1-AACT-20260905',
            'graph_version':'HTT-KG-AACT-20260905-FULL2824-v1','snapshot_date':'2026-09-05',
            'filters':{'phase':phase,'intervention_type':intervention_type},'total':len(records),'returned':min(len(records),limit),
            'has_more':len(records)>limit,'records':records[:limit],
            'interpretation':'Exact registered categories, not a semantic or clinical-effectiveness ranking.'}

    def answer(self,question):
        started=time.perf_counter()
        if not isinstance(question,str) or not question.strip() or len(question)>2000:raise ValueError('Question must be 1–2000 characters')
        ids=sorted(set(re.findall(r'\bNCT\d{8}\b',question.upper())))
        if len(ids)!=1:
            return {'status':'ABSTAIN','answer':'ABSTAIN: Request exactly one valid NCT identifier. No semantic substitution was made.',
                    'model_attempts':0,'mode':'OFFLINE_PINNED_CSV'}
        prepared=self.source.prepared(ids[0],limit=200)
        trace=factual_answer(question,prepared,contract=self.source.contract)
        return {'question':question,'mode':'OFFLINE_PINNED_CSV_NOT_LIVE_NEO4J','nct_id':ids[0],
            'status':trace['status'],'answer':trace['answer'],'model_attempts':trace['generation']['attempts'],
            'evidence_count':prepared['evidence_record_count'],'prepared_evidence':prepared,
            'answer_trace':trace,'elapsed_seconds':time.perf_counter()-started,
            'risk_estimate':'NOT_PROVIDED: current registered facts are not historical predictor profiles.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('answer');a.add_argument('question')
    b=s.add_parser('search');b.add_argument('--phase');b.add_argument('--intervention-type');b.add_argument('--limit',type=int,default=20)
    args=p.parse_args();explorer=PhaseExplorer()
    result=explorer.answer(args.question) if args.action=='answer' else explorer.search(args.phase,args.intervention_type,args.limit)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
