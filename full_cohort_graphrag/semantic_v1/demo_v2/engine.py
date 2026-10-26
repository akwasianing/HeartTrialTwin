"""Bounded candidate examination; unchanged ranking and read-only retrieval."""
import time
import urllib.request
from datetime import datetime, timezone

from full_cohort_graphrag.src import retrieve as api, generate_answer as g
from full_cohort_graphrag.src.prepare_evidence import prepare_evidence
from ..bridge import RankingWorker, validate_ranking
from ..pipeline import route, NOTICE
from ..identity import SemanticError, require, check_k
from . import VERSION
from .facts import factual_answer

OLLAMA_TIMEOUT = 60
MAX_SCAN = 10


class BoundedOllama:
    """Original constrained generation/validation, one shorter transport deadline.

    No free-form synthesis is certified by the existing validator. This optional
    mode retains its exact catalog-ID explanation methodology without weakening
    it, adding retries, or relabeling selected facts as clinical interpretation.
    """
    def __init__(self, contract, *, opener=None):
        self.opener = opener or urllib.request.urlopen
        self.contract = contract

    def generate(self, question, prepared):
        def bounded_open(request, **_):
            return self.opener(request, timeout=OLLAMA_TIMEOUT)
        result = g.OllamaAnswerGenerator(contract=self.contract, urlopen=bounded_open).generate(question, prepared)
        result['generation'].update(timeout_seconds=OLLAMA_TIMEOUT,
                                    transport_policy='Demo-v2: one attempt, 60-second socket timeout')
        result['answer_origin'] = 'OLLAMA_CONSTRAINED_CATALOG_EXPLANATION'
        if 'OLLAMA_CONNECTION_OR_TIMEOUT_FAILURE' in result['validation']['errors']:
            result['answer'] = ('ABSTAIN: Local Ollama was unavailable or exceeded the 60-second request bound. '
                                'No retry or unsupported model answer was published. Verified evidence remains below. '
                                'You may explicitly run the deterministic mode instead.')
        return result


class Demonstration:
    def __init__(self, retriever, *, ranker=None, generator=None):
        self.retriever = retriever
        self.contract = retriever.contract
        self.ranker = ranker or RankingWorker()
        self.generator = generator

    def run(self, question, *, candidate_count=2, scan_limit=5, answer_mode='deterministic', progress=None):
        start = time.perf_counter()
        trace = {'schema_version': VERSION, 'question': question, 'status': 'ABSTAIN', 'answer': '',
                 'started_utc': datetime.now(timezone.utc).isoformat(), 'answer_mode': answer_mode,
                 'dataset_version': api.DATASET, 'graph_version': api.GRAPH, 'snapshot_date': api.SNAPSHOT,
                 'ranking': None, 'trial_results': [], 'skipped_candidates': [], 'selected_nct_ids': [],
                 'errors': [], 'notice': NOTICE, 'model_attempts': 0,
                 'selection': {'requested': candidate_count, 'scan_limit': scan_limit, 'examined': 0,
                               'rank_order_changed': False, 'candidate_universe': 2824},
                 'validation': {'source_grounding_passed': False, 'semantic_association_confirmed': False}}
        def report(message):
            if progress:
                progress(message)
        def finish(error=None):
            if error:
                trace.update(status='ABSTAIN', answer='ABSTAIN: ' + error + ' Verified evidence, if any, is retained below.')
                trace['errors'].append(error)
            trace['elapsed_seconds'] = round(time.perf_counter() - start, 6)
            return trace
        try:
            require(answer_mode in ('deterministic', 'ollama'), 'Unsupported answer mode')
            check_k(candidate_count, 3)
            check_k(scan_limit, MAX_SCAN)
            require(scan_limit >= candidate_count, 'Scan budget must cover the requested candidate count')
            selected = route(question)
            trace['route'] = selected
            semantic = selected['mode'] == 'SEMANTIC_CANDIDATES'
            if semantic:
                require(answer_mode == 'deterministic', 'Discovery publishes complete deterministic evidence, not an LLM interpretation')
                report('Verifying pinned MiniLM artifacts and ranking 2,824 trials (local CPU).')
                result = self.ranker.rank(selected['query_text'], scan_limit)
                trace['ranking'] = validate_ranking(result, scan_limit, self.contract.membership)
                candidates = result['ranked_trials']
            else:
                candidates = [{'nct_id': selected['ids'][0], 'rank': None, 'similarity': None}]
            report('Verifying the pinned read-only Neo4j database identity.')
            self.retriever.verify_connection()
            for candidate in candidates:
                nct = candidate['nct_id']
                report(f'Retrieving registered evidence for {nct}.')
                raw = self.retriever.trial_profile(nct, limit=200, offset=0)
                require(raw.get('nct_id') == nct, 'Retrieved trial does not match selected NCT ID')
                prepared = prepare_evidence(raw, contract=self.contract)
                require(prepared['scope']['selected_nct_ids'] == [nct], 'Prepared trial association mismatch')
                evidence_question = f'What planned outcomes were registered for {nct}?' if semantic else question
                answer = factual_answer(evidence_question, prepared, contract=self.contract)
                # No automatic fallback after a model failure. Deterministic mode
                # is the explicit default, not a repair of untrusted model prose.
                if answer_mode == 'ollama' and answer['validation']['passed'] and answer['status'] != 'COMPLETE_LISTING':
                    report('Optional local Ollama explanation: one attempt, at most 60 seconds for the request.')
                    answer = (self.generator or BoundedOllama(self.contract)).generate(question, prepared)
                trace['model_attempts'] += answer['generation']['attempts']
                item = {'nct_id': nct, 'original_rank': candidate['rank'], 'similarity': candidate['similarity'],
                        'raw_retrieval': raw, 'prepared_evidence': prepared, 'evidence_question': evidence_question,
                        'answer_trace': answer, 'published': False}
                trace['trial_results'].append(item)
                trace['selection']['examined'] += 1
                if not answer['validation']['passed']:
                    reasons = answer['validation']['errors']
                    if not semantic:
                        finish('; '.join(reasons))
                        trace['answer'] = answer['answer'] + '\n' + NOTICE
                        return trace
                    trace['skipped_candidates'].append({'nct_id': nct, 'original_rank': candidate['rank'],
                        'similarity': candidate['similarity'], 'reasons': reasons,
                        'meaning': 'Evidence unavailable/incomplete for this listing, not proof of no registered measure or clinical relevance.'})
                    continue
                trace['selected_nct_ids'].append(nct)
                if len(trace['selected_nct_ids']) >= (candidate_count if semantic else 1):
                    break
            trace['selection']['unexamined_ranked_candidates'] = len(candidates) - trace['selection']['examined']
            if not trace['selected_nct_ids']:
                return finish('No candidate with complete, citation-verified requested evidence was found within the scan budget; absence is not established.')
            accepted = [r for r in trace['trial_results'] if r['answer_trace']['validation']['passed']]
            for item in accepted:
                item['published'] = True
            trace['validation']['source_grounding_passed'] = True
            if semantic:
                enough = len(accepted) == candidate_count
                trace['status'] = 'GROUNDED_CANDIDATE_EVIDENCE' if enough else 'PARTIAL_CANDIDATE_EVIDENCE'
                header = (f'Semantic discovery: {len(accepted)} of {candidate_count} requested evidence-backed candidates, '
                          f'after examining {trace["selection"]["examined"]} ranked trials (budget {scan_limit}). '
                          'This is not a search of every trial\'s outcome records. Similarity does not establish '
                          'clinical equivalence or ownership of the query measure. Skipped candidates remain in the original ranking.\n\n')
                trace['selection']['requested_candidate_count_met'] = enough
            else:
                trace['status'] = accepted[0]['answer_trace']['status']
                header = ''
            trace['answer'] = header + '\n\n'.join(r['answer_trace']['answer'] for r in accepted) + '\n' + NOTICE
            return finish()
        except SemanticError as exc:
            return finish(str(exc))
        except Exception:
            return finish('Neo4j, MiniLM, evidence validation or generation failed safely; check local services and private configuration. No raw service error is displayed.')
