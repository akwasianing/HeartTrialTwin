# Phase 3 — clean-environment and GitHub preparation report

**Date:** November 6, 2026. **Overall: PARTIAL — instructor reproducibility
acceptance is not fully met.** The application runs with verified local assets
and fresh packages, but the final source-only candidate lacks 144 assets, no public
runtime-bundle route exists, and cold scenario loading had an unresolved first
failure. This is a measured handoff assessment, not a new scientific experiment.

## Recovery and preservation

Recovered the existing `codex/v6-submission-readiness` branch at
`be520bcd40748abfc03e4ff9b64bf244650c5367`; `main` remains at that same commit.
Nothing was staged, committed, pushed, merged or deleted. The interrupted fresh
UI installation had succeeded; metadata and dependency checks verified it and
it was not reinstalled. The empty fresh worker environment was completed.

All **13 Phase 2 files** remain byte-identical to their recorded hashes. The
original 187-asset receipt remains
`958f09f86117ee7cdad8315ffa7d1f1ffdcf8d2ce931d58293654fa70e846655`.
No application feature, timeout, test, model, graph, frozen protocol, poster or
historical research result was changed. Earlier 169-test Phase 2 results remain
historical evidence and are not claimed as newly rerun here.

## What was executed

| Check | Actual result |
| --- | --- |
| Fresh UI installation | Recovered successful independent installation; seven pinned packages verified; no reinstall |
| Fresh worker installation | Successful pinned wheel installation; no existing environment modified |
| Dependency checks | Both fresh environments: no broken requirements |
| Initial source-only candidate | Tracked-tree export plus proposed source overlay; **143 missing Phase 2 assets**, zero checksum mismatches; not runnable as complete app |
| Final reviewed source-only candidate | **144 missing assets**, zero checksum mismatches after the private-path legacy helper was held out; not GitHub-only reproducible |
| Local-asset candidate | Same source overlay, **143 additional verified runtime copies**; no credential or development-package copies |
| Runtime preflight | **READY_LOCAL**; 187 Phase 2 assets pass; separate 190-file Phase 3 inventory includes the original cohort-manifest dependency and bootstrap files |
| Initial full fresh workflow suite | **24 tests: 23 passes, 0 assertion failures, 1 error**, no skips; 143.059 s runner time |
| Scenario diagnosis | Direct frozen profile loading succeeded: **257 profiles / 42.871 s**; no fitting |
| One focused scenario rerun | **1 pass / 11.674 s**; acknowledgement, actual NCT03015402 26→39 replay, four saved-model rows, zero fits, no source writes |
| Fresh Streamlit server | Loopback port 8511 started; health returned `ok`; test server then stopped |

The initial scenario error was `KeyError` for absent `historical_profiles['count']`.
The underlying worker error/status was not retained. Slow cold initialization or
resource contention is plausible, **not confirmed**. Do not describe the initial
suite as 24/24 passing or the root cause as definitively fixed. All 24 distinct
methods eventually have passing coverage, but not in a single clean first run.
No automatic retry, repair, timeout increase or suppressed test was introduced.
Rehearse the scenario page before a live demonstration; cold-path reliability
needs a separately scoped investigation if this feature is required first-use.

See [EXECUTION_RESULTS.json](EXECUTION_RESULTS.json),
[ENVIRONMENTS.json](ENVIRONMENTS.json), and [exact commands](COMMANDS.md).
Seven standard-library handoff tests also passed (0.030 s); the tightened
publication-exclusion check was rerun alone after the privacy hold and passed.
These are separate from both the 24 fresh application methods and the retained
169 Phase 2 methods. [VALIDATION_CHECKS.json](VALIDATION_CHECKS.json) records the
scoped final path/content review and exact preservation counts.
The actual isolated test is a same-machine tracked-tree export, **not** a fresh
remote clone or independent hardware replication. Explicit aliases point only
to the newly created test environments, never development site-packages. No
development project appeared on the tested Python import path.

## Demonstrated workflows

With pinned local assets and fresh packages, the passing checks cover:

- Five-page startup/navigation; NCT00206232 default and valid/unknown IDs.
- Baylor College of Medicine sponsor and Spironolactone intervention, with
  correct trial-bound citations and zero LLM calls.
- Seven complete registered planned-outcome records and citation/evidence IDs.
- Missing evidence and unsupported effectiveness/cross-trial questions abstain.
- Community membership, shared source relationships and session feedback;
  optional unvalidated model interpretation stays disabled.
- NA + DRUG filter: 115; blocked predictive dashboard: 329 binary-evaluable records.
- Scenario acknowledgement and replay succeeded on the focused rerun, with the
  first-run qualification above. The model is not clinically validated.
- Tampering, missing assets, worker failure and timeout safeguards.

No live Neo4j or Ollama call was made. HTTP health does not alone establish these
workflows; AppTest executed the actual local UI/evidence paths.

## Assets and missing provisioning boundary

[RUNTIME_ASSETS.json](RUNTIME_ASSETS.json) specifies **190 required files**,
**41,603,498 bytes**, each with destination, size, hash, authority and distribution
classification. Phase 2's preserved retriever additionally checks the original
frozen cohort CSV; this was made explicit here without changing its code/receipt.

- **Source suitable for review/publication:** application/support code, tests,
  documentation, requirements, manifests and selected aggregate evidence.
- **Documented public sources:** already tracked bytes have base-commit GitHub
  links; Python packages have a public-index reference and actual fresh-install
  evidence. The upstream AACT archive reference is not a direct download of
  derived runtime files and was not downloaded here.
- **Separate bundle needed:** exact graph/source caches, historical eligibility
  records, required old base-package files and other derived runtime material.
  No public bundle URL or independent redistribution clearance is invented.
- **Not proposed for public distribution:** four trusted fitted joblib models,
  the preserved training/helper module with a private authorization-path pointer,
  private configuration, databases, environments and backups. Models must be
  supplied through an approved owner-controlled route to reproduce scenario
  functionality and satisfy the unchanged whole-base guard.
- **Optional:** Neo4j/Ollama, MiniLM/GraphSAGE weights and embeddings, Chroma and
  raw AACT ZIP are unnecessary for this main offline demo.

The exact proposed source/evidence set is in
[PUBLICATION_FILES.txt](PUBLICATION_FILES.txt) and
[PUBLICATION_ALLOWLIST.json](PUBLICATION_ALLOWLIST.json). Those are review-only
allowlists, not permission to stage whole directories. Existing earlier-challenge
tracked content is preserved, not newly endorsed as a universal runtime.

## Documentation and scientific evidence

Root README now starts with the main v6 purpose, intended research users,
cohort, five pages, setup gate, real example and results limitations. Earlier
Challenge 1/2/3 sections are retained and explicitly distinguished. The separate
MiniLM/live GraphRAG demo is supplementary, not the main UI.

[RESULTS_INDEX.md](RESULTS_INDEX.md) maps the graph, communities, ranking,
descriptive analysis, V1 independent evaluation and longitudinal pilot to saved
evidence. New public review copies of three aggregate JSON summaries retain
source paths/hashes. Nothing was refitted, rescored, bootstrapped or tuned.
Graph rows were recounted (28,777 / 79,125) and saved community values aggregated
(B1 ARI 0.648078; B3 0.866962; B3 904 groups / 820 singletons). These are file
checks, not fresh extraction, community detection or live database verification.

GraphSAGE remains the negative experimental comparison: test MRR 0.01124 versus
MiniLM 0.07619 and context pooling 0.07841 on 2,219 eligible queries. These are
saved descriptive test comparisons, not new selection. V1 later evaluation
remains 329 binary-evaluable records, ROC-AUC 0.487, AP 0.157, Brier 0.1100,
release BLOCKED. Historical T/W discontinuation and later Terminated-only
evaluation remain distinct. The longitudinal 24/72 pilot's nine changing trials
yield ten changed comparisons—not dated clinical events or validated forecasting.

The exact Version 20 PowerPoint and a demonstration video remain **not located**.
No older poster was moved, renamed or substituted as Version 20.

## Security and publication

Credential rotation/revocation remains **unconfirmed by the owner**. No exposed
credential was read, used, copied, disclosed or changed. The affected dedicated
full-cohort Neo4j account must be privately rotated/revoked before live reuse.
A clean content review cannot certify the unchanged account credential safe.

This phase uses an exact allowlist and scoped text/size/path checks, not another
expensive historical binary/OCR scan. Previously completed history findings are
retained with their limits. `.gitignore` now excludes local backup archives and
future handoff workspaces; valuable files were not removed. No new weights,
raw datasets, `.env`, private databases, environments or unrelated working files
are proposed. Archival source may retain platform-specific font paths; these
are identified separately, not silently rewritten inside preserved code.
The one preserved training module containing a private local authorization path
is held out of the new public source set; it remains unchanged in the trusted
runtime bundle. Its training main is not invoked by serving.

## Reviewer walkthrough

| Instructor criterion | Status | Reason |
| --- | --- | --- |
| Understand project/users/method | **PASS** | Main README, scope and architecture are explicit |
| Install dependencies | **PASS on tested Intel Mac** | Fresh UI/worker packages and checks succeed; no cross-platform claim |
| Provision data independently | **PARTIAL** | Exact inventory/checker exist; owner-supplied assets work, public runtime route absent |
| Launch application | **PASS with provisioned assets** | Fresh server health and actual UI startup; source-only fails closed |
| Run documented example | **PASS with provisioned assets** | Sponsor/intervention and seven-outcome citations verified |
| Use all five pages reliably on first start | **PARTIAL** | Navigation works; initial cold scenario failure remains qualified |
| Inspect results | **PASS for saved evidence** | Index and aggregate results available; poster/video missing |
| Understand limitations | **PASS** | Planned/results distinction, missingness, observed-graph scope and blocked risk release explicit |

## Smallest remaining steps

1. Establish an approved, accessible runtime-bundle route and redistribution
   terms, including a trusted-model provision policy; then test that actual route.
2. Resolve cold scenario initialization in a separately authorized change or
   explicitly limit the accepted first-use demonstration scope. Preserve Phase 2
   and the recorded failure until an actual fix is tested.
3. Privately rotate/revoke the exposed Neo4j account before supplementary live use.
4. Locate the real Version 20 poster/video; do not substitute prior versions.
5. Review final allowlist/security findings, then seek publication approval.

**Stop before commit/push. Main history and frozen research remain unchanged.**
