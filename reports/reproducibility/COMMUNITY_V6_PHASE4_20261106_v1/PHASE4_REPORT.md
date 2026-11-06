# Phase 4 — final reproducibility and submission readiness

**Date: November 6, 2026. Assessment: READY WITH LIMITATIONS for the local
demonstration and reviewed source submission. NOT READY for public-GitHub-only
execution.** This does not clear clinical release, account security or public
runtime redistribution.

## Completed work and measured results

| Requirement | Verified outcome |
| --- | --- |
| Recover current state | Continued `codex/v6-submission-readiness` from `be520bcd40748abfc03e4ff9b64bf244650c5367`; no unrelated files deleted/moved |
| Review runtime gap | All 190 exact entries assessed; source-only candidate lacks **144 files / 37,521,267 bytes** |
| Local asset distribution | One private versioned tar created outside repo; safe installer copied all 144 and verified **190/190** files |
| Dependencies | Reused two independently installed fresh Phase 3 venvs; both pass `pip check`, all required versions pass preflight; no redundant reinstall |
| Main application workflows | **24/24** existing UI/integrity methods pass, 47.753 s, no errors/skips, scenario first |
| New handoff tooling | **7/7** focused offline tests pass, 0.157 s; unsafe/tampered/incomplete/duplicate payloads and overwrites rejected |
| HTTP startup | Initial sandbox bind denied; authorized localhost startup/health `ok`; server stopped |
| Scenario initialization | New-process profile load 4.339 s; replay 2.408 s. Earlier failure not reproduced; original cause remains unknown |
| Security | Scoped 190-file text/compressed/metadata scan: zero credential-pattern findings; privacy/terms holds retained, no claim of exhaustive clearance |
| Scientific preservation | Existing source hashes/Phase 2/3 records and frozen artifacts verified separately; no research/model changes |
| Poster/video | Original `figures and charts /HeartTrialTwin_V20.pptx` located during final whole-project check; 1 slide / 48 × 36 inches; no video located |

The 24 UI methods cover all five pages, NCT00206232 sponsor Baylor College of
Medicine / intervention Spironolactone, seven distinct outcome/citation bindings,
community navigation, NA + DRUG count 115, 329-record blocked evaluation,
NCT03015402 bounded scenario, invalid/unknown/missing records, unsupported
effectiveness and cross-trial requests, tampering and worker failure/timeout.
These are functionality tests, not a new predictive or retrieval benchmark.

No live Neo4j or Ollama call was made. AppTest exercises actual offline evidence;
HTTP health separately establishes startup. No screenshot or cross-machine/public
download verification is claimed. [Execution results](EXECUTION_RESULTS.json),
[server record](SERVER_SMOKE.json) and [commands](COMMANDS.md) retain the evidence.

## Distribution decisions and remaining missing assets

All 144 missing paths and 46 already supplied entries are individually documented
in [ASSET_DISTRIBUTION_REVIEW.json](ASSET_DISTRIBUTION_REVIEW.json). After **local**
provisioning: zero missing/mismatched. For a **public source-only clone**: the
144-file gap remains; no approved public bundle route exists.

The tested private artifact is 37,683,200 bytes, with a SHA-256-bound receipt.
It preserves original scientific/source bytes and required old whole-package
dependencies. It includes four trusted joblib models and private-path metadata,
so it is **not a candidate upload**. [Distribution decisions](DISTRIBUTION_DECISIONS.md)
define the structure, upstream-source limits, rights/privacy checks and trusted
private alternative. GitHub Releases or an institutional archive is a possible
future host only after explicit clearance; no URL/license is invented.

The public proposal contains application/support source, tests, manifests,
selected lightweight aggregate results and reproduction documentation—not the
runtime tar, external models, historical caches, raw ZIP, databases or private
authorization material. Previously tracked earlier-challenge artifacts remain
unchanged, not silently relicensed by this update.

## Scenario finding

The earlier profile-count KeyError had no retained underlying error response.
The targeted new harness saved worker exit/status/timing without logging secrets
or raw stderr. With verified assets and matching fresh packages, scenario works
first in the test process. This is evidence against a reproducible mandatory
test-order fault, **not** proof that cold initialization cannot fail. No timeout
increase, automatic retry, retraining, imputation change or guard bypass occurred.
See [SCENARIO_DIAGNOSIS.md](SCENARIO_DIAGNOSIS.md). Rehearse the page before use.

## Scientific/security boundaries

- The graph remains 2,824 trials / 28,777 nodes / 79,125 relationships / 19,740
  registered planned-outcome associations, snapshot September 5, 2026.
- Planned endpoints are **not observed clinical results**; source values may
  include amendments. Community groupings remain exploratory similarities.
- The later V1 evaluation remains 329 binary-evaluable trials, ROC-AUC about
  0.487; predictive release **BLOCKED**. No new performance was estimated here.
- Scenario arithmetic is acknowledged, development-only, noncausal and not a
  validated prospective forecast; unsupported risk categories remain Not Modeled.
- Unvalidated community LLM interpretation remains disabled. MiniLM/live Neo4j
  is a separate supplementary demonstration, not required for the main app.
- The previously exposed dedicated full-cohort Neo4j credential remains
  unconfirmed rotated/revoked. It was not read, used or copied. The owner must
  privately rotate/revoke it before live reuse. No database rebuild is necessary.
- Earlier review found no known-secret match in inspected published history;
  no new account-safety certification or exhaustive historical/binary scan is
  claimed. A clean allowlist does not make that unchanged password safe.

## Repository materials and instructor accessibility

Root README preserves previous challenges and now directs readers to the current
setup, per-file gap and measured readiness. Requirements and application logic
remain unchanged. [SETUP.md](SETUP.md) supplies exact commands, real workflows and
external-asset gates. The prior [results index](../COMMUNITY_V6_PHASE3_20261106_v1/RESULTS_INDEX.md)
remains authoritative and unchanged. The final allowlist supersedes only the
current source proposal, not historical Phase 3 records.

The unstaged `git diff --check` passes. The staged check identifies **three
pre-existing, hash-preserved whitespace exceptions**: Markdown hard line breaks
in `V1_INDEPENDENT_EVALUATION_REPORT.md` lines 3–4, and a final blank line in
Phase 2's `trial_intelligence_v5.py` line 209. These original bytes were not
rewritten. The final checker accepts only these exact path/line/issue triples
after file-hash verification and rejects any new whitespace issue. The raw
staged check is therefore not represented as a zero-exception pass.

No local official instruction confirming that a feature-branch submission alone
is acceptable was established. Treat a useful default-branch README as the
instructor-facing expectation. A pushed branch/PR is **not** the same as a merged
`main`; merge requires owner review and is not automatic.

The actual V20 poster was found outside the previously checked reports folders:
`figures and charts /HeartTrialTwin_V20.pptx`. The original is unchanged and linked
from the root README. Structural/text/security review is recorded in
[POSTER_REVIEW.json](POSTER_REVIEW.json); no new visual rendering is claimed.
Phase 3's historical not-located finding remains unchanged. No older poster was
renamed and no video URL is supplied.

## Remaining manual actions

1. Review/merge the submission PR into `main` when appropriate; use the branch/PR
   URL meanwhile and explicitly disclose whether default-branch publication is pending.
2. Approve an owner-to-team asset handoff for the instructor, or clear licensing,
   privacy, executable-model trust and hosting before a public runtime release.
3. Test the **actual approved public download** and an independent-machine clone
   once available. Same-machine local provision does not meet that stronger claim.
4. Privately rotate/revoke the affected Neo4j credential before supplementary live use.
5. Supply a real demonstration-video URL if desired; the genuine V20 poster is now linked.

No new models, experiments, application redesign, frozen-result changes,
database writes, secret use or publication of the private runtime was performed.
Authorized Git publication outcome is reported separately after remote verification.
