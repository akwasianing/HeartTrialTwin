"""Explicit Step 66G-3 runner: fixed sequential cases, no writes or retries.

Run only with owner authorization. No action occurs on import. Two clearly
labeled fault injections test handling without stopping either real service.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
from pathlib import Path
import signal
import time
import urllib.error
import urllib.request
from unittest.mock import Mock, patch

from full_cohort_graphrag.src import retrieve as api
from full_cohort_graphrag.src import generate_answer as generation
from full_cohort_graphrag.src.list_planned_outcomes import list_registered_planned_outcomes
from .identity import ROOT, require
from .pipeline import SemanticGraphRAG, save_trace

OUTPUT = ROOT/'full_cohort_graphrag/semantic_v1/live_validation/HTT-MINILM-GRAPHRAG-LIVE-v1'
CASES = (
    ('01_profile','What title is registered for clinical trial NCT00206232?','GROUNDED','ollama'),
    ('02_discovery','Find trials with registered planned outcomes about quality of life.','GROUNDED_CANDIDATE_EVIDENCE','semantic'),
    ('03_sponsor','Who is the lead sponsor of NCT00206232?','GROUNDED','ollama'),
    ('04_intervention','What intervention is registered for clinical trial NCT00206232?','GROUNDED','ollama'),
    ('05_outcomes','What planned outcomes were registered for NCT00206232?','COMPLETE_LISTING','neo4j'),
    ('06_effectiveness','Did spironolactone improve survival in NCT00206232?','ABSTAIN','offline'),
    ('07_unknown','What planned outcomes were registered for NCT99999999?','ABSTAIN','neo4j'),
    ('08_invalid','What planned outcomes were registered for NCT0020623?','ABSTAIN','offline'),
    ('09_missing_evidence','What planned outcomes were registered for NCT00000475?','ABSTAIN','neo4j'),
    ('10_neo4j_fault','What planned outcomes were registered for NCT00206232?','ABSTAIN','injected_neo4j'),
    ('11_ollama_fault','What title is registered for clinical trial NCT00206232?','ABSTAIN','injected_ollama'),
)


class CaseTimeout(BaseException):
    pass


def timeout_handler(*_):
    raise CaseTimeout()


def write(path,value):
    with Path(path).open('x',encoding='utf-8') as handle:
        handle.write(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n')


def probe():
    """Bounded service/ACL reads. Never return usernames, passwords or raw errors."""
    result = {}
    try:
        with api.FullCohortRetriever(api.load_config()) as retriever:
            verified = retriever.verify_connection()
            from neo4j import Query
            rows,_,_ = retriever.driver.execute_query(Query('SHOW USER PRIVILEGES',timeout=10),
                                                      database_=api.DATABASE,routing_='r')
            require(len(rows) <= 200,'Unexpected privilege volume')
            privileges = [{k:row.get(k) for k in ('access','action','resource','graph','segment')} for row in rows]
            denied = {r['segment'] for r in privileges if r['access']=='DENIED'
                      and r['action']=='write' and r['graph'] in ('*',api.DATABASE)}
            grants = [r for r in privileges if r['access']=='GRANTED']
            safe_actions = {'load','execute','access','match','read','traverse'}
            readonly = ({'NODE(*)','RELATIONSHIP(*)'} <= denied
                        and all(r['action'] in safe_actions for r in grants)
                        and any(r['action']=='match' and r['graph']==api.DATABASE for r in grants))
            result['neo4j'] = {'connected':True,'identity':verified,'read_only_verified':readonly,
                              'privilege_inspection':privileges,
                              'method':'SHOW USER PRIVILEGES; explicit global/target node and relationship write denials; no elevated write/admin grants; no write probe'}
    except Exception as exc:
        result['neo4j'] = {'connected':False,'read_only_verified':False,
            'error_type':type(exc).__name__,'error':'Connection, identity or privilege inspection failed; configuration details suppressed'}
    try:
        with urllib.request.urlopen('http://localhost:11434/api/tags',timeout=10) as response:
            raw = response.read(100001)
        require(len(raw) <= 100000,'Ollama metadata budget exceeded')
        data = json.loads(raw)
        models = [{k:r.get(k) for k in ('name','digest','size')} for r in data.get('models',[]) if r.get('name')==generation.MODEL]
        result['ollama'] = {'reachable':True,'configured_model':generation.MODEL,
                            'model_installed':bool(models),'matching_models':models}
    except Exception as exc:
        result['ollama'] = {'reachable':False,'model_installed':False,'configured_model':generation.MODEL,
            'error_type':type(exc).__name__,'errno':getattr(getattr(exc,'reason',None),'errno',None),
            'error':'Local Ollama metadata request failed; details suppressed'}
    return result


def audit(trace,contract):
    """Independently bind all published facts/listings back to live prepared data."""
    checked = []
    for item in trace.get('trial_results',[]):
        bundle, answer = item['prepared_evidence'], item['answer_trace']
        generation.validate_prepared(bundle,contract)
        require(bundle['scope']['selected_nct_ids']==[item['nct_id']],'Trial association mismatch')
        if answer['status'] not in ('COMPLETE_LISTING','GROUNDED'):
            continue
        require(answer['source_references']==bundle['citations'],'Source-reference mutation')
        indexed = generation.build_fact_id_catalog(generation.build_fact_catalog(bundle))
        references = {r['citation_id']:r for r in bundle['citations']}
        if answer['status']=='COMPLETE_LISTING':
            records = bundle['trials'][0]['categories']['planned_outcomes']
            by_id = {r['evidence_id']:r for r in records}
            listed = answer['listed_outcomes']
            require(len(listed)==len(by_id) and {r['evidence_id'] for r in listed}==set(by_id),'Incomplete/duplicate listing')
            facts = []
            for row in listed:
                source = by_id[row['evidence_id']]
                require(all(row[k]==value for k,value in source.items()),'Outcome source values changed')
                facts.append({**indexed[row['fact_id']]['fact'],'fact_id':row['fact_id'],'sentence':row['sentence']})
            require(answer['generation']['attempts']==0,'Deterministic listing used model')
        else:
            facts = answer['validation']['accepted_facts']
        require(bool(facts),'Successful answer has no facts')
        for fact in facts:
            entry = indexed[fact['fact_id']]
            require({k:v for k,v in fact.items() if k not in ('fact_id','sentence')}==entry['fact']
                    and fact['sentence']==entry['sentence'] and fact['sentence'] in answer['answer'], 'Published fact/catalog mismatch')
            require(fact['nct_id']==item['nct_id'],'Cross-trial fact')
            for key in fact['citation_ids']:
                ref = references[key]
                require(ref['nct_id']==fact['nct_id'] and ref['evidence_id']==fact['evidence_id']
                        and ref['dataset_version']==api.DATASET and ref['graph_version']==api.GRAPH
                        and ref['snapshot_date']==api.SNAPSHOT,'Invalid citation/source binding')
            checked.append({'nct_id':fact['nct_id'],'field':fact['field'],'value':fact['value'],
                            'evidence_id':fact['evidence_id'],'citation_ids':fact['citation_ids']})
        require(api.PLANNED_SAFEGUARD in answer['answer'] and api.SNAPSHOT_SAFEGUARD in answer['answer'],'Missing safeguard')
    successful = trace.get('status') in ('GROUNDED','COMPLETE_LISTING','GROUNDED_CANDIDATE_EVIDENCE')
    return {'citation_validity':'PASS' if successful and checked else 'NOT_APPLICABLE_NO_PUBLISHED_FACTS',
            'checked_facts':checked,'checked_fact_count':len(checked),
            'method':'Exact catalog/fact/record equality, trial-specific citation bindings and live prepared-evidence round-trip; not clinical equivalence validation'}


def run(destination=OUTPUT):
    destination = Path(destination)
    destination.mkdir(parents=True,exist_ok=False)
    logging.getLogger('neo4j').setLevel(logging.CRITICAL)
    # Preserve the existing frozen files; this hashes train/validation only, no test truth.
    old = json.loads((ROOT/'gnn_graphrag/diagnostics/HTT-GNN-DIAG-66G1-v1/diagnostic_plan.json').read_text())['protected_files_before']
    require(all(api.sha256(ROOT/name)==value for name,value in old.items()),'Existing protected artifacts changed')
    write(destination/'plan.json',{'version':'HTT-MINILM-GRAPHRAG-LIVE-v1','authorization':'Project-owner Step 66G-3',
        'cases':[{'id':i,'question':q,'expected_status':s,'execution_type':k} for i,q,s,k in CASES],
        'semantic_top_k':2,'max_live_model_attempts':3,'attempts_per_case':1,
        'llm_timeout_seconds':180,'case_watchdog_seconds':240,'neo4j_query_timeout_seconds':30,
        'failure_injections_are_simulations':True,'retries':0,'test_benchmark':False})
    services = probe()
    write(destination/'services.json',services)
    db_available = services['neo4j'].get('connected') and services['neo4j'].get('read_only_verified')
    model_available = services['ollama'].get('reachable') and services['ollama'].get('model_installed')
    print(json.dumps({'event':'services','neo4j_read_only_verified':bool(db_available),'ollama_available':bool(model_available)}),flush=True)
    contract = api.load_contract()
    retriever = api.FullCohortRetriever(api.load_config(),contract=contract) if db_available else Mock(contract=contract)
    summaries = []
    try:
        for case_id,question,expected,kind in CASES:
            if (kind in ('neo4j','semantic','ollama','injected_ollama') and not db_available
                    or kind=='ollama' and not model_available):
                summaries.append({'id':case_id,'question':question,'result':'NOT_RUN','reason':'Required service or read-only authorization unavailable'})
                continue
            started = time.perf_counter()
            handler = signal.signal(signal.SIGALRM,timeout_handler)
            signal.alarm(240)
            try:
                if kind=='injected_neo4j':
                    with patch.object(retriever,'verify_connection',side_effect=api.RetrievalError('Injected Neo4j outage; no real service changed')):
                        trace = SemanticGraphRAG(retriever).run(question)
                elif kind=='injected_ollama':
                    opener = Mock(side_effect=urllib.error.URLError('Injected transport failure'))
                    generator = generation.OllamaAnswerGenerator(contract=contract,urlopen=opener)
                    trace = SemanticGraphRAG(retriever,generator=generator).run(question)
                else:
                    trace = SemanticGraphRAG(retriever).run(question,top_k=2)
                trace['validation_execution_type'] = 'FAULT_INJECTION' if kind.startswith('injected') else 'LIVE_SERVICES' if kind!='offline' else 'LOCAL_POLICY_ONLY'
                checked = audit(trace,contract)
                trace['independent_live_audit'] = checked
                require(trace['status']!='ABSTAIN' or not trace['validation']['source_grounding_passed'],'Abstention published unsupported facts')
                if kind=='ollama' and any('TIMEOUT' in e or 'CONNECTION' in e for row in trace['trial_results'] for e in row['answer_trace']['validation']['errors']):
                    model_available = False  # No piling further requests on a possibly busy/unavailable server.
                expected_error = {'06_effectiveness':'Unsupported question','07_unknown':'NOT_FOUND',
                                  '08_invalid':'Invalid NCT','09_missing_evidence':'MISSING_SOURCE_RECORDS',
                                  '10_neo4j_fault':'failed safely','11_ollama_fault':'OLLAMA_CONNECTION_OR_TIMEOUT_FAILURE'}.get(case_id)
                passed = (trace['status']==expected and (not expected_error or expected_error in ' '.join(trace['errors'])))
                summary = {'id':case_id,'question':question,'result':'PASS' if passed else 'FAIL',
                    'expected_status':expected,'actual_status':trace['status'],'execution_type':trace['validation_execution_type'],
                    'retrieval_method':trace.get('route',{}).get('mode','POLICY_REJECTION'),
                    'retrieved_trial_ids':[r['nct_id'] for r in trace['trial_results']],
                    'evidence_counts':{r['nct_id']:r['prepared_evidence']['evidence_record_count'] for r in trace['trial_results']},
                    'citation_validity':checked['citation_validity'],'checked_fact_count':checked['checked_fact_count'],
                    'source_completeness':{r['nct_id']:r['prepared_evidence']['completeness'] for r in trace['trial_results']},
                    'model_attempts':sum(r['answer_trace']['generation']['attempts'] for r in trace['trial_results']),
                    'elapsed_seconds':time.perf_counter()-started,'errors':trace['errors'],'trace_file':case_id+'.json'}
                save_trace(trace,destination/(case_id+'.json'))
            except CaseTimeout:
                model_available = False if kind=='ollama' else model_available
                summary = {'id':case_id,'question':question,'result':'TIMEOUT','elapsed_seconds':time.perf_counter()-started,
                           'error':'240-second watchdog; no retry; no answer published'}
            except Exception as exc:
                summary = {'id':case_id,'question':question,'result':'FAIL','error_type':type(exc).__name__,
                           'error':'Runner audit failed; details suppressed','elapsed_seconds':time.perf_counter()-started}
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM,handler)
            summaries.append(summary)
            write(destination/(case_id+'_summary.json'),summary)
            print(json.dumps({'event':'case','id':case_id,'result':summary['result'],
                              'status':summary.get('actual_status'),'seconds':summary['elapsed_seconds']}),flush=True)
    finally:
        if db_available:
            retriever.__exit__(None,None,None)
    require(all(api.sha256(ROOT/name)==value for name,value in old.items()),'Protected artifacts changed during live validation')
    write(destination/'summary.json',{'version':'HTT-MINILM-GRAPHRAG-LIVE-v1','cases':summaries,
        'protected_files_unchanged':len(old),'pass_count':sum(s['result']=='PASS' for s in summaries),
        'fail_count':sum(s['result'] in ('FAIL','TIMEOUT') for s in summaries),
        'not_run_count':sum(s['result']=='NOT_RUN' for s in summaries),
        'service_checks':'services.json','test_benchmark_run':False,'production_code_modified':False})
    hashes = {p.name:api.sha256(p) for p in sorted(destination.iterdir()) if p.is_file()}
    write(destination/'manifest.json',{'version':'HTT-MINILM-GRAPHRAG-LIVE-v1','files_sha256':hashes,
                                     'runner_sha256':api.sha256(Path(__file__))})


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true',required=True,help='Explicitly allow authorized bounded live service calls')
    parser.parse_args()
    run()
