# Step 66G-3 — bounded live integration validation, v1

**Disposition: conditional readiness for a constrained demonstration interface.**
The real Neo4j/MiniLM path, deterministic complete listing, and two live Ollama
answers worked. Top-two discovery could not publish a complete answer because a
candidate had no registered outcomes. Intervention generation timed out and
correctly abstained. Do not describe all generation scenarios as successful.

This is a functional integration check, **not** a new retrieval-performance
benchmark or the final Challenge 3 report. Registered planned outcomes are not
observed clinical results. September 5, 2026 snapshot values may include
amendments; original-registration availability and clinical efficacy are not
established.

## Services and safety

- Database: `hearttrialtwin-full2824`; live identity, SourceDataset, six label
  counts and seven relationship counts matched the checksum-pinned full-cohort
  manifest. **2,824 trials, 28,777 nodes, 79,125 relationships, 19,740 planned
  outcomes**. Dataset `HTT-P1-AACT-20260905`; graph
  `HTT-KG-AACT-20260905-FULL2824-v1`; snapshot `2026-09-05`.
- Read-only access was verified through current-user privilege metadata: explicit
  node and relationship `write` denials, target-graph MATCH access and no elevated
  write/admin grants in the returned privileges. **No write probe was attempted.**
  The fixed retrieval allowlist and explicit database selection were unchanged.
  Inspection used the documented [Neo4j privilege listing](https://neo4j.com/docs/operations-manual/current/authentication-authorization/manage-privileges/).
- Ollama metadata was reachable; configured **`qwen2.5:1.5b`** was installed,
  digest `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`.
  Both successful live responses reported that model. Temperature 0, context
  8192, output cap 150 and the original 180-second request timeout were unchanged.
- Initial sandboxed probes failed. The same authorized read-only checks worked
  outside the sandbox; those initial failures were not treated as server outages.
- Credentials were loaded privately from the established configuration. Neither
  username/password nor unrelated connection settings were printed or saved.
  Recorded privileges exclude username/role columns. A final in-memory scan found
  no actual private credential values and no prohibited evidence-property keys
  in the saved JSON artifacts.

Actual service verification: [services.json](services.json).

## Predefined execution and results

Eleven sequential cases, one attempt each; at most **three real Ollama generation
requests**. Semantic top-k was fixed at **2**, profiles at **200 records**, and
each case had a 240-second watchdog. No retry, query change, candidate filtering,
timeout increase, model change or post-hoc success reclassification occurred.

**9 PASS, 2 FAIL against their prespecified successful-answer expectations,
0 NOT_RUN.** Both failed-success cases abstained safely. Two of the nine passes
are explicitly injected failures, and two are local policy checks, not live
service-generation successes. Case timings total **514.203 seconds**; this sum
excludes initial service checks and the separate offline regression run.

| Case / exact question | Retrieval and evidence | Result | Seconds |
| --- | --- | --- | ---: |
| 01 — What title is registered for clinical trial NCT00206232? | Exact NCT; 14 records; no semantic ranking | **PASS — GROUNDED**, one cited title | 167.590 |
| 02 — Find trials with registered planned outcomes about quality of life. | MiniLM over 2,824 candidates; NCT00939146: 28 records; NCT00012870: 6 | **FAIL successful-answer expectation — ABSTAIN**, second candidate missing outcomes; safeguard correct | 23.081 |
| 03 — Who is the lead sponsor of NCT00206232? | Exact NCT; 14 records | **PASS — GROUNDED**, one cited sponsor | 137.600 |
| 04 — What intervention is registered for clinical trial NCT00206232? | Exact NCT; 14 records; source contains intervention | **FAIL — ABSTAIN**, Ollama connection/timeout error at 180 seconds | 181.153 |
| 05 — What planned outcomes were registered for NCT00206232? | Exact NCT; 14 records; all seven outcome records | **PASS — COMPLETE_LISTING**, zero model attempts | 1.952 |
| 06 — Did spironolactone improve survival in NCT00206232? | Rejected by local question policy; no retrieval/model call | **PASS — ABSTAIN**, unsupported clinical premise | 0.001 |
| 07 — What planned outcomes were registered for NCT99999999? | Exact-ID lookup; no trial found; zero evidence | **PASS — ABSTAIN**, structured NOT_FOUND retained | 0.522 |
| 08 — What planned outcomes were registered for NCT0020623? | Invalid identifier rejected locally; no semantic substitution | **PASS — ABSTAIN** | 0.001 |
| 09 — What planned outcomes were registered for NCT00000475? | Known trial; 9 records; missing planned-outcome source evidence | **PASS — ABSTAIN**, not misrepresented as a nonexistent trial | 1.388 |
| 10 — What planned outcomes were registered for NCT00206232? | **Injected Neo4j verification failure**; no actual outage or graph modification | **PASS — controlled ABSTAIN** | 0.082 |
| 11 — What title is registered for clinical trial NCT00206232? | Live Neo4j: 14 records; **injected Ollama transport failure** | **PASS — controlled ABSTAIN** | 0.833 |

Exact questions, scope, coverage, errors, attempt counts and timings are retained
in [plan.json](plan.json), [summary.json](summary.json), individual case JSON and
`*_summary.json` files. In the raw summaries, `retrieved_trial_ids` denotes
profile-attempt identifiers: for case 07 it contains the requested unknown ID,
**not a found Trial node**. The response and this report explicitly mark it
NOT_FOUND; no evidence or citations were invented for it.

## Factual grounding and citations

Published answers were checked against exact trial-bound catalog entries,
original retrieved properties, citations and prepared-evidence round trips.
This verifies internal source consistency, **not independent clinical truth or
clinical equivalence**. Each successful published answer passed the additional
runner audit. Cases 01, 03 and 05 published **nine source-bound facts in total**
(one title, one sponsor and seven outcomes). No unsupported answer was published
for any abstention case. The first discovery candidate's two outcome facts were
also source-checked but retained separately, not published as a complete
cross-candidate answer.

- **Title:** `Novel Treatment for Diastolic Heart Failure in Women`, citation
  `cite:85602b5dbe212bf4ce959041`; source trial record `NCT00206232` in studies.txt.
- **Lead sponsor:** `Baylor College of Medicine`, citation
  `cite:3db774038cf4618ff9294543`; evidence path
  `NCT00206232|LEAD_SPONSORED_BY|sponsor:64f999d92d1b73893f9b`.
- **Intervention source-only verification:** actual retrieved evidence contains
  `Spironolactone`, citation `cite:21f56031bbf8289fe76bfdcb`, evidence path
  `NCT00206232|HAS_INTERVENTION|intervention:eb4e562ee31fac7ede8a`.
  **This was not a successful LLM answer**: generation timed out. This lookup
  uses the existing live trace, not a retry, mock substitution or fallback answer.

Full registered facts, source-record IDs, relationship properties and provenance
are in the individual traces. The model never generates or repairs citations;
accepted IDs resolve to original exact catalog sentences. Source facts do not
justify treatment-benefit or termination-reason claims.

## Deterministic planned-outcome completeness

Case 05 returned exactly **seven unique source-bound outcomes**, with exact
evidence-ID set equality and correct trial association. Measures, source record
IDs, outcome types and all available time frames were preserved. Counts:
**one primary, one secondary, five other**. No endpoints were relabeled.

| design_outcomes.txt record ID | Registered measure | Type |
| --- | --- | --- |
| 1426532164 | Procollagen peptides, troponin I, tumor necrosis factor alpha, Brain Natriuretic Peptide | other |
| 1426532165 | Electrolytes, blood urea nitrogen, creatinine | other |
| 1426532166 | Quality of Life Questionaire | other |
| 1426532167 | New York Heart Association Classification | other |
| 1426532168 | Number of participants with adverse events | other |
| 1426533443 | Echocardiography parameters of diastolic function | secondary |
| 1426534673 | Six minute walk distance | primary |

The source spelling “Questionaire” remains unchanged. The complete time frames,
citations and readable answer are in [05_outcomes.json](05_outcomes.json).
Both the planned-outcome and snapshot warnings are present in that published
answer. `model_generated=false`, `generation.attempts=0`, no Ollama request.

## Discovery and timeout limitations

The fixed MiniLM discovery ranks were:

1. NCT00939146 — cosine **0.4297686517238617**, 28 evidence records, complete
   source coverage, two registered outcomes.
2. NCT00012870 — cosine **0.390091210603714** as recorded in its live ranking,
   6 evidence records, **zero registered planned outcomes**.

The ranker correctly did not filter candidates using outcome availability.
Cosine measures trial-text similarity, not verified ownership of the query
measure. The second candidate's missing evidence caused the original complete-
listing safeguard to block the composite answer. This is an expected data/policy
limitation, not a proven ranking, joining or citation defect. We did not drop
the candidate, lower top-k after inspecting the result, or silently publish a
partial listing. See [02_discovery.json](02_discovery.json).

The intervention case's raw model response and token counts are **unavailable**,
not zero; there was no completed response to validate. Its recorded error is
`OLLAMA_CONNECTION_OR_TIMEOUT_FAILURE`, with model-call latency 180.015 seconds.
It was the last real generation attempt; no retry or extra repair request was
issued. The fault-injection case later used a mock transport and did not contact
Ollama.

For the title case, actual Ollama request latency was **162.056 seconds**:
model loading **9.902 s**, prompt evaluation **150.179 s** for **2,374 tokens**,
and output generation **1.728 s** for **10 tokens**. Sponsor generation used
**2,364 prompt / 10 output tokens** with request latency **137.106 s**.
These measured timings make prompt evaluation a demonstrated bottleneck; they
do not establish a new optimal prompt or justify changing timeouts here.

## Fixes, regression checks and preservation

**No reproducible production integration correctness defect was demonstrated;
no production fix was made.** Missing outcomes should not be fabricated or
excluded to force success, and a timeout is not grounds to weaken claim checks.
The new `live_validation_v1.py` runner and this versioned evidence package are
the only additions for this step.

The existing focused integration regression suite was rerun:

```bash
.venv-graphrag/bin/python -B -m unittest full_cohort_graphrag.semantic_v1.test_pipeline -q
```

**17 passed, 0 failures**, in **4.579 seconds**. The earlier Step 66G-2 count of
163 distinct tests is historical and is not counted again as this live run.

All **51 protected files** remain checksum-identical, including frozen protocol
manifests, feature bundles, checkpoint and benchmark/training/validation
artifacts in that preservation scope. No frozen test association truth or
benchmark evaluation was used. No Neo4j writes, retraining, installation,
dataset changes, application replacement, commit or push occurred.
See [final_checks.json](final_checks.json) and [manifest.json](manifest.json).

## Demonstration-interface readiness and next boundary

**Ready conditionally** for an explicitly constrained interface showing exact
NCT facts, deterministic complete listings, candidate scores, verified evidence
and honest abstention. **Not yet ready to promise consistently responsive LLM
answers or complete evidence for every semantic candidate.**

- Preserve exact-ID bypass and distinguish semantic candidates from verified
  registered associations and clinical efficacy.
- Display missing-source reasons and per-candidate verified evidence separately
  from the blocked composite answer; do not label it a complete answer.
- Clearly distinguish deterministic listings from model-selected facts. Keep
  long-call progress, one-attempt timeouts and visible failure states.
- Before promising fast interactive LLM performance, seek approval for a bounded
  prompt-size investigation that retains full audit evidence and all validators.
  No prompt, model, temperature, timeout or retrieval setting was changed here.
- A new live-validation run must use a new output version; the executed runner
  refuses to overwrite this package. No further live run is authorized
  automatically by this report.

**Stopped after Step 66G-3. No final interface or final Challenge 3 report started.**
