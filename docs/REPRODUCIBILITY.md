# HeartTrialTwin: reproducibility and execution guide

This is the current navigation layer, not a replacement for frozen protocols or
historical handoff records. Community v6 source is now published; older Phase 3/4
reports describe the pre-publication tests at their recorded commits. Their
external-asset limitations still apply. No research result was regenerated for
this documentation update.

## Choose the correct execution scope

| Component | Public clone alone? | Additional requirements |
| --- | --- | --- |
| Python saved-evidence replay | **Yes** | Python 3.10+; standard library only |
| Hosted browser replay | **Yes, no clone needed** | Modern HTTPS browser with JavaScript/WebCrypto |
| Community v6 local research application | **No** | Approved 190-file runtime set, trusted saved models, separate UI/worker environments |
| Supplementary MiniLM + GraphRAG | **No** | Pinned features/model cache, dedicated read-only Neo4j graph, separate environments and privately remediated credentials |
| Frozen GraphSAGE training/benchmark reproduction | **No** | Exact protocol, features, model inputs/checkpoints and recorded ML environment; no test-set tuning |
| Saved aggregate findings/reports | **Inspectable** | Reading a report is not rerunning its experiment |

## Public evidence replay

The public site is [HeartTrialTwin](https://akwasianing.github.io/HeartTrialTwin/).
[Launch Demo](https://akwasianing.github.io/HeartTrialTwin/#evidence-demo) scrolls
to the interactive replay; View GitHub opens the original repository. This is
one verified saved trial, not a live database or general-purpose clinical QA.

From a new clone:

```bash
git clone https://github.com/akwasianing/HeartTrialTwin.git
cd HeartTrialTwin
python3 -I -B demos/public_evidence_v1/replay.py --field outcomes
python3 -I -B demos/public_evidence_v1/replay.py --field sponsor
python3 -I -B demos/public_evidence_v1/replay.py --field intervention
python3 -I -B demos/public_evidence_v1/replay.py --question "Did spironolactone improve survival in NCT00206232?" --json
python3 -I -B -m unittest discover -s demos/public_evidence_v1/tests -p 'test_*.py' -v
python3 -I -B demos/public_evidence_v1/build_site.py --check
```

Python 3.10+ is required; 3.14.6 was tested locally. No pip install, virtual
environment, API key, database, model or private configuration is needed. CLI
facts come from the three published traces and original hash manifest under
`full_cohort_graphrag/semantic_v1/demo_v2/validation/HTT-DEMO-v2-SMOKE-v1/`.
The replay checks source hashes, trial associations, exact records and citations.
Keep those files at their repository-relative locations.

Expected results: Baylor College of Medicine; Spironolactone; seven source-bound
outcomes with `COMPLETE_LISTING` and zero model attempts. The survival question
returns `ABSTAIN`. Unknown/invalid IDs return no facts. Missing/tampered inputs
fail closed; do not silently rebuild them from newer registry records.

Optional browser-core tests and local serving:

```bash
node --test demos/public_evidence_v1/tests/test_browser.mjs
python3 -I -B -m http.server 8521 --bind 127.0.0.1 --directory demos/public_evidence_v1/site
```

Open `http://127.0.0.1:8521/`; stop that server with Ctrl-C. Do not use `file://`.
Node is only needed for the optional development tests, not normal hosted use
or Python replay. The browser verifies an 18,960-byte deterministic projection,
not the full trace bytes anew; [the replay guide](../demos/public_evidence_v1/README.md)
explains this distinction. No npm packages are needed.

## Community v6 local research application

**A source-only clone is insufficient.** The recorded 190-file inventory has
144 missing source-candidate files, totaling 37,521,267 payload bytes. There is
no approved public download for the complete runtime bundle. The owner must
approve distribution and supply the exact frozen files; trusted saved joblib
pipelines are executable objects and must not be replaced by untrusted downloads.

Read these before installation:

- [Phase 4 setup and private provisioning](../reports/reproducibility/COMMUNITY_V6_PHASE4_20261106_v1/SETUP.md).
- [Runtime asset inventory](../reports/reproducibility/COMMUNITY_V6_PHASE3_20261106_v1/RUNTIME_ASSETS.json).
- [Per-file distribution review](../reports/reproducibility/COMMUNITY_V6_PHASE4_20261106_v1/ASSET_DISTRIBUTION_REVIEW.json).
- [Environment record](../reports/reproducibility/COMMUNITY_V6_PHASE3_20261106_v1/ENVIRONMENTS.json).
- [Five-page walkthrough and safeguards](../reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/README.md).

Python 3.12.14 on Intel macOS was the tested full-app platform. Create absent
environments only, from the repository root:

```bash
python3.12 -m venv .venv-full-system
.venv-full-system/bin/python -I -B -m pip --isolated install --no-cache-dir -r reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/requirements-ui.txt
python3.12 -m venv .venv-vector-rag
.venv-vector-rag/bin/python -I -B -m pip --isolated install --no-cache-dir -r reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/requirements-worker.txt
```

These deliberately separate UI and worker dependencies, including different
NumPy versions. The inherited worker environment name is not a requirement to
run Vector RAG. Follow the existing provisioning guide for approved external
assets, then require successful integrity/environment checks before launch:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/provision.py --check-environments
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/app.py --inspect
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B -m streamlit run reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/app.py --server.address 127.0.0.1 --server.port 8510 --server.headless true --browser.gatherUsageStats false
```

Open `http://127.0.0.1:8510/`. The app needs no live Neo4j, Ollama, Chroma or
MiniLM service. It retains session-local human review and deterministic citations;
unvalidated LLM interpretation stays disabled. The Scenario Lab replays frozen
scores only after acknowledgment; it does not train or validate forecasts.

With approved assets and environments, the existing app tests are:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B -m unittest discover -s reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/tests -p 'test_*.py' -v
```

This update did not repeat installations, scenario inference or expensive suites.
Prior [Phase 4 execution results](../reports/reproducibility/COMMUNITY_V6_PHASE4_20261106_v1/EXECUTION_RESULTS.json)
record same-machine provisioned handoff success, not a public GitHub-only full-app
reproduction. The initial Phase 3 scenario error remained unexplained despite
later successful fresh runs; do not hide a recurrence by disabling checks.

## Supplementary research paths

The [MiniLM + GraphRAG guide](../full_cohort_graphrag/semantic_v1/demo_v2/README.md)
documents the separate semantic-search application, pinned 384-dimensional
MiniLM revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, exact NCT routing,
read-only Neo4j retrieval and evidence checks. It needs additional graph/model
assets and private configuration. **Do not use the previously exposed Neo4j
credential**; rotation/revocation has not been confirmed.

The [GraphSAGE experiment guide](../gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/README.md)
records feature generation, authorization, supervised training and evaluation.
The frozen Version 2 splits/embargoes and 61,218 permitted edges must remain
unchanged. Do not retrain or rerun the exposed test set as a setup step.

Graph construction requires the exact checksum-pinned AACT archive and original
cohort manifest; current live registry data are not a substitute. See
[full-cohort preparation](../cohort_scaling/FULL_COHORT_PREPARATION.md) and
[import safeguards](../cohort_scaling/FULL_COHORT_IMPORT.md). No importer is run
by these documentation or public-demo commands.

## Reproducibility boundaries

The 2,824-trial snapshot analysis, 258-record historical development population,
329-record later V1 assessment and older 462-record classifier test are different
scientific populations. See [results/history](RESULTS_AND_HISTORY.md), including
the precise outcome rules and original reports. Archived observations do not
automatically establish initial-registration values or clinical event dates.

No .env, credential, raw archive, private database, external fitted-model bundle
or model cache is added here. The public site is credential-free; this does not
prove that the previously exposed account is safe. Preserve immutable result
hashes, maintain the blocked predictive release and obtain a separately designed
evaluation before making new predictive claims.
