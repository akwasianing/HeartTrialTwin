# Step 66G-5 — final technical audit

Audit date: October 25, 2026, America/Chicago.

**Disposition:** local demonstration and scientific evidence are ready for
report/presentation authoring with explicit limitations. **Publication/security
clearance remains blocked pending credential rotation and a separate staging
review.** No actual Challenge 3 report or new presentation was written.

## Audit boundary and canonical evidence

Reviewed the pinned full graph and source coverage, original five-trial GraphRAG
retrieval/grounding implementation, full-cohort adapter/generator, frozen V2
protocol, MiniLM feature code/provenance, trained checkpoint/history/config,
saved five-method validation/test results, GNN diagnostics, semantic integration
and final Streamlit application. Saved results were reconciled, not regenerated.

The detailed counts/metrics are consolidated in
[FINAL_PROJECT_SUMMARY.md](FINAL_PROJECT_SUMMARY.md). Machine-readable checks:
[evidence_audit.json](evidence_audit.json), [integrity_final.json](integrity_final.json),
and [current_services.json](current_services.json). The first audit finished all
tests and saved its JSON, then hit a **reporting-only relative-path error** while
printing the output path. The new audit helper was corrected and its subsequent
integrity-only run succeeded. Successful tests were not needlessly repeated.

## Component consistency

| Component | Verified evidence / result | Remaining boundary |
| --- | --- | --- |
| Full graph | Manifest, 26 file hashes, membership/source coverage; 28,777 nodes, 79,125 relationships | Live identity/count checks are not a byte-for-byte audit of every live property |
| Full cohort | 2,824 frozen members; no outcome-availability membership filter | Terminal-outcome-selected cohort; not every registered HF trial |
| Source coverage | 253 trials lack browse terms; 41 lack outcome rows; 528 outcome time frames blank | Missing link/value is not evidence of absence |
| Original GraphRAG | Fixed Cypher, provider separation, deterministic provenance, claim checks/abstention inspected | Five-trial workflows and legacy validators are not a full-cohort benchmark |
| Frozen V2 | Manifest/files/source hashes; 31 saved-fixture V1/V2 regressions passed | Family/near-query screening is conservative and incomplete |
| Features | Three complete feature-bundle payload hash maps, original identity pins; runtime artifact validation passed | Exact environments/local cache are required; no cross-platform bit-identity promise |
| GraphSAGE | Selected checkpoint/config/history hashes; 80 updates, epoch-60 selection; mathematical regressions pass | Weak held-out ranking, no deployment claim |
| Benchmarks | Both saved results and per-bundle file hashes match; same 2,824-candidate universe | No new test evaluation or test-based tuning; no three-RAG-system formal benchmark claim |
| Diagnostics | Frozen report/manifest, fixed-weight message comparison and tiny training-only findings inspected | Proposed causes remain hypotheses, not isolated causal findings |
| Final integration | Exact routing, deterministic facts, unchanged ranking, bounded evidence selection and safe failures tested | Rigid question grammar, strict source completeness, bounded discovery |

### Identity pins

- Full graph manifest SHA-256:
  `3ef82624d131b36abc1eb9ad4e89b3439fed9f9600b92262c21bbcbfe6cf8757`.
- Protocol manifest SHA-256:
  `b13d662390b687b62a08cc1fb81bd3413f2c9d1fbb3b6ec86438b1a6854cd95b`.
- Core feature manifest SHA-256:
  `e2f167b01b2e83aef1f11ef6e4dba673d741246927a43f30936888beecf99a17`.
- Selected checkpoint SHA-256:
  `58bac20f20d15349063ef36079d204714052b48bb4332c6622e68c43d0d7b936`.

V2 still has `training_permitted=False` and its historical provisional status.
External freeze/execution authorizations, not rewriting these fields, explain
the later completed experiment. The original default fail-closed loader remains.
Frozen `selection.json` saying `test_accessed:false` describes selection time;
the separate test manifest records subsequent completed test evaluation.

## Current regression verification

| Suite | Passed | Failed/errors/skipped |
| --- | ---: | ---: |
| Full-cohort retrieval/preparation/generation/listing | 102 | 0 |
| Original semantic integration + demo backend | 39 (17 + 22) | 0 |
| Mocked Streamlit UI | 4 | 0 |
| MiniLM ranking + GNN execution/diagnosis | 44 (12 + 32) | 0 |
| Existing V1/V2 saved-fixture protocol regressions | 31 | 0 |
| **Distinct current tests** | **220** | **0** |

Logs: [full cohort](full_cohort_tests.txt), [integration/demo](integration_demo_tests.txt),
[UI](streamlit_ui_tests.txt), [ranking/GNN](ranking_gnn_tests.txt),
[protocol](protocol_tests.txt). Eight mutation/regeneration protocol methods were
deliberately not selected; they are not counted as passes or skips. Historical
80-, 102-, 163- or 189-test milestones are not additional current passes.

Tests cover title/sponsor/intervention facts, exact trial/citation bindings,
seven-outcome completeness, original ranks/ties, evidence-backed selection and
skip logs, partial budgets, missing sources, unknown/malformed IDs, clinical-
premise abstention, tampering, pagination, output caps, service failure redaction,
Ollama timeout/no-retry behavior, explicit deterministic re-request, subprocess
deadlines and rendered UI. Mocked timeout tests are not measured live outages.

## Current live/application checks

- Browser application at <http://127.0.0.1:8502/> loaded and answered
  **“What title is registered for NCT00206232?”** with `GROUNDED`, **0** model
  requests, **6.36 s** displayed elapsed time, and the exact registered title and
  citation. Screenshots: [status](screenshots/01_live_title.jpg),
  [answer/provenance](screenshots/02_live_title_answer.jpg). These are real
  captures from the available narrow in-app browser, not mock screenshots.
- Current read-only service probe: Neo4j identity/version/count checks succeeded;
  explicit node/relationship write denials and no elevated grants were verified
  using privilege metadata. No write probe or data mutation. Configured local
  Ollama/model metadata was reachable; no generation call was made.
- Existing G-4 four-case smoke and UI-to-backend traces remain checksum-identical.
  Sponsor/intervention/listing/discovery success, exact citations, seven outcomes,
  the missing-evidence skip and latency values were verified from those traces.
  We did not rerun that full suite merely for the audit.
- Earlier G-3 failures remain failures: discovery had insufficient top-two
  evidence and intervention generation timed out. New deterministic success
  does not retrospectively turn those LLM attempts into successful generation.

## Security and publication findings

| Finding | Action / disposition |
| --- | --- |
| Password present in `full_cohort_graphrag/.env.example` | **Confirmed, sanitized** to placeholders. Private `.env` and database account were not changed. Treat the old credential as exposed; owner must rotate it privately and update ignored configuration before sharing/publication. No password value is repeated here. |
| Disposable `.codex-ppt-build/` was untracked/nonignored | Added a single `.gitignore` entry. Valuable local files remain; nothing deleted from the build directory. |
| Two scanner candidates in other example files | Reviewed as placeholder assignments, not live-secret findings; no original GraphRAG/pilot change needed. |
| Bounded final credential scan | No known-private-secret or limited key-pattern matches remained in inspected text. Scope/exclusions are explicit in `integrity_final.json`; five >5 MiB text files and binaries were not content-scanned. This is not an exhaustive security certificate. |
| Private configuration and environments | Existing `.env` and `.venv*` exclusions verified. No private `.env` file is tracked. Public remote contains no embedded credential. |
| Large files | No >50 MiB files in the bounded tracked/nonignored inventory, excluding course week folders. Original archive lives outside the repository. Untracked raw/generated research data still needs selective publication review. |
| Public reproducibility | The current full-cohort/GNN directories remain untracked local work, not a verified GitHub release. Do not stage them wholesale. Authorize a reviewed publication/data-distribution plan separately. |

Initial and final security inventories are bounded scans, not historical leak
searches. The exposed credential must be rotated even after the template is
clean; local sanitization does not undo earlier copies, chat/tool output or other
possible exposure. Do not send the replacement password in chat.

## Preservation, dependencies and documentation

- Current checks verify 51 protected research files, 12 original semantic files
  and 28 prior live-validation files against recorded hashes. Full graph,
  protocol, feature, training and evaluation payload hash maps also passed.
  Both complete 25-file V1/V2 protocol tree fingerprints additionally match the
  original freeze/integrity records, not merely their top-level manifest hashes.
- 49 original GraphRAG/full-cohort/GNN Python source files passed syntax parsing;
  functional imports are exercised by the actual environment-specific tests and
  offline ranking worker. No missing runtime dependency was demonstrated.
- Existing environments remain separate: Streamlit 1.64.0 / NumPy 2.1.3 /
  PyArrow 24.0.0 for UI; Neo4j driver 6.4.0 / dotenv 1.2.4 for retrieval; pinned
  NumPy 1.26.4 / PyTorch 2.2.2 / Sentence Transformers 5.1.2 for MiniLM/GNN.
  No package was installed, upgraded or mixed across these environments.
- Sandbox UI tests emitted non-fatal CPU-probe/bare-context warnings. The live
  browser/service check succeeded outside those restrictions.
- Earlier READMEs saying “retrieval only”, protocol NOT_RUN metadata and older
  presentation files are stage-specific historical records, not proof that the
  current integrated demo is absent or that a final presentation is complete.
  This package supplies the current scope without rewriting those records.
- Source-relative documentation links and syntax/whitespace checks are covered
  by [FINAL_QA.json](FINAL_QA.json) and the package is bound by
  [EVIDENCE_MANIFEST.json](EVIDENCE_MANIFEST.json). No repository-wide claim about every historical
  document or screenshot is made.

Git at audit start: branch `main`, HEAD
`4c5d187ea18845b46f655910b0935ef559da2ba6`. The remote is
[akwasianing/HeartTrialTwin](https://github.com/akwasianing/HeartTrialTwin).
This is a base revision plus uncommitted/untracked work, not a commit identifying
all final experiment code; use the frozen code/data hashes for research identity.
No commit, push, Neo4j write, retraining, embedding regeneration, frozen-result
change, or modification under `week 5/` occurred.

## Remaining gates

1. Rotate the exposed read-only credential privately; update ignored `.env` and
   recheck access before public sharing. This audit does not change authentication.
2. Review and selectively publish the intended source, documentation and permitted
   pinned assets only after explicit approval; establish portable data/cache setup.
3. Author the actual Challenge 3 report and presentation from this evidence.
   Retake wider screenshots if needed for slides; do not reuse obsolete prototype
   metrics as trained full-cohort results.
4. Keep all clinical/generalization/superiority claims within the documented
   limits. New model work requires a separate protocol and independent confirmation.

No remaining runtime/scientific-integrity defect was demonstrated in the
supported local paths. Limitations are not waived by passing tests.
