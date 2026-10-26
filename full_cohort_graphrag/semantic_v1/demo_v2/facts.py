"""Complete, exact catalog facts; no language model or database access."""
import copy
import time

from full_cohort_graphrag.src import generate_answer as g, retrieve as api
from full_cohort_graphrag.src.list_planned_outcomes import list_registered_planned_outcomes

FIELDS = {
    'intervention': ('interventions', 'name'),
    'lead sponsor': ('lead_sponsors', 'name'),
    'submitted condition': ('submitted_conditions', 'name'),
    'browse condition': ('browse_conditions', 'name'),
}
METADATA = {'title': 'brief_title', 'study type': 'study_type', 'phase': 'phase'}


def factual_answer(question, prepared, *, contract, max_answer_bytes=50_000):
    """Publish ALL requested field facts only after full source/citation checks.

    Deliberately retains the existing strict all-category completeness policy,
    even when a different, unrequested category is missing. No partial fallback.
    """
    if type(max_answer_bytes) is not int or not 1 <= max_answer_bytes <= 50_000:
        raise g.GenerationInputError('Invalid answer byte limit')
    g.validate_prepared(prepared, contract)
    relevance = g.classify_question(question)
    if relevance['permitted_fields'] == ['planned outcome measure']:
        return list_registered_planned_outcomes(question, prepared, contract=contract,
                                               max_answer_bytes=max_answer_bytes)
    start = time.perf_counter()
    result = {'schema_version': 'HTT-DEMO-DETERMINISTIC-FACTS-v1',
              'answer_origin': 'DETERMINISTIC_VERIFIED_FACTS', 'model_generated': False,
              'status': 'ABSTAIN', 'answer': '', 'raw_model_output': None,
              'dataset_version': api.DATASET, 'graph_version': api.GRAPH, 'snapshot_date': api.SNAPSHOT,
              'source_references': copy.deepcopy(prepared['citations']),
              'prepared_evidence_sha256': g.digest(prepared),
              'deterministic_evidence_summary': prepared['summary'],
              'generation': {'provider': None, 'attempts': 0, 'maximum_attempts': 0},
              'validation': {'passed': False, 'errors': [], 'accepted_facts': [],
                             'expected_evidence_ids': [], 'citation_ids': [], 'relevance': relevance}}

    def finish(errors, facts=None):
        result['validation'].update(passed=not errors, errors=errors, accepted_facts=facts or [])
        if errors:
            result['answer'] = ('ABSTAIN: ' + ', '.join(errors) +
                                '. Verified evidence is retained separately; missing records do not prove absence.')
        result['total_latency_ms'] = round((time.perf_counter() - start) * 1000, 3)
        return result

    if (relevance['classification'] != 'CLASSIFIED' or len(relevance['requested_nct_ids']) != 1
            or relevance['requested_nct_ids'] != prepared['scope']['selected_nct_ids']):
        return finish(['QUESTION_SCOPE_OR_FIELD_UNSUPPORTED'])
    complete = prepared['completeness']
    if complete['not_found_nct_ids'] or prepared['retrieval_status'] == 'NOT_FOUND':
        return finish(['NOT_FOUND'])
    if complete['pagination_limited']:
        return finish(['PAGINATION_LIMITED'])
    if complete['missing_source_records']:
        return finish(['MISSING_SOURCE_RECORDS'])
    if not complete['complete_evidence']:
        return finish(['INCOMPLETE_EVIDENCE'])
    trial = prepared['trials'][0]
    nct = relevance['requested_nct_ids'][0]
    fields = relevance['permitted_fields']
    expected = set()
    for field in fields:
        if field in FIELDS:
            category, key = FIELDS[field]
            rows = trial['categories'][category]
            coverage = trial['coverage'][category]
            if (not rows or len(rows) != coverage['total'] or not coverage['all_evidence_returned']
                    or any(not r['properties'].get(key, '').strip() for r in rows)):
                return finish(['INCOMPLETE_RELEVANT_VALUES'])
            expected.update(r['evidence_id'] for r in rows)
        elif field not in METADATA or not trial['trial'].get(METADATA[field], '').strip():
            return finish(['INCOMPLETE_RELEVANT_VALUES'])
    catalog = g.build_fact_catalog(prepared)
    indexed = g.build_fact_id_catalog(catalog)
    facts = [dict(copy.deepcopy(entry['fact']), fact_id=key, sentence=entry['sentence'])
             for key, entry in indexed.items() if entry['sentence'] in g.question_catalog(catalog, relevance)]
    ids = [f['evidence_id'] for f in facts if f['evidence_id'] is not None]
    result['validation']['expected_evidence_ids'] = sorted(expected)
    if not facts or set(ids) != expected or len(ids) != len(expected):
        return finish(['FACT_SOURCE_SET_MISMATCH'])
    references = {r['citation_id']: r for r in prepared['citations']}
    for fact in facts:
        if fact['nct_id'] != nct or fact['sentence'] not in catalog or not fact['citation_ids']:
            return finish(['FACT_CITATION_MISMATCH'])
        for cid in fact['citation_ids']:
            ref = references.get(cid, {})
            if (ref.get('nct_id') != nct or ref.get('evidence_id') != fact['evidence_id']
                    or any(ref.get(k) != prepared[k] for k in
                           ('dataset_version', 'graph_version', 'snapshot_date', 'manifest_sha256'))):
                return finish(['FACT_CITATION_MISMATCH'])
    answer = '\n'.join(['Deterministically assembled from verified registered evidence — not model-generated.',
                        *[f['sentence'] for f in facts], api.PLANNED_SAFEGUARD, api.SNAPSHOT_SAFEGUARD,
                        f'Dataset: {api.DATASET}; graph: {api.GRAPH}; snapshot: {api.SNAPSHOT}.'])
    if len(answer.encode()) > max_answer_bytes:
        return finish(['OUTPUT_LIMIT_EXCEEDED'])
    result.update(status='GROUNDED', answer=answer)
    result['validation']['citation_ids'] = sorted({c for f in facts for c in f['citation_ids']})
    return finish([], facts)
