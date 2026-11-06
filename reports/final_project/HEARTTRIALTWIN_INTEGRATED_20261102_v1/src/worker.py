"""Bounded JSON worker for offline evidence and research-only saved inference."""
import json,os,sys,time
os.environ.update(PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
from identity import *

def execute(request):
    require(type(request) is dict,'Request must be an object')
    action=request.get('action')
    fields={'profiles':{'action'},'scenario':{'action','nct_id','planned_enrollment','acknowledge'},
        'answer':{'action','question'},'search':{'action','phase','intervention_type','limit'},'compare':{'action','nct_ids'}}
    require(action in fields and set(request)==fields[action],'Unsupported action or unexpected fields')
    if action in {'profiles','scenario'}:
        from inference import ResearchInference
        model=ResearchInference()
        return model.profiles() if action=='profiles' else model.score(request['nct_id'],planned_enrollment=request['planned_enrollment'],acknowledge=request['acknowledge'])
    verify_base();legacy_paths()
    from phase_explorer import PhaseExplorer
    explorer=PhaseExplorer()
    if action=='answer':return explorer.answer(request['question'])
    if action=='search':return explorer.search(request['phase'],request['intervention_type'],request['limit'])
    ids=request['nct_ids']
    require(type(ids) is list and 1<=len(ids)<=3 and all(isinstance(n,str) for n in ids) and len(set(ids))==len(ids),'Compare one to three distinct trial IDs')
    results=[explorer.answer(f'What planned outcomes were registered for {n}?') for n in ids]
    return {'status':'COMPLETE_COMPARISON' if all(r['status']=='COMPLETE_LISTING' for r in results) else 'PARTIAL_COMPARISON',
        'mode':'OFFLINE_PINNED_CSV','nct_ids':ids,'trial_results':results,'source_associations_preserved':True,
        'interpretation':'Independent registered outcome lists; no inferred clinical equivalence or treatment effect.'}

def main():
    started=time.perf_counter()
    try:
        raw=sys.stdin.buffer.read(16001);require(len(raw)<=16000,'Input limit exceeded')
        result=execute(json.loads(raw));result['worker_elapsed_seconds']=time.perf_counter()-started
    except (ValueError,KeyError,TypeError) as exc:
        # Input/integrity messages are authored policy text; no raw network/driver errors.
        result={'status':'ABSTAIN','error_code':'INPUT_OR_INTEGRITY_REJECTED','answer':'Request rejected by the research input or source-integrity policy.',
            'diagnostic_type':type(exc).__name__,'worker_elapsed_seconds':time.perf_counter()-started}
    except Exception:
        result={'status':'ABSTAIN','error_code':'LOCAL_BACKEND_FAILURE','answer':'Local evidence or model environment unavailable. No answer or score fabricated.',
            'worker_elapsed_seconds':time.perf_counter()-started}
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))

if __name__=='__main__':main()
