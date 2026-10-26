"""One fixed JSON request in the existing Neo4j environment; no shell or secrets output."""
import json
import logging
import sys

from full_cohort_graphrag.src import retrieve as api
from ..pipeline import route
from .engine import Demonstration


def execute(request):
    if not isinstance(request, dict) or set(request) != {'question', 'candidate_count', 'scan_limit', 'answer_mode'}:
        raise ValueError('Invalid demo request')
    route(request['question'])  # Unsupported clinical questions never open a driver.
    with api.FullCohortRetriever(api.load_config()) as retriever:
        return Demonstration(retriever).run(**request)


def main():
    logging.getLogger('neo4j').setLevel(logging.CRITICAL)
    try:
        raw = sys.stdin.read(16_385)
        if len(raw.encode()) > 16_384:
            raise ValueError('Request too large')
        result = execute(json.loads(raw))
    except Exception:
        result = {'status': 'ABSTAIN', 'answer': 'ABSTAIN: Unsupported question or local service/configuration failure. '
                  'Use a documented registered-field question. No unsupported answer was produced.',
                  'errors': ['REQUEST_OR_SERVICE_FAILURE'], 'trial_results': [], 'ranking': None,
                  'skipped_candidates': [], 'model_attempts': 0}
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
