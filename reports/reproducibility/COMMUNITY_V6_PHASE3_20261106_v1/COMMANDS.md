# Phase 3 command record

Date: November 6, 2026. Run from the repository root unless a `cd` is shown.
The recovered temporary workspace was `hearttrialtwin-phase3.olTGJX` under
`/private/tmp`. The variable below makes the recipe portable and creates a new
directory; it never deletes previous work. No private configuration is copied.

## Repository and preservation inspection

```bash
git branch --show-current
git rev-parse HEAD
git status --porcelain=v1 -uno
git diff --cached --name-only
git diff --check
```

The earlier interrupted session created `codex/v6-submission-readiness`. It was
reused, not recreated. Targeted `sed`/`rg`/file metadata inspection recovered
Phase 2 and the partially installed fresh environments. All 13 Phase 2 files
were compared with their prior SHA-256 values; no bytes changed.

## Fresh dependencies

```bash
HTT_PHASE3_TEMP=$(mktemp -d /private/tmp/hearttrialtwin-phase3.XXXXXX)
python3.12 -m venv "$HTT_PHASE3_TEMP/install_probe_ui"
python3.12 -m venv "$HTT_PHASE3_TEMP/install_probe_worker"
"$HTT_PHASE3_TEMP/install_probe_ui/bin/python" -I -B -m pip --isolated install --disable-pip-version-check --no-input --no-cache-dir --only-binary=:all: --retries 0 --timeout 20 -r reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/requirements-ui.txt
"$HTT_PHASE3_TEMP/install_probe_worker/bin/python" -I -B -m pip --isolated install --disable-pip-version-check --no-input --no-cache-dir --only-binary=:all: --retries 0 --timeout 20 -r reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/requirements-worker.txt
```

Actual recovery reused the successful fresh UI install rather than repeating it;
package metadata and `pip check` verified it. The worker installation completed
in this phase. Original installer timing/log for the UI was not retained.
The restricted UI attempt initially found no distributions; the authorized
network retry installed them. Existing development environments were not touched.

The observed complete package sets are in [ENVIRONMENTS.json](ENVIRONMENTS.json).
[UI](requirements-ui-observed.txt) and [worker](requirements-worker-observed.txt)
observed pins record transitive versions for future replay. These are not
wheel-hash locks or independently verified cross-platform builds. No second
installation was run merely to re-test those exported lists.

## Isolated code and local-asset candidates

```bash
python3.12 -B reports/reproducibility/COMMUNITY_V6_PHASE3_20261106_v1/prepare_workspace.py --destination "$HTT_PHASE3_TEMP/source_only" --ui-env "$HTT_PHASE3_TEMP/install_probe_ui" --worker-env "$HTT_PHASE3_TEMP/install_probe_worker"
python3.12 -B reports/reproducibility/COMMUNITY_V6_PHASE3_20261106_v1/prepare_workspace.py --destination "$HTT_PHASE3_TEMP/provisioned" --provision-local-assets --ui-env "$HTT_PHASE3_TEMP/install_probe_ui" --worker-env "$HTT_PHASE3_TEMP/install_probe_worker"
```

Both start with `git archive` of the recorded base commit plus the exact proposed
source overlay. Neither is a remote clone. The second adds 143 otherwise absent
local runtime files, verified before and after copying. Fresh-environment aliases
avoid reinstalling successful packages; no environment aliases point into the
development project. Source/evidence files are actual copies, not links back to it.
The tested source overlay predates final report-only edits; application bytes and
runtime hashes remain identical. Final allowlist hashes bind the finished docs.

In each candidate, source/inventory preflight was checked. The source-only
candidate reports 143 missing assets and cannot run the complete prototype.
The provisioned candidate reports `READY_LOCAL` with no asset/environment errors.
After the privacy-held legacy helper was excluded from the public proposal, a
final source-only export confirmed **144** missing assets and zero mismatches.
A first attempt at that final export correctly refused differing `.gitignore`
bytes. The new Phase 3 tool was corrected to permit only the two explicitly
reviewed tracked text updates (`README.md` and `.gitignore`); a new destination
then succeeded. No partial workspace or protected source was deleted or repaired.

```bash
cd "$HTT_PHASE3_TEMP/provisioned"
PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 .venv-full-system/bin/python -B reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/provision.py --check-environments
.venv-full-system/bin/python -I -B -m pip --isolated check
.venv-vector-rag/bin/python -I -B -m pip --isolated check
PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 .venv-full-system/bin/python -B -m unittest discover -s reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/tests -p 'test_*.py' -v
```

Actual test invocation used the same unittest discovery in a short Python heredoc
with framework warnings suppressed via `logging.disable(logging.WARNING)`;
it did not suppress failures. Initial result: **23 passed, one error** in 24
tests. The scenario page lacked the expected profile count. The underlying worker
status/error was not captured, so it is not retrospectively called a confirmed
timeout. A direct read-only `ResearchInference().profiles()` diagnostic then
succeeded with 257 profiles in 42.871 s. It did not fit or optimize a model.
One explicitly scoped rerun of the scenario method passed in 11.674 s:

```bash
cd "$HTT_PHASE3_TEMP/provisioned"
PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 .venv-full-system/bin/python -B - <<'PY'
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path('reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/tests').resolve()))
from test_app import AppTests
result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([AppTests('test_scenario_acknowledgement_gate')]))
raise SystemExit(not result.wasSuccessful())
PY
```

No full-suite repeat, automatic application retry, timeout increase, test change
or Phase 2 modification hid the initial failure. A separate isolation probe used
`-I` for direct script execution and failed because it removes the script import
directory; the documented `-B` application command was then used. `-I` remains
appropriate for the installer/metadata commands, not the preserved script imports.

## Server smoke test

```bash
cd "$HTT_PHASE3_TEMP/provisioned"
PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 .venv-full-system/bin/python -B -m streamlit run reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/app.py --server.address 127.0.0.1 --server.port 8511 --server.headless true --browser.gatherUsageStats false
```

In a separate terminal:

```bash
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8511/_stcore/health
```

Returned `ok`. The server started for this test was stopped with Ctrl-C. No other
server was stopped. HTTP health is distinct from the actual five-page AppTest
checks; no browser screenshot or remote deployment is claimed.

## Final lightweight validation

From the development project root, without changing application/research files:

```bash
python3.12 -B -m unittest discover -s reports/reproducibility/COMMUNITY_V6_PHASE3_20261106_v1/tests -p 'test_*.py' -v
git diff --check
git diff --stat
git status --short
```

Also performed: scoped secret/key-pattern review, allowlist hashes, Markdown-link
and whitespace checks, exact Phase 2 preservation, frozen-manifest hashes, saved
metric inspection, graph row recount and saved-community count/ARI aggregation.
No research training, model selection, bootstrap rerun, Neo4j/Ollama request,
staging, commit, push, history rewrite or main-branch update occurred.
