"""Record actual offline functionality, not a live Neo4j/Ollama claim."""
import json,time
from pathlib import Path
from phase_explorer import PhaseExplorer,FINAL

def main():
    dest=FINAL/'integration/verified_examples.json'
    if dest.exists():raise SystemExit('Existing demonstration preserved.')
    t=time.perf_counter();e=PhaseExplorer();load=time.perf_counter()-t
    questions=['Who is the lead sponsor of NCT00206232?',
               'What intervention is registered for clinical trial NCT00206232?',
               'What planned outcomes were registered for NCT00206232?',
               'Did spironolactone improve survival in NCT00206232?',
               'What planned outcomes were registered for NCT99999999?',
               'What planned outcomes were registered for NCT00000475?']
    results=[e.answer(q) for q in questions]
    assert [r['status'] for r in results]==['GROUNDED','GROUNDED','COMPLETE_LISTING','ABSTAIN','ABSTAIN','ABSTAIN']
    assert len(results[2]['answer_trace']['listed_outcomes'])==7
    assert all(r['model_attempts']==0 for r in results)
    searches=[e.search('PHASE2','DRUG',20),e.search('NA','DEVICE',20),e.search('NA','DRUG',20)]
    dest.write_text(json.dumps({'schema':'HTT-FINAL-OFFLINE-DEMO-v1','mode':'OFFLINE_PINNED_CSV_NOT_LIVE_NEO4J',
        'source_initialization_seconds':load,'examples':results,'searches':searches,'runtime_seconds':time.perf_counter()-t},indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'statuses':[r['status'] for r in results],'outcomes':7,'model_calls':0,'search_totals':[s['total'] for s in searches],
        'initialization_seconds':load,'total_seconds':time.perf_counter()-t},indent=2))

if __name__=='__main__':main()
