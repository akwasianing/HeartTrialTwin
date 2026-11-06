# Phase 2 — Community v6 finalization and validation

**Date:** November 5, 2026. **Disposition:** ready for a local, deterministic,
research-only demonstration on the provisioned Intel Mac. **Not** a clean-clone
release, clinical deployment or new model evaluation. Nothing staged, committed
or pushed. No dependency installation, data download, model fit, embedding
generation, Neo4j query/write or Ollama request occurred.

## Scope and exact changes

Modified only these three pre-existing v6-local files:

- `app.py`: v6 labels/launch instructions; full preflight before loading preserved
  dependencies; deterministic community view; supplementary-demo boundary.
- `trial_intelligence_v5.py`: retained filename, v6-local implementation; default
  NCT00206232; exact selected-trial question scope; loading/elapsed display;
  prevent stale answers after question/field/trial changes.
- `README.md`: current commands, workflows, warnings and provisioning boundary.

Added only within this same v6 directory:

- `community_page.py`: source-derived relationships, full separate loaded outcome
  lists, distinct-trial attribute counts, session feedback; **no model controls**.
- `integrity.py`: receipt pin, file/semantic membership checks, safe paths and
  fail-closed errors; never repairs evidence.
- `runtime_integrity_v1.json`: new runtime receipt, not a replacement historical
  manifest. SHA-256:
  `958f09f86117ee7cdad8315ffa7d1f1ffdcf8d2ce931d58293654fa70e846655`.
- `provision.py`: read-only inventory, external-mirror and environment preflight.
- `requirements-ui.txt`, `requirements-worker.txt`: actual locally verified pins.
- `tests/test_app.py`, `tests/test_integrity.py`: actual local workflow and
  isolated provisioning/tamper regressions.
- `PROVISIONING.md` and this validation record.

The unused old v6 backup/helper/upgrade files were neither executed nor removed.
No v4, original GraphRAG, integrated-package or historical manifest was edited.

## Integrity and preservation

Preflight verifies **187 assets / 40,539,404 bytes**. Graph authority is the
unchanged `full_cohort_manifest.json` with SHA-256
`3ef82624d131b36abc1eb9ad4e89b3439fed9f9600b92262c21bbcbfe6cf8757`.
The B3 expectation is copied from the preserved community exploration manifest's
`inputs_sha256`, not inferred from desired counts. Runtime also checks the exact
trial-ID universe and seed-42 B3 identity: **2,824 trials, 904 groups, 820 singletons**.

The receipt covers all files demanded by the unchanged graph/base guards,
dashboard outputs, later evaluation, four saved LR pipelines, and 22 historical
development-observation caches. Current application-code hashes are explicitly
new code-snapshot provenance, not falsely attributed to an old frozen manifest.
The bootstrap verifier and receipt pin still require source review; they are
not a digital signature or defense against arbitrary whole-project editing.

Before/after hashes matched for **288 protected files**, including the full graph
payload, old v4 app, prior base/integrated packages, Version 1/2 protocols, GNN
experiment/checkpoint and the later independent-evaluation JSON. Tracked Git
files remain unchanged. Version 2 remains at
`b13d662390b687b62a08cc1fb81bd3413f2c9d1fbb3b6ec86438b1a6854cd95b`.
No partitions, labels, model coefficients, scores or research results changed.

The old integration manifest's previously reported stale entries remain intact;
this new receipt documents the current reviewed code without rewriting history.

## Tests and observed workflows

| Suite | Distinct tests | Result | Observed run time |
| --- | ---: | --- | ---: |
| New v6 UI, real local evidence/scenario and integrity/provisioning | 24 | PASS | 52.769 s |
| Existing full-cohort retrieval/preparation/generation/listing | 102 | PASS | 13.060 s |
| Existing semantic pipeline/demo backend | 39 | PASS | 6.426 s |
| Existing supplementary Streamlit UI | 4 | PASS | 3.108 s |
| **Total distinct methods** | **169** | **0 failures/errors** | — |

Final inventory classification and a whitespace-only cleanup were followed by a
separate rerun of the **12 integrity tests** (PASS, 0.845 s); these are included
in the 24, not counted again. Initial new-test scaffolding had two incorrect assumptions about
existing trace nesting/empty arrays. Those assertions were corrected to the
actual unchanged contract; no production scientific validator was relaxed.

Actual AppTest workflows, not merely syntax inspection:

- All five pages start without execution exceptions.
- NCT00206232: verified sponsor **Baylor College of Medicine**, registered
  intervention **Spironolactone**, trial-bound citation references, zero LLM calls.
- Complete planned-outcome listing: **seven distinct evidence IDs**, preserved
  per-trial citation bindings, outcome safeguard and snapshot provenance.
- Unknown/invalid trial IDs do not acquire fabricated evidence or semantic
  replacements. NCT00000475's missing planned outcomes produce abstention and
  retain the available evidence separately.
- Unsupported survival-effectiveness question and cross-trial custom question
  abstain. Changing the chosen field hides an earlier result.
- B3 community and shared-source graph render; human feedback remains session
  state. No Generate/Revise controls or reachable Ollama option in the v6 view.
- NA + DRUG phase filter: **115** records. Dashboard displays **329** binary
  evaluable trials, ROC-AUC **0.487**, and **BLOCKED** predictive release.
- Scenario: **257** eligible historical development profiles; acknowledgement
  required. Actual NCT03015402 **26 → 39** replay produced four saved-model rows,
  `model_fits=0`, `source_evidence_written=false`, release `BLOCKED_UNCHANGED`.
- Mocked timeout and absent worker produce controlled abstentions, no retry and
  no fabricated result. New UI tests forbid `urllib` external requests.

Sandbox PyArrow CPU-probe warnings are nonfatal. Existing reused pages still
emit some Streamlit width deprecation warnings; they were not cosmetically
rewritten. No clinical inference is inferred from any UI test or score replay.

## Commands executed and reproduction

All commands run from the repository root. Inspection used `git branch
--show-current`, `git rev-parse HEAD`, `git status --porcelain=v1 -uno`, targeted
`find`/`rg`/`sed`, dependency metadata inspection, and read-only hash comparisons.
No `git add`, checkout, clean, reset, commit, push or blanket move was used.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/app.py --inspect
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/provision.py --check-environments
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B -m unittest discover -s reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/tests -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B -m unittest discover -s reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/tests -p 'test_integrity.py' -q
PYTHONDONTWRITEBYTECODE=1 .venv-graphrag/bin/python -B -m unittest discover -s full_cohort_graphrag/tests -p 'test_*.py' -q
PYTHONDONTWRITEBYTECODE=1 .venv-graphrag/bin/python -B -m unittest full_cohort_graphrag.semantic_v1.test_pipeline full_cohort_graphrag.semantic_v1.demo_v2.test_demo -q
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B -m unittest full_cohort_graphrag.semantic_v1.demo_v2.test_app -q
git diff --check
```

The recorded UI test executions used the same unittest loaders inside a short
Python heredoc with `logging.disable(logging.WARNING)` and `TextTestRunner`;
this suppresses repetitive framework logging, not failures or test methods.
The commands above reproduce the same suites without that logging wrapper.

Actual server smoke command:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B -m streamlit run reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/app.py --server.address 127.0.0.1 --server.port 8510 --server.headless true --browser.gatherUsageStats false
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8510/_stcore/health
```

Socket binding was initially denied by the sandbox. The approved retry started
Streamlit on loopback; the health endpoint returned **`ok`**. The test server
was then stopped with Ctrl-C; no existing server was stopped. HTTP health alone
does not prove application workflows—the separate AppTest checks above do.

`app.py --inspect`: **OK**. Provisioning with dependency checks: **READY_LOCAL**,
no asset or environment failures, zero copies/downloads. An empty isolated root
was deliberately rejected; clean-clone reproducibility remains **false/unverified**.
Syntax and documentation links were checked, plus scoped whitespace/security
checks. New text contains no detected API-key patterns or credential-bearing
URLs. This is not an exhaustive security or historical binary scan.

## Scientific and security boundaries

Registered measures are not observed results. Shared nodes/group memberships do
not establish clinical equivalence. Historical fractions are descriptive,
noncausal and terminal-cohort-selected. Scenario scores are exploratory,
in-sample and not calibrated prospective risks. No claim that GraphSAGE improved
retrieval, community stability establishes clinical validity, or held-out
association ranking establishes unseen-trial induction is made.

No exposed credential was read, copied into the package, authenticated with,
rotated or printed. The earlier local full-cohort Neo4j credential exposure
requires the owner's private rotation/revocation action before live reuse;
see [PROVISIONING.md](PROVISIONING.md). The main app operates without it.

## Remaining handoff gates

1. Curate a source/dependency allowlist; keep backups, `.env`, environments,
   raw archives and model weights out of automatic staging.
2. Obtain permission and a safe distribution route for the exact external
   graph/source assets and trusted frozen scenario-model bundle.
3. Execute the documented install/provision sequence on an independent clean
   Python 3.12 machine. Existing local success is not this evidence.
4. Update root navigation/README in a separately reviewed publication phase.
5. Resolve the exposed Neo4j account credential before supplementary live use.
6. Locate the Version 20 poster/video before asserting their publication/readiness.

No publication is authorized or performed by this validation record.
