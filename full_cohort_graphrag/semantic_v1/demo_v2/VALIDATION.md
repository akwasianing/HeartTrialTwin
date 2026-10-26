# Step 66G-4 — demonstration validation

**Disposition: ready for Step 66G-5 final project audit, within the documented
registered-evidence scope.** This is not a retrieval-performance benchmark,
clinical validation, or the final Challenge 3 report.

## Recovered work and implementation

The interrupted G-4 inspection had produced no confirmed demonstration code.
Existing G-2/G-3 code, traces, source data and research artifacts were preserved.
All additions are isolated under `semantic_v1/demo_v2/`:

- `facts.py`: complete deterministic answers, original catalog and validation.
- `engine.py`: original question routing, stable MiniLM ranking, bounded
  evidence-backed selection, optional bounded existing Ollama generation.
- `worker.py` / `client.py`: fixed subprocess boundary; private config remains
  in the existing Neo4j environment, not the Streamlit UI or command arguments.
- `app.py`: separate Streamlit entry point; no changes to older applications.
- `test_demo.py` / `test_app.py`: backend and UI regression checks.
- `smoke.py` / `ui_smoke.py`: explicit bounded read-only validation runners.
- `__init__.py`, `README.md`, this document, and versioned validation outputs.

No package installation, training, checkpoint change, Neo4j write, benchmark
evaluation, commit or push was performed.

## Latency diagnosis and changes

The previous title request spent **150.179 s** on **2,374 prompt tokens**, versus
**1.728 s** generating ten tokens; model loading took **9.902 s**. Prefill was
the dominant observed cost, not response length. The previous sponsor request
took **137.600 s** end to end; intervention generation timed out at **181.153 s**.

The default demonstration does not make a model request for source-exact fields.
It deterministically assembles original authorized catalog sentences and checks
trial-bound citations, source-set completeness, provenance, pagination and output
limits. This is not a cache of old answers or a fallback that publishes failed
model output. Outcome listings continue to use the unchanged original helper.

Optional Ollama retains the original constrained fact-ID methodology and all
validators, with a **60-second request/socket timeout**, one attempt, no repair
and no automatic retry. The old generator remains unchanged with its 180-second
setting. The UI backend separately bounds overall execution at **240 seconds**.
We did not claim a new faster or validated unrestricted synthesis model. No
Ollama inference was rerun for this milestone; availability and mocked timeout
behavior were verified. Server-side inference cancellation is not guaranteed
by the client timeout.

## Actual live smoke results

Four fixed cases, one attempt each, no generation calls. The original verification
probe confirmed the pinned local database identity, 28,777 nodes, 79,125
relationships, and current-user explicit node/relationship write denials. No
write probe was used. Ollama's configured model was available by metadata.

| Case | Status | Evidence | Seconds |
| --- | --- | ---: | ---: |
| Lead sponsor, NCT00206232 | GROUNDED; Baylor College of Medicine | 14 | 0.634078 |
| Intervention, NCT00206232 | GROUNDED; Spironolactone | 14 | 0.757853 |
| Planned outcomes, NCT00206232 | COMPLETE_LISTING; all 7 unique records | 14 | 2.279710 |
| Quality-of-life discovery | GROUNDED_CANDIDATE_EVIDENCE; 2 candidates selected after 3 examined | 28 + 6 + 11 | 25.092864 |

The sponsor result is approximately **137.6 → 0.63 seconds**; the intervention
changed from timeout/abstention to a verified deterministic answer in **0.76 s**.
These are separate observed functional runs, not repeated controlled latency
estimates or a claim of faster LLM inference. MiniLM cold process/model startup
still makes discovery noticeably slower than direct lookup.

Discovery preserved the exact ranking prefix:

| Original rank | NCT ID | Cosine | Evidence disposition |
| ---: | --- | ---: | --- |
| 1 | NCT00939146 | 0.4297686517 | Selected; 2 registered outcomes |
| 2 | NCT00012870 | 0.3900912106 | Skipped; missing planned-outcome records |
| 3 | NCT04715490 | 0.3846414089 | Selected; 4 registered outcomes |
| 4 | NCT03596359 | 0.3727539778 | Not examined; requested count reached |
| 5 | NCT05366686 | 0.3673866093 | Not examined; requested count reached |

No renumbering or benchmark ranking change occurred. All available skipped
candidate evidence and the exact skip reason are retained, not treated as a
clinical absence. The answer explicitly disclaims query ownership/clinical
equivalence. Source-bound citation audits passed for **15 facts** across these
four cases (1 sponsor, 1 intervention, 7 exact outcomes, 6 candidate outcomes).

Full traces, per-case evidence counts, source checks and manifest:
[validation/HTT-DEMO-v2-SMOKE-v1/summary.json](validation/HTT-DEMO-v2-SMOKE-v1/summary.json).

A fifth bounded check exercised the **actual Streamlit AppTest UI → fixed backend
subprocess → real read-only Neo4j** path, not a mock: `COMPLETE_LISTING`, seven
unique outcomes, **0** model attempts, **1.299269 s** client wall time, no UI
exceptions. Streamlit's loopback health endpoint returned `ok` at port 8502.
See [validation/ui_live_v1.json](validation/ui_live_v1.json). This is distinct from
the four mocked UI tests and not counted as an automated unit-test pass.

## Offline regression results

| Suite / environment | Passed | Failed |
| --- | ---: | ---: |
| Existing full-cohort retrieval, evidence, generation, listing / `.venv-graphrag` | 102 | 0 |
| Existing semantic integration / `.venv-graphrag` | 17 | 0 |
| New demonstration backend / `.venv-graphrag` | 22 | 0 |
| New mocked Streamlit UI / `.venv-full-system` | 4 | 0 |
| Existing MiniLM ranking / `.venv-vector-rag` | 12 | 0 |
| Existing GNN execution/diagnosis regression / `.venv-vector-rag` | 32 | 0 |
| **Distinct tests** | **189** | **0** |

Coverage includes exact routing, field/citation bindings, all seven outcome
records with types/time frames, unchanged ranked-ID mappings, skipped candidates,
partial scan budgets, checksum rejection, clinical-premise abstention, unknown
and malformed IDs, missing source categories, pagination, output caps,
Neo4j failure redaction, optional Ollama validation/timeouts, explicit return to
deterministic mode, backend deadlines and UI rendering. No frozen test-set
performance evaluation occurred.

Sandboxed UI checks emitted Streamlit bare-context and PyArrow CPU-query warnings;
they were non-fatal. Initial service/server attempts were sandbox-denied, then
the authorized checks/start worked outside the sandbox. These permission errors
were not represented as Neo4j or Ollama outages.

## Preservation, security and limitations

The smoke runner checked **51 protected research files**, **12 original semantic
files/results**, and **28 prior live-validation files** against their recorded
hashes before and after execution. No differences. This includes the pinned
protocol/feature/checkpoint/benchmark artifacts in that protection scope;
historical test truth was not used to configure the demo. The entire older
GraphRAG application and retriever remain unchanged.

The UI shows plain-text verified answers and audit evidence; raw model output is
not rendered as an answer. Credentials stay in the ignored private configuration.
The bounded smoke records passed an in-memory check for the actual password.
No public hosting/security audit is claimed. The application is local-only.

Limitations remain explicit: rigid single-field question grammar; no open-ended
scientific synthesis; strict all-category completeness can abstain despite a
usable requested field; profiles over 200 records need separate pagination work;
bounded discovery is not exhaustive; no guarantee of clinical equivalence or
complete relevant-trial recall; corpus fields may include later amendments.
GraphSAGE remains experimental, not the default model. No clinical effectiveness
or patient-outcome prediction is provided. Final audit should review these scope
limits and the actual UI/evidence before any deployment claim.

Screenshot capture instructions and exact launch/test commands are in
[README.md](README.md). No fabricated screenshots or final Challenge 3 report
were created.
