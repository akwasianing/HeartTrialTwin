# Community v6 — Phase 4 handoff

**Status: READY WITH LIMITATIONS for an approved local handoff; not yet
public-GitHub-only reproducible.** No public runtime URL or redistribution approval
exists. Do not use the previously exposed Neo4j credential. The main offline app
needs neither Neo4j nor Ollama.

## What comes from where

| Component | Supply route |
| --- | --- |
| Existing GitHub tree | Recorded base commit `be520bcd40748abfc03e4ff9b64bf244650c5367`; earlier challenges preserved |
| Proposed v6 source, tests and docs | Exact [publication allowlist](PUBLICATION_ALLOWLIST.json); **not committed/published in this phase** |
| 144 absent runtime files | Approved owner-supplied private mirror/bundle; no independent public download established |
| Python packages | Public package index; successful fresh Phase 3 installations retained and checked again |
| Supplementary semantic demo | Separate Neo4j database, cached MiniLM assets and privately rotated credentials; not tested here |
| Optional research reproduction | Additional frozen inputs/environments; [results index](../COMMUNITY_V6_PHASE3_20261106_v1/RESULTS_INDEX.md) distinguishes saved results from reruns |

The 190-file inventory is pinned by SHA-256
`5a06766aa1188ebb5d69397b1e0684b67da102e59f53d5dc57cc0297286844e6`.
Do not change its hashes, remove old guard-required reports, substitute registry
updates, or recreate fitted models to fill gaps. Four executable joblib files
must come from a trusted owner; checksums alone do not make arbitrary pickles safe.

## 1. Prepare source and environments

Until publication, the review-only source export can be produced from this
workspace (new destination each time):

```bash
python3.12 -B reports/reproducibility/COMMUNITY_V6_PHASE4_20261106_v1/prepare_workspace.py --destination /private/tmp/htt-v6-team-review
```

This is a local `git archive` plus exact source overlay, not a remote clone.
After eventual approved publication, a normal clone must be tested separately.
From the **new project root**, create absent environments only:

```bash
python3.12 -m venv .venv-full-system
.venv-full-system/bin/python -I -B -m pip --isolated install -r reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/requirements-ui.txt
python3.12 -m venv .venv-vector-rag
.venv-vector-rag/bin/python -I -B -m pip --isolated install -r reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/requirements-worker.txt
```

UI and worker have deliberately different NumPy versions. Do not merge these
environments. The worker directory name is an inherited interface, not a Vector
RAG dependency. Python 3.12.14 / Intel macOS is the tested platform. The exact
fresh-installed package sets are retained in Phase 3's
[environment record](../COMMUNITY_V6_PHASE3_20261106_v1/ENVIRONMENTS.json).

## 2. Obtain and verify approved assets

**Owner-local test only** — create a new private bundle outside the repository:

```bash
python3.12 -B reports/reproducibility/COMMUNITY_V6_PHASE4_20261106_v1/runtime_bundle.py create-private --source . --candidate /private/tmp/htt-v6-team-review --archive /private/tmp/HTT-COMMUNITY-V6-PRIVATE-RUNTIME-v1.tar --trusted-local-assets
```

The owner must approve recipient access and provide the archive SHA-256 through a
trusted channel. Do not use an untrusted download plus a checksum supplied only by
that same download as evidence of authenticity. The tested private artifact was
**144 files / 37,521,267 payload bytes**, **37,683,200 archive bytes**, SHA-256:

```text
7b6944290de538c4ce1fcc196199e6c6ed60c71030e6cff0abd59918907e3fa5
```

Install into the new checkout (never the development tree):

```bash
python3.12 -B reports/reproducibility/COMMUNITY_V6_PHASE4_20261106_v1/runtime_bundle.py install --archive /private/tmp/HTT-COMMUNITY-V6-PRIVATE-RUNTIME-v1.tar --destination /private/tmp/htt-v6-team-review --trusted-archive-sha256 7b6944290de538c4ce1fcc196199e6c6ed60c71030e6cff0abd59918907e3fa5
```

Only that exact tested archive has this hash. Packaging from a different source
overlay may require a different missing-file subset/hash; verify the actual
receipt. The installer verifies all members before copying, rejects traversal,
symlinks, extra/duplicate members, incomplete coverage and conflicting existing
bytes, and rechecks all 190 required files. A failed install is not automatically
deleted or repaired. This is not a public hosting service or a software signature.

From the provisioned root:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/provision.py --check-environments
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/app.py --inspect
```

Require `READY_LOCAL` and `OK`. Source-only is expected to fail closed.

## 3. Launch and inspect all five pages

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 .venv-full-system/bin/python -B -m streamlit run reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/app.py --server.address 127.0.0.1 --server.port 8510 --server.headless true --browser.gatherUsageStats false
```

Open <http://127.0.0.1:8510/>. No credentials need to be entered.

1. Trial Intelligence: NCT00206232 → Baylor College of Medicine, Spironolactone,
   seven registered planned outcomes with trial-bound citations. Survival-benefit
   questions abstain; NCT99999999 is outside the cohort; missing outcomes for
   NCT00000475 do not establish absence of originally registered outcomes.
2. Community Explorer: NCT00206232 → saved B3 membership, source-linked shared
   relationships; 904 exploratory groups / 820 singletons; LLM disabled.
3. Phase and Intervention Explorer: NA + DRUG → 115; descriptive, not predictive.
4. Operational Risk Dashboard: 329 binary-evaluable records, displayed ROC-AUC
   0.487; release **BLOCKED**, not a validated ongoing-trial forecast.
5. Scenario Lab: load 257 development profiles, acknowledge research warnings,
   select NCT03015402, change planned enrollment 26 → 39. Four saved-model scores,
   zero fits/writes. Not causal, not prospectively validated; unmodeled risk
   categories remain Not Modeled.

The first scenario failure from Phase 3 remains unexplained. This phase's fresh
process succeeded without retry; OS cache coldness was not controlled. If loading
fails, retain the authored error and diagnostic code; do not increase timeouts,
disable checks or claim a result. Rehearse before a demonstration.

## Tests and handoff instrumentation

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 .venv-full-system/bin/python -B -m unittest discover -s reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/tests -p 'test_*.py' -v
python3.12 -B -m unittest discover -s reports/reproducibility/COMMUNITY_V6_PHASE4_20261106_v1/tests -p 'test_*.py' -v
```

The new tools' seven tests are independent of the 24 UI/integrity methods.
`run_handoff.py --root NEW_CHECKOUT --output NEW_RESULT.json`, run with the fresh
UI Python, executes those 24 methods once with scenario first and records safe
worker timings/codes. It requires loopback bind permission for its separate
server check; AppTest success is not the same as HTTP startup. It saves neither
stderr/configuration nor credential values. The actual sandbox bind denial and
subsequent authorized health check are both retained, not hidden.

No training, Neo4j, Ollama, embeddings, publication, model replacement or frozen
result regeneration is part of this handoff.
