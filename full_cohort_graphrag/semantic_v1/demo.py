"""Explicit opt-in command-line demonstration; defaults to offline validation."""
import argparse
import json
from pathlib import Path

from .bridge import RankingWorker
from .identity import SemanticError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Explicitly allow read-only Neo4j and supported local Ollama calls')
    parser.add_argument('--question')
    parser.add_argument('--top-k',type=int,default=3)
    parser.add_argument('--env-file',type=Path)
    parser.add_argument('--output',type=Path,help='New JSON trace path; existing files are never overwritten')
    args = parser.parse_args(argv)
    if args.output and args.output.exists():
        parser.error('Output already exists; no calls made')
    if not args.live:
        if args.question:
            parser.error('Question execution requires explicit --live; default is artifact validation only')
        try:
            result = RankingWorker().call({'operation':'validate'})
            print(json.dumps(result,indent=2))
            return 0
        except SemanticError:
            print('Offline artifact validation failed; inspect the documented environment and pinned files.')
            return 1
    if not args.question:
        parser.error('--live requires --question')
    from full_cohort_graphrag.src.retrieve import FullCohortRetriever, load_config
    from .pipeline import SemanticGraphRAG, save_trace, route
    try:
        # Reject unsupported questions before constructing a live driver.
        route(args.question)
        with FullCohortRetriever(load_config(args.env_file)) as retriever:
            result = SemanticGraphRAG(retriever).run(args.question,top_k=args.top_k)
        if args.output:
            save_trace(result,args.output)
        print(result['status'])
        print(result['answer'])
        return 0 if result['validation']['source_grounding_passed'] else 2
    except Exception:
        print('Request failed safely. Verify supported question syntax, read-only Neo4j configuration and local dependencies.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
