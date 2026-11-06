# Community v6 — reproducible setup boundary

This is the **main deterministic offline demo**, not the separate live
Neo4j/MiniLM app. Do not use the previously exposed Neo4j credential: rotation
or revocation remains **unconfirmed by the owner on November 6, 2026**.

## Prerequisites and installation

Supported test platform: Intel macOS, Python 3.12.14. Other platforms are not
certified. Two environments are required because UI NumPy 2.1.3 and the saved
model worker's NumPy 1.26.4/scikit-learn 1.9.1 must remain separate. No MiniLM,
Chroma, PyTorch, Neo4j, Ollama or 2.53 GB AACT download is needed for the main app.

From the project root, on a new checkout, create these environments **only if
absent**. Never overwrite/upgrade the developer's existing environments:

```bash
python3.12 -m venv .venv-full-system
.venv-full-system/bin/python -I -B -m pip --isolated install --no-cache-dir -r reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/requirements-ui.txt
python3.12 -m venv .venv-vector-rag
.venv-vector-rag/bin/python -I -B -m pip --isolated install --no-cache-dir -r reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/requirements-worker.txt
```

The worker's directory name is inherited from the preserved subprocess
interface; it does not mean the main app runs Vector RAG. Use the original
separate environments for earlier Challenge 2 and classification applications.

## Provisioning — currently not a public one-command download

[RUNTIME_ASSETS.json](RUNTIME_ASSETS.json) lists **190 required files** with exact
sizes, SHA-256 hashes, authority, source reference and root-relative destination.
This supplements, without changing, Phase 2's 187-file receipt with the verifier,
receipt itself, and original frozen cohort manifest checked by `load_contract()`.
The preserved Phase 2 source/tests/docs must also be present in the source revision.

Ask the owner for an approved mirror of the externally supplied entries. A
published downloadable runtime bundle has **not** been established. Do not infer
that the documented upstream AACT archive URL supplies the derived CSVs, history
caches or fitted models directly. Four joblib models must remain trusted,
owner-controlled external assets; do not publish or deserialize unknown substitutes.
Source redistribution terms still require review. No credentials belong in a bundle.
The exact preserved `train_exploratory.py` runtime helper is also held out of the
public proposal because its unused training entry point references a private
local authorization attachment. Serving does not open that attachment. Keep the
unchanged helper in the trusted owner bundle; do not rerun its training main or
rewrite it to evade the old package hash guard.

The original base guard checks the entire old package, including prior reports
and poster assets; these are runtime integrity dependencies, **not substitutes
for the missing Version 20 poster**. Do not prune them or rewrite frozen manifests.

Once approved bytes are placed at the documented paths:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/provision.py --check-environments
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/app.py --inspect
```

Require `READY_LOCAL` and `OK`; never change a checksum or backfill with current
registry values to force success. The Phase 3 isolated test also provisions the
original frozen manifest, which Phase 2's narrower receipt does not inventory.

## Launch and documented example

```bash
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B -m streamlit run reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/app.py --server.address 127.0.0.1 --server.port 8510 --server.headless true --browser.gatherUsageStats false
```

Open <http://127.0.0.1:8510/>. Select NCT00206232, then citation-validated lookup:

- **lead sponsor:** Baylor College of Medicine, with source-bound citation.
- **intervention:** Spironolactone, with source-bound citation.
- **planned outcomes:** complete seven-record list, not observed clinical results.
- **unsupported question:** “Did spironolactone improve survival in NCT00206232?”
  → abstention; no treatment-effect claim.
- NCT99999999 → outside this cohort; NCT00000475 outcome lookup → missing-source
  abstention, not evidence that outcomes were never registered.

Visit Community Explorer (exploratory B3 groups), Phase and Intervention Explorer
(NA + DRUG: 115), Operational Risk Dashboard (329 binary-evaluable independent
records; predictive release BLOCKED), and Scenario Lab (257 development profiles;
acknowledgement required for noncausal in-sample score arithmetic).

## Tests

```bash
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B -m unittest discover -s reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/tests -p 'test_*.py' -v
```

These 24 methods test actual local evidence/scenario replay and isolated failure
fixtures, not live services or a new scientific evaluation. Test counts for prior
milestones are historical records, not additive proof of independent replication.

## Reproduce the isolated handoff check

`prepare_workspace.py` exports the recorded tracked commit plus only the exact
publication allowlist. It refuses an existing destination, credentials, unsafe
paths, unexpected symlinks and checksum mismatches. With explicit authorization
it copies the pinned local runtime assets into the **new** destination only.
It never modifies source evidence, Git history, or the original environments.

```bash
python3.12 -B reports/reproducibility/COMMUNITY_V6_PHASE3_20261106_v1/prepare_workspace.py --destination /private/tmp/htt-review-source-only
python3.12 -B reports/reproducibility/COMMUNITY_V6_PHASE3_20261106_v1/prepare_workspace.py --destination /private/tmp/htt-review-provisioned --provision-local-assets
```

Use new paths on reruns; the script does not delete or clean previous workspaces.
Create the two environments inside that new project layout and run the commands
above. Test-only `--ui-env` / `--worker-env` options may alias **separately created
fresh** environments so successful installs need not be repeated. They reject
development-root environments and system-site-packages. Such aliases are a
documented harness convenience, not borrowed development packages or a public
provisioning service. The recorded test used these aliases to recover interrupted
fresh installs. Normal new-team setup creates the named environments directly.

The export is a local tracked-tree snapshot, **not a fresh remote GitHub clone**.
Passing with owner-supplied data does not prove GitHub-only reproducibility.
See [PHASE3_REPORT.md](PHASE3_REPORT.md) for measured results and remaining gates.
