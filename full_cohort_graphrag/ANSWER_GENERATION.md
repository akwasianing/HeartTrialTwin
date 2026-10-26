# Full-cohort answer generation — Step 2 (offline-tested)

`src/generate_answer.py` consumes **only** the output of the existing
`prepare_evidence()` adapter. It performs no retrieval, database access,
environment loading, or automatic trace saving. Existing retrieval and evidence
preparation files are unchanged. The catalog-ID v2 interface has been tested
offline only. Earlier v1 live attempts and traces are preserved; they do not
establish that the new interface succeeds live.

## Use

From the repository root, in the existing GraphRAG environment:

```python
import json
from pathlib import Path
from full_cohort_graphrag.src.generate_answer import OllamaAnswerGenerator, save_trace

# This must be an actual saved prepare_evidence() output, not a raw response.
prepared = json.loads(Path("path/to/prepared_evidence.json").read_text())
client = OllamaAnswerGenerator()  # local contract validation; no network yet
# Explicit live call, only after separate approval / with Ollama already running:
trace = client.generate("What information is registered for NCT00206232?", prepared)
print(trace["answer"])
print(trace["deterministic_evidence_summary"])  # separate, not model prose
save_trace(trace, Path("full_cohort_graphrag/results/unique_generation_trace.json"))
```

The parent output directory must already exist. Saving uses exclusive creation:
existing files are never overwritten. There is no database-connected CLI or
answer-generation integration in the retriever. Nothing runs merely on import.

## Step 65B — explicit deterministic complete outcome listing

For a supported registered planned-outcome question naming **exactly one NCT
ID**, use the separate offline entry point. The prepared bundle must also be
scoped to that one trial; no extra trials or evidence pages are silently filtered.

```python
from full_cohort_graphrag.src.list_planned_outcomes import list_registered_planned_outcomes

trace = list_registered_planned_outcomes(
    "What planned outcomes were registered for NCT00206232?", prepared
)
print(trace["status"])  # COMPLETE_LISTING or ABSTAIN
print(trace["answer"])
```

This makes **no Ollama or Neo4j request**, requires no running model or database,
and does not read credentials. It reads the local pinned contract to revalidate
the prepared evidence (an already loaded contract can be supplied). It is not
automatically called by `OllamaAnswerGenerator.generate()` after failure and is
not a retry, repair, or fallback. The model's original three-ID response schema,
selection checks, and `INCOMPLETE_TRIAL_BOUND_LISTING` failure remain unchanged.

The function reuses the existing question classifier and prepared-evidence
validator, requires complete source coverage, then selects **all** source-bound
planned-outcome catalog facts. It verifies exact evidence-ID set equality and
uniqueness against the supplied records and their coverage totals, plus each
fact's measure and trial/source/path/version-bound citation. It renders original
catalog sentences in evidence-ID order, preserving registered measures, outcome
types and available time frames, with the planned-outcome and snapshot warnings.
A missing/blank measure blocks the whole listing. Missing optional outcome types
or time frames remain unchanged in structured records and are explicitly marked
unavailable in the readable answer; they are never filled in. No clinical result,
equivalence, benefit, or ranking is inferred from the listing order.

**Output policy:** at most **200 outcome records** and **50,000 UTF-8 bytes** for
the complete rendered listing, including its header, citations, provenance and
disclaimers. `max_outcomes=` and `max_answer_bytes=` may lower, but not raise,
these hard caps. A listing exceeding either cap returns `ABSTAIN` with
`LISTING_OUTPUT_LIMIT_EXCEEDED`, empty `listed_outcomes` and no published outcome
IDs. It never truncates. The fixed abstention notice and separately retained
audit evidence are outside the listing-byte cap. No pagination is performed:
even a final page remains insufficient when earlier pages are absent.

New traces use `HTT-FULL-DETERMINISTIC-OUTCOMES-v1` and
`HTT-FULL-COMPLETE-OUTCOME-LISTING-v1`, with
`answer_origin=DETERMINISTIC_VERIFIED_EVIDENCE`, `model_generated=false`,
`raw_model_output=null`, zero model attempts, and no invented token usage.
`listed_outcomes` retains exact source records plus fact IDs and original catalog
sentences; `validation` records expected/listed evidence-ID sets and citations.
The original prepared bundle, its hashes, source references and deterministic
summary remain separate and unchanged. `save_trace()` can save this trace with
the same exclusive, non-overwriting behavior. Only `COMPLETE_LISTING` represents
a successfully validated full listing; `ABSTAIN` never carries a partial list.

This is complete only for the **supplied pinned record**, not all registry
versions or all 2,824 trials. Snapshot values may contain amendments. Like the
existing adapter, validation establishes internal consistency, not independent
authentication of a self-consistent forged response. Questions outside the
declared grammar, multi-trial listings, and semantic clinical interpretation
remain unsupported. All Step 65B testing is offline; no new live retrieval or
model run is required or claimed.

## Method and explicit limitations

- One POST to loopback-only `http://localhost:11434/api/generate`, using
  `qwen2.5:1.5b`, temperature **0**, context **8192**, output limit **150**, timeout
  **180 seconds**, streaming disabled. No repair, retry, model download, or
  fallback provider. Model identity and completion metadata must match.
- This conservative first wrapper implements **constrained extractive
  explanations**, not free-form clinical interpretation. The unchanged
  `build_fact_catalog()` supplies the original exact sentences and trial-bound
  metadata. `build_fact_id_catalog()` sorts those sentences lexicographically
  and numbers them `F001`, `F002`, etc. The same catalog, regardless of dictionary
  insertion order, produces the same mapping. IDs are **local to that catalog**,
  not permanent global IDs: changing the evidence/scope can reindex them. The
  full mapping and its SHA-256 are retained with each trace.
- The LLM receives `fact_catalog` mapping IDs to their authorized sentences,
  including `[cite:...]` references, plus source identifiers and provenance.
  It returns **only** `{"fact_ids": ["F001"]}` (1–3 distinct existing IDs) or
  `{"abstain": true}`. One relevant fact is sufficient. Old `sentences` replies,
  combined keys, extra prose/fields, false/nonboolean abstention, malformed or
  duplicate-key JSON, invalid counts/types, unknown IDs and duplicate IDs are
  rejected. No stripping, normalization, filtering, deduplication or repair is
  performed. Unknown IDs invalidate the entire selection, even alongside valid IDs.
- Only after **all** raw IDs pass structural/membership validation does code
  resolve them to their original exact sentences, retaining model-selected order.
  The original sentence-grounding and listing-completeness validator still runs;
  the LLM no longer needs to reproduce long citation strings. The ID mapping is
  checked against the original catalog before resolution. Resolved facts preserve
  NCT IDs, evidence IDs and citations; full relationship/source provenance stays
  in prepared evidence and source references. Sentences retain exact source values.
  Accepted sentences are labeled selected registered facts, not an exhaustive
  listing. Deterministic formatting, evidence summaries, and citations are not
  represented as independently LLM-authored analyses.
- The catalog is **trial/path-bound**, not a global entity bag. A sponsor that
  occurs elsewhere is not evidence of a relationship to a different trial.
  Citations must support the exact field and trial. Novel prose, invented
  associations, incorrect citations, effectiveness/results claims, and inferred
  clinical equivalence cannot be introduced by model prose: such response fields
  are rejected, and no generated wording replaces the original sentences.
  The legacy `validate_output()` remains an internal sentence-grounding helper;
  live generation uses `validate_fact_selection()`, which rejects old sentence
  response envelopes.
- **Relevance is not solved by IDs.** The prompt requires question-relevant facts
  or abstention. Existing question-versus-retrieval NCT scope checks remain, and
  selected facts outside a question's explicitly named NCT IDs are now rejected.
  But there is no general semantic relevance/answer-completeness validator: a
  supported fact may still be irrelevant to a question about a different field or
  unsupported clinical findings. `validation.relevance.status=NOT_ESTABLISHED`
  reports this limitation, including when source grounding passes. `GROUNDED`
  and `validation.passed` mean source/selection checks passed, **not** independently
  verified relevance. Human review must assess whether the selected facts answer
  the question; do not present catalog membership as proof that they do.
- For search/comparison, any generated sponsor/outcome listing must cover that
  entire category for the supplied subset, or it is rejected. This prevents the
  earlier incomplete Q2 listing from being treated as complete. With only three
  selected facts, larger lists may not be expressible even though the shorter ID
  response fits 150 tokens; the full deterministic evidence remains separate.
  Unsupported Q3-style universal similarities or
  clinical generalizations are not allowed. No claim of resolving the original
  live model's limitations is made from mocked tests.
- Prepared evidence is round-tripped through the public, offline adapter before
  model use to check all original associations, citations, hashes, source identity,
  summary, scope, and completeness. This checks internal consistency against
  the pinned contract; it is not independent authentication of a self-consistent
  forged retrieval response. Trusted retrieval/source records remain essential.
- Pagination (including a final page with missing earlier pages), nonexistent
  trials, or **any** missing source category stop generation before a model call.
  This is intentionally conservative: even a browse-condition gap blocks a profile
  explanation although other facts may be available. Optional blank fields remain
  visible in prepared evidence and are never filled in. Questions naming an NCT
  outside the supplied subset also abstain without retrieval.
- The prompt includes every catalog fact and every source-record identifier,
  with dataset/graph/snapshot identity supplied once. Repetitive citation path
  properties are compacted in the prompt; full paths remain in the trace.
  Descriptions/population are not model claim fields in this first wrapper.
  A **24,000 UTF-8 byte** system/prompt/schema budget is an engineering bound,
  not a tokenizer-measured guarantee. If exceeded, the wrapper abstains rather
  than trimming facts or pretending a subset is complete. Long profiles or the
  complete 12-trial heart-failure/spironolactone search can exceed this bound.
  Reported prompt-token counts that leave insufficient output headroom also
  block publication. This does not prove the server never truncated an input;
  absent/limited backend telemetry and the lack of a local Qwen tokenizer remain
  a live-validation limitation. Only exact, source-backed sentences can publish
  even when the model may not have processed all the prompt text.
- The Ollama JSON schema retains the same object/array/string, closed `oneOf`
  branches and boolean `enum` constraints, replacing only the `sentences` property
  with `fact_ids`. No new schema keywords or dependencies were introduced.
  Uniqueness and membership are enforced in Python, not an assumed-supported
  `uniqueItems` or new grammar feature. The new response format has not been
  tested against the installed Ollama service; live compatibility remains unverified.
- Truncation, missing completion metadata, token-cap exhaustion, invalid model
  responses, and connection/timeouts produce controlled abstentions. The
  `ABSTAIN:` prefix does **not** whitelist the prose that follows: all such prose
  remains audit-only. Errors are safe fixed codes, not backend error strings.

Registered planned outcomes are not observed clinical results. September 5,
2026 snapshot values may include amendments; original-registration availability
is not asserted. The wrapper preserves the actual selected/returned trial scope,
not a claim that all 2,824 trials were examined.

## Trace and display contract

- Display **only** `answer` as model-result text. `status` is `GROUNDED` or
  `ABSTAIN`; invalid caller inputs raise `GenerationInputError` before generation.
- Display `deterministic_evidence_summary` separately and explicitly as verified
  evidence, not as the generated explanation. `verified_evidence` and
  `source_references` retain every adapter record/citation, including relationships,
  missingness, source identifiers, graph/dataset/snapshot identity, and pagination.
- `raw_model_output` is **audit-only**, including unsupported/truncated/abstention
  text. Never concatenate it with a published answer or treat deterministic
  citations as validation of that raw text.
- Versioned traces record the prepared-evidence and summary SHA-256 values,
  question, actual compact model input and prompt hash, schema/instruction hashes,
  settings, requested/actual model, completion reason, token usage and backend
  durations when provided, timestamps, measured latency, validation codes,
  accepted trial-bound facts and cited references. Unknown usage remains `null`;
  it is not estimated. Backend durations retain Ollama's nanosecond units, while
  wrapper latencies are labeled milliseconds. Timestamps/latency are naturally
  variable; source hashes, policy/settings and exact model input are reproducible.
  Temperature zero is not a promise of bit-identical local model outputs.
- New traces use `HTT-FULL-GENERATION-v2` and policy
  `HTT-FULL-CATALOG-ID-GROUNDING-v2`; `fact_catalog` uses
  `HTT-FULL-FACT-ID-CATALOG-v1` and records its ordering rule, hash and complete
  ID→sentence→metadata bindings. `validation.selected_fact_ids`,
  `validation.resolved_sentences`, `accepted_facts` (including fact IDs), and
  `citation_ids` record only fully validated selections. Failed selections remain
  in `raw_model_output` for diagnosis, never partially published. Raw v1 traces
  are not migrated or overwritten. Callers inspecting model JSON must now expect
  `fact_ids`, not `sentences`; `generate(question, prepared)` and the public
  `answer`/separate-evidence fields retain their calling convention.

## Offline tests

```bash
.venv-graphrag/bin/python -B -m unittest discover \
  -s full_cohort_graphrag/tests -p 'test_*.py' -v
```

Tests use checksum-verified pinned CSV fixtures and the existing fake driver;
HTTP calls are mocked and real driver creation is blocked. They exercise source
bindings, incomplete lists, unsupported claims, citations, abstention tails,
deterministic ID mappings, selection types/membership/duplicates, explicit-trial
scope, pagination/missing sources, context/truncation budgets, failures, trace
hashes, serialization, and non-overwriting saves. No additional dependencies are needed.
