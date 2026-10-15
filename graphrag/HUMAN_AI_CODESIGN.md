# Verified Human–AI co-design iteration

1. **Initial human design decision.** The human required a minimal GraphRAG
   demonstration built on fixed, parameterized, read-only Cypher rather than
   LLM-generated Cypher. Phase 1 had to preserve relationship paths, exact trial
   identifiers, planned-outcome identifiers, and dataset provenance.
2. **AI recommendation.** The AI recommended keeping retrieval and generation
   as separate modules, passing only the user question and retrieved graph
   evidence to the model, and adding a post-generation grounding gate rather
   than relying on prompt instructions alone.
3. **Human evaluation.** After Phase 1 returned verified results and nine tests
   passed, the human explicitly accepted Phase 1 as complete and required Phase
   2 to reuse `retrieve.py` and the existing parameterized queries without
   rewriting or replacing them. The human also required abstention, citations,
   and preservation of raw evidence and answers.
4. **Revised implementation.** Phase 2 adds only `generate_answer.py`. It uses
   the unchanged retrieval API, sends structured evidence to the LLM, and blocks
   model output that introduces unsupported NCT/source-record identifiers or
   omits dataset, snapshot, or planned-outcome safeguards. This preserves the
   human-approved graph semantics while making generation auditable.

Verification consists of the unchanged Phase 1 tests plus mocked LLM tests for
prompt isolation, citations, abstention, unsafe-output blocking, trace contents,
and credential exclusion.

## Provider iteration

1. **Initial human decision.** Phase 2 initially allowed a simple API model but
   required the pipeline not to assume that an API key existed.
2. **AI recommendation.** OpenAI Responses was retained as an optional provider
   with strict post-generation grounding validation.
3. **Human evaluation and modification.** The human confirmed that no OpenAI
   key was available and independently verified local Ollama 0.40.3 with
   `qwen2.5:1.5b`, including a successful planned-outcome safeguard response.
4. **Revised implementation.** Ollama is now the default and requires no API
   credential. OpenAI remains optional. Because the local model has 1.5B
   parameters, its prompt uses a compact identifier-preserving evidence view,
   while the trace retains the complete raw Neo4j result for audit.

## Grounding and provenance refinement

1. **Initial human design decision.** The complete local pipeline had to cite
   NCT IDs, source-record identifiers, dataset version, and snapshot date, and
   it had to state exactly that registered planned outcomes are not observed
   clinical results.
2. **Observed AI limitation.** In the first live run, `qwen2.5:1.5b` explained
   the retrieved trial evidence reasonably but omitted the required
   source-record citations, snapshot date, and exact safeguard. The grounding
   gate correctly blocked the answer after its bounded correction attempt.
3. **Human evaluation and modification.** The human required provenance to be
   derived deterministically from retrieved KG evidence while keeping the LLM
   responsible only for the explanatory prose. The human also required that
   deterministic citations must never legitimize unsupported model claims.
4. **Revised implementation.** The pipeline validates the model's substantive
   prose before attaching a clearly labeled evidence/provenance section built
   from the retrieval payload. A subsequent live review showed that strict
   word-level matching rejected harmless forms such as `PHASE4` versus
   `Phase 4` and `Six minute` versus `six-minute`. The human therefore refined
   the design again: validation now canonicalizes case, hyphenation, punctuation,
   and whitespace; accepts ordinary headings and connective prose; and focuses
   on retrieved identifiers, named sponsors/interventions/conditions/outcome
   measures, numeric values, treatment-effect claims, and termination reasons.
   Missing metadata or unsupported factual assertions still produce an
   abstention. Traces retain the raw model output, deterministic section, both
   validation layers, and timing data.

This validator is intentionally conservative and is not represented as a
general semantic-entailment model. Its limitations are recorded in each trace.

## Deadline-focused demonstration pass — October 15, 2026

The final focused pass kept Neo4j retrieval and the fixed Cypher unchanged,
reduced the prompt to a 2–3 sentence request, capped Ollama at 150 output
tokens, disabled repair attempts, and constructed trial facts, identifiers,
citations, provenance, and the planned-outcome safeguard deterministically.
It corrected the two known false positives for `SHA256` numeric parsing and
planned-outcome metadata headings. The final automated result was 29 passing
tests.

The single authorized live Question 1 run retrieved the verified graph and
generated locally, but publication remained blocked. The model ignored the
concise-format request and emitted metadata bullets until the 150-token cap.
`Intervention ID` and `Intervention Type` were then misclassified as invented
intervention assertions even though both values were present in the retrieved
evidence. The safe abstention was retained. Per the human stop rule, Questions
2 and 3 were not run and no automatic repair or additional live retry occurred.
The audit trace is
`graphrag/results/graphrag_demo_20261015T003131313741Z.json`.
