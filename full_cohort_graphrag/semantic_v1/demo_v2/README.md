# HeartTrialTwin — MiniLM + GraphRAG demonstration v2

Separate, opt-in Step 66G-4 application. It does not replace the original
`semantic_v1/pipeline.py`, the earlier Streamlit applications, or any research
experiment. No training, corpus embedding regeneration or Neo4j writes occur.

## Launch with the existing environments

From Terminal:

```bash
cd "/Users/lovelaceashong/Desktop/Courses/Fall 2026/Project"
.venv-full-system/bin/python -B -m streamlit run full_cohort_graphrag/semantic_v1/demo_v2/app.py --server.address 127.0.0.1 --server.port 8502 --server.headless true --browser.gatherUsageStats false
```

Open <http://127.0.0.1:8502>. If this verified demo server is already running,
open that URL rather than launching a second server on the same port.

No additional installation is required in the inspected local setup:

- `.venv-full-system`: Streamlit **1.64.0** UI; no ML or Neo4j imports.
- `.venv-graphrag`: existing Neo4j **6.4.0** and private environment loading;
  a fixed subprocess runs `demo_v2.worker` for each submitted question.
- `.venv-vector-rag`: existing pinned MiniLM runtime, invoked by the original
  `RankingWorker` only for semantic discovery. This avoids NumPy/PyTorch ABI
  mixing across environments and does not reinstall or alter dependency pins.

The backend loads the existing ignored `full_cohort_graphrag/.env`, or the four
explicit `FULL_GRAPHRAG_NEO4J_*` environment settings. Keep the existing dedicated
read-only account and database `hearttrialtwin-full2824`. No credential entry,
credential display, Aura fallback, or importer credentials are used in the UI.
Do not publish private configuration or make this local research UI public
without a separate security/deployment review.

## Answer paths and limits

1. **Exact NCT:** existing anchored question classification and direct profile
   retrieval; semantic ranking is bypassed. Unknown or malformed identifiers are
   never replaced with a different trial.
2. **Verified facts:** `facts.factual_answer()` validates prepared evidence using
   the original round-trip checker, then publishes all requested catalog facts.
   NCT, field, evidence-ID set, trial-bound citations and dataset identity must
   agree. Titles, lead sponsors, interventions, conditions, phase and study type
   need no model call. Submitted/browse conditions remain distinct.
3. **Planned outcomes:** reuse the unchanged
   `list_registered_planned_outcomes()` complete-listing entry point. Measures,
   types, time frames and citations remain source-exact. All seven records for
   NCT00206232 are returned, not a model-selected subset.
4. **Semantic discovery:** unchanged cosine ranking over all **2,824** candidates
   using the checksum-verified 384-dimensional MiniLM features and revision
   `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. Request a prefix of five candidates
   by default; examine them in original rank order until two have complete
   requested evidence. Limits: 1–3 selected candidates, 1–10 examined candidates,
   with scan budget at least the requested count. Stop early on success. Ranks,
   scores and the benchmark universe are not changed. Each skip retains its
   original rank, score, evidence, and explicit reasons. Unexamined candidates
   are labeled. Similarity is **not** verified outcome ownership or clinical
   equivalence. This topic search ranks existing trial representations; it is
   not a comprehensive search of all 19,740 outcome texts.
5. **Optional Ollama:** advanced checkbox retains the original one-attempt,
   citation-validated catalog-ID explanation for supported exact-NCT fields.
   Default remains deterministic; outcome listings never use the model. The
   request timeout is **60 seconds** (original path remains 180). Model
   `qwen2.5:1.5b`, temperature 0, context 8192, output cap 150, prompt/schema and
   all original validation checks are retained. A failure abstains; it does not
   automatically retry, publish raw output, or silently fall back. Users may
   explicitly choose deterministic mode for a new request.

Ollama's retained methodology is **constrained extractive explanation**, not
free-form scientific synthesis. Open-ended synthesis and multi-intent questions
remain unsupported and abstain rather than bypassing relevance validation.
The optional path was tested with mocked responses/timeouts in this milestone;
its availability, not a fresh slow generation, was checked live.

Boundedness: profiles return at most 200 evidence records, complete answers at
most 50,000 UTF-8 bytes per trial; over-limit or paginated evidence abstains,
never truncates. The UI backend has a **240-second overall subprocess deadline**;
MiniLM's original worker retains its 180-second bound and Neo4j its 30-second
per-query bound. The Ollama 60-second value is a socket/request timeout, not a
server-side inference cancellation guarantee. Timed-out inference may continue
on Ollama; the UI makes no automatic retry.

The original conservative **all-source-category** completeness rule remains:
even a usable title may abstain when another source category is missing. Missing
records, nonexistent trials, pagination, output limits and insufficient scan
budgets are distinguished in retained evidence. If some complete candidates are
found but fewer than requested, `PARTIAL_CANDIDATE_EVIDENCE` publishes only those
complete trial listings and states the unmet count. No eligible candidates
means abstention, not evidence of absence.

## Demonstration questions

| Question / UI choice | Expected behavior |
| --- | --- |
| What title is registered for NCT00206232? | Deterministic cited title; no MiniLM/Ollama |
| Who is the lead sponsor of NCT00206232? | Baylor College of Medicine, trial-bound citation |
| What intervention is registered for clinical trial NCT00206232? | Spironolactone, trial-bound citation; no effectiveness claim |
| What planned outcomes were registered for NCT00206232? | Complete seven-record deterministic listing with types/time frames |
| Find trials with registered planned outcomes about quality of life. | Original ranks shown; missing-evidence skips recorded; complete candidate listings |
| Did spironolactone improve survival in NCT00206232? | Local policy abstention; no clinical-results inference |
| What planned outcomes were registered for NCT99999999? | Unknown-trial abstention; no semantic substitution |
| What planned outcomes were registered for NCT00000475? | Missing-source abstention, not a nonexistent-trial claim |

## Reproduce offline checks

```bash
.venv-graphrag/bin/python -B -m unittest discover -s full_cohort_graphrag/tests -p 'test_*.py' -q
.venv-graphrag/bin/python -B -m unittest full_cohort_graphrag.semantic_v1.test_pipeline full_cohort_graphrag.semantic_v1.demo_v2.test_demo -q
.venv-full-system/bin/python -B -m unittest full_cohort_graphrag.semantic_v1.demo_v2.test_app -q
.venv-vector-rag/bin/python -B -m unittest full_cohort_graphrag.semantic_v1.test_ranking gnn_graphrag.tests.test_full_cohort_diagnosis gnn_graphrag.tests.test_full_cohort_execution -q
```

These suites do not issue live service requests or retrain models. UI tests mock
the backend and label prior trace fixtures as rendering-only, not new live
results. Permission-related PyArrow CPU-probe and Streamlit bare-context warnings
were observed in sandboxed UI tests; no tests failed.

## Traces and evidence

The UI has a local JSON audit download; it does not overwrite old traces. It
shows verified answers as plain text, not executable HTML/Markdown from source
values. Raw model output is audit-only, never a published answer.

Actual bounded live checks are in
[validation/HTT-DEMO-v2-SMOKE-v1](validation/HTT-DEMO-v2-SMOKE-v1/summary.json).
Read [VALIDATION.md](VALIDATION.md) for measured results and preservation checks.
This is functional integration evidence, **not** a new ranking benchmark.

## Reproducible screenshot instructions

1. Launch/open the local application. Keep the research warning and snapshot
   caption visible. Select **Exact-NCT lookup**, NCT00206232, **lead sponsor**;
   click **Retrieve verified evidence**. Capture the answer, citation and status.
2. Select **planned outcomes**, run once, and capture the complete seven-record
   listing. Scroll for a second capture if necessary; expand selected evidence
   to show source-record citations and outcome types/time frames.
3. Select **Semantic discovery**, topic **quality of life**, default two selected
   candidates/scan budget five. Capture the original ranking table and expand
   **Skipped candidates and evidence limitations** to show rank 2's missing
   evidence. The successful selection is ranks 1 and 3, not a rewritten top-two
   ranking.
4. Use **Question input** for the unsupported survival question; capture the
   abstention. On macOS press **Shift–Command–4** to capture the relevant region.
   Do not include private Terminal/environment windows.

No screenshots are fabricated or claimed in this package. The UI was checked
with Streamlit AppTest, including one separately recorded live backend lookup.

## Research boundary

Dataset `HTT-P1-AACT-20260905`; graph
`HTT-KG-AACT-20260905-FULL2824-v1`; snapshot **2026-09-05**. Snapshot values may
include amendments and are not certified original-registration values.
Registered planned outcomes are not observed clinical results. The system does
not predict clinical effectiveness, patient outcomes, or treatment benefit.
GraphSAGE remains an experimental comparison; its checkpoint/results and the
frozen Version 2 protocol are unchanged. No test labels are read for serving,
candidate selection or configuration. No commit, push, or final report is part
of this step.
