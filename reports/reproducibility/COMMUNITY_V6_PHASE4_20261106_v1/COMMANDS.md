# Phase 4 actual commands and outcomes

November 6, 2026. Run from the project root unless a different root is specified.
All Phase 2 application/source bytes and Phase 3 records were preserved. No
Neo4j/Ollama requests, credential reads, training or result regeneration occurred.

## Recovery and source-only export

```bash
git branch --show-current
git rev-parse HEAD
git status --short -uno
git diff --cached --name-only
python3.12 -B reports/reproducibility/COMMUNITY_V6_PHASE3_20261106_v1/prepare_workspace.py --destination /private/tmp/hearttrialtwin-phase4-20261106/source --ui-env /private/tmp/hearttrialtwin-phase3.olTGJX/install_probe_ui --worker-env /private/tmp/hearttrialtwin-phase3.olTGJX/install_probe_worker
```

Branch `codex/v6-submission-readiness`, base `be520bcd40748abfc03e4ff9b64bf244650c5367`.
The export preceded Phase 4 README changes; 144 required files were absent.
The new Phase 4 `prepare_workspace.py` supports the final reviewed README overlay
without changing Phase 3's historical hash-bound selection.

## Scoped asset scan and private archive

The available bundled Python (PDF/Pillow already present, no install) ran:

```bash
python -B reports/reproducibility/COMMUNITY_V6_PHASE4_20261106_v1/audit_assets.py --candidate /private/tmp/hearttrialtwin-phase3.olTGJX/final_source_review2
python3.12 -B reports/reproducibility/COMMUNITY_V6_PHASE4_20261106_v1/runtime_bundle.py create-private --source . --candidate /private/tmp/hearttrialtwin-phase4-20261106/source --archive /private/tmp/hearttrialtwin-phase4-20261106/HTT-COMMUNITY-V6-PRIVATE-RUNTIME-v1.tar --trusted-local-assets
python3.12 -B reports/reproducibility/COMMUNITY_V6_PHASE4_20261106_v1/runtime_bundle.py install --archive /private/tmp/hearttrialtwin-phase4-20261106/HTT-COMMUNITY-V6-PRIVATE-RUNTIME-v1.tar --destination /private/tmp/hearttrialtwin-phase4-20261106/source --trusted-archive-sha256 7b6944290de538c4ce1fcc196199e6c6ed60c71030e6cff0abd59918907e3fa5
```

First scan used the Phase 4 source directory before provisioning; the final
metadata regeneration used Phase 3's still source-only mirror with the same
missing set. The archive creation happened once. Install copied 144 files and
verified all 190. The archive stayed private outside the repository. The actual
PDF helper executable was obtained through the bundled dependency locator; no
extra package/environment was installed. It is not an application dependency.

## Tests and safe worker instrumentation

```bash
python3.12 -B -m unittest discover -s reports/reproducibility/COMMUNITY_V6_PHASE4_20261106_v1/tests -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 /private/tmp/hearttrialtwin-phase3.olTGJX/install_probe_ui/bin/python -B reports/reproducibility/COMMUNITY_V6_PHASE4_20261106_v1/run_handoff.py --root /private/tmp/hearttrialtwin-phase4-20261106/source --output reports/reproducibility/COMMUNITY_V6_PHASE4_20261106_v1/EXECUTION_RESULTS.json
```

Seven new handoff tests passed (0.157 s). The runner checked both fresh venvs with
`python -I -B -m pip --isolated check`, ran provision preflight and the existing
24 methods once, scenario first: **24 passed / 0 failures / 0 errors / 0 skips**.
It used an absolute output path in the actual invocation because the runner
switches to the isolated project root. See [EXECUTION_RESULTS.json](EXECUTION_RESULTS.json).

## Actual server startup

From `/private/tmp/hearttrialtwin-phase4-20261106/source`:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 .venv-full-system/bin/python -B -m streamlit run reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/app.py --server.address 127.0.0.1 --server.port 8512 --server.headless true --browser.gatherUsageStats false
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8512/_stcore/health
```

Sandbox socket binding failed with `PermissionError: [Errno 1]`. The identical
server command was authorized outside the sandbox, started, returned `ok` to the
authorized health check, and stopped via Ctrl-C (exit 0). No production fix or
timeout change was needed. Only this test server was stopped.

## Final review

```bash
git diff --check
git status --short
```

Final source proposal paths/hashes are recorded separately from the private
bundle. Focused staged-byte checks and publication receipts record subsequent
explicitly authorized Git operations; no blanket `git add .` is used.
