"""Opt-in candidate ranking -> existing verified GraphRAG, no baseline mutations."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from full_cohort_graphrag.src import retrieve as api
from full_cohort_graphrag.src.prepare_evidence import prepare_evidence
from full_cohort_graphrag.src.generate_answer import OllamaAnswerGenerator, classify_question
from full_cohort_graphrag.src.list_planned_outcomes import list_registered_planned_outcomes
from .identity import VERSION, SemanticError, check_k, check_text, require
from .bridge import RankingWorker, validate_ranking

SEMANTIC_PATTERN = re.compile(r'Find trials with registered planned outcomes about (?P<measure>[^\r\n]{1,500}?)\.?',re.I)
NOTICE = ('Experimental registered-association retrieval, not clinical advice. Similarity proposes candidates; '
          'it does not verify ownership of the query measure or clinical effectiveness.')


def route(question):
    check_text(question)
    tokens = re.findall(r'\bnct\w*',question,re.I)
    if any(not re.fullmatch(r'NCT\d{8}',token,re.I) for token in tokens):
        raise SemanticError('Invalid NCT identifier; no semantic substitution performed')
    ids = sorted({token.upper() for token in tokens})
    if ids:
        require(len(ids) == 1, 'This opt-in entry point supports one explicit NCT ID at a time')
        relevance = classify_question(question)
        require(relevance['classification'] == 'CLASSIFIED' and relevance['requested_nct_ids'] == ids,
                'Unsupported question: only declared registered-fact fields are available, not clinical results or termination reasons')
        return {'mode':'EXACT_NCT','ids':ids,'relevance':relevance}
    match = SEMANTIC_PATTERN.fullmatch(question.strip())
    require(match is not None, 'Use an exact-NCT registered-field question or: Find trials with registered planned outcomes about <measure>')
    measure = match['measure'].strip()
    check_text(measure)
    return {'mode':'SEMANTIC_CANDIDATES','query_text':measure}


class SemanticGraphRAG:
    def __init__(self, retriever, *, ranker=None, generator=None):
        self.retriever = retriever
        self.contract = retriever.contract
        self.ranker = ranker or RankingWorker()
        self.generator = generator  # Created only for a supported non-listing question.

    def run(self, question, *, top_k=3):
        started = time.perf_counter()
        trace = {'schema_version':VERSION,'question':question,'status':'ABSTAIN','answer':'',
                 'answer_origin':None,'ranking':None,'trial_results':[],
                 'dataset_version':api.DATASET,'graph_version':api.GRAPH,'snapshot_date':api.SNAPSHOT,
                 'manifest_sha256':api.MANIFEST_SHA256,'notice':NOTICE,
                 'started_utc':datetime.now(timezone.utc).isoformat(),'errors':[],
                 'validation':{'source_grounding_passed':False,'semantic_association_confirmed':False}}
        def finish(error=None):
            if error:
                trace['status'] = 'ABSTAIN'
                trace['errors'].append(error)
                trace['answer'] = 'ABSTAIN: '+error+' No unsupported answer is published.'
            trace['elapsed_seconds'] = time.perf_counter()-started
            return trace
        try:
            check_k(top_k,5)  # Engineering bound, not tuned for ranking performance.
            selected = route(question)
            trace['route'] = selected
            if selected['mode'] == 'EXACT_NCT':
                ids = selected['ids']
            else:
                result = self.ranker.rank(selected['query_text'],top_k)
                trace['ranking'] = validate_ranking(result,top_k,self.contract.membership)
                ids = [v['nct_id'] for v in result['ranked_trials']]
            # Explicit NCTs never use or fall back to semantic search.
            self.retriever.verify_connection()
            for nct in ids:
                response = self.retriever.trial_profile(nct,limit=200,offset=0)
                require(response.get('nct_id') == nct, 'Retrieved profile does not match requested candidate')
                prepared = prepare_evidence(response,contract=self.contract)
                require(prepared['scope']['selected_nct_ids'] == [nct], 'Prepared trial association mismatch')
                if selected['mode'] == 'SEMANTIC_CANDIDATES' or selected['relevance']['permitted_fields'] == ['planned outcome measure']:
                    evidence_question = (question if selected['mode'] == 'EXACT_NCT' else
                                         f'What planned outcomes were registered for {nct}?')
                    result = list_registered_planned_outcomes(evidence_question,prepared,contract=self.contract)
                    origin = 'DETERMINISTIC_VERIFIED_EVIDENCE'
                else:
                    evidence_question = question
                    generator = self.generator or OllamaAnswerGenerator(contract=self.contract)
                    result = generator.generate(question,prepared)
                    origin = 'OLLAMA_CATALOG_SELECTION'
                trace['trial_results'].append({'nct_id':nct,'raw_retrieval':response,
                    'prepared_evidence':prepared,'evidence_question':evidence_question,
                    'evidence_question_is_derived':evidence_question != question,'answer_trace':result})
                if result['status'] not in ('COMPLETE_LISTING','GROUNDED') or not result['validation']['passed']:
                    return finish('Verified evidence is unavailable or insufficient: '+', '.join(result['validation']['errors']))
                require(all(ref['nct_id'] == nct for ref in result['source_references']), 'Citation trial mismatch')
            trace['validation']['source_grounding_passed'] = True
            if selected['mode'] == 'SEMANTIC_CANDIDATES':
                trace['status'] = 'GROUNDED_CANDIDATE_EVIDENCE'
                trace['answer_origin'] = 'DETERMINISTIC_CANDIDATE_EVIDENCE'
                header = ('Semantic candidates, not verified query-to-trial associations. '
                          'The following are each candidate\'s complete registered records; '
                          'not a claim that their measures match the query clinically.\n')
            else:
                trace['status'] = trace['trial_results'][0]['answer_trace']['status']
                trace['answer_origin'] = origin
                header = ''
            trace['answer'] = header+'\n\n'.join(v['answer_trace']['answer'] for v in trace['trial_results'])+'\n'+NOTICE
            return finish()
        except SemanticError as exc:
            return finish(str(exc))
        except Exception:
            # Raw driver/generator exceptions can contain private configuration.
            return finish('Retrieval, evidence preparation or generation failed safely; inspect local configuration and source coverage')


def save_trace(trace, path):
    path = Path(path)
    with path.open('x',encoding='utf-8') as handle:
        handle.write(json.dumps(trace,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
