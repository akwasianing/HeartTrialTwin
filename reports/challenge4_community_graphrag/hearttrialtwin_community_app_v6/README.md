# HeartTrialTwin — main research demonstration v6

Local CS 5588 / Hack-A-Roo demonstration over the selected **2,824-trial** cohort,
AACT snapshot **September 5, 2026**. Experimental — not validated for clinical
decision-making. This is registered-evidence exploration, not clinical advice,
treatment-effectiveness prediction or validated ongoing-trial forecasting.

## Inspect and launch

Run from the repository root, not this subdirectory:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/provision.py --check-environments
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/app.py --inspect
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B -m streamlit run reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/app.py --server.address 127.0.0.1 --server.port 8510 --server.headless true --browser.gatherUsageStats false
```

Open <http://127.0.0.1:8510/>. Choose a free port if necessary. Stop your server
with Ctrl-C. Do not start a second server on an occupied port.
Startup verifies the receipt and all required assets; missing/changed inputs
block the application. Do not regenerate a manifest or bypass a guard to force
startup. No Neo4j, Ollama, Chroma, MiniLM weights or embeddings are needed by this
main demonstration. The scenario page uses existing trusted saved LR pipelines
only; it never fits a model.

## Five pages and a short demonstration

1. **Trial Intelligence:** default NCT00206232. Inspect source records, choose
   intervention (Spironolactone) or lead sponsor (Baylor College of Medicine),
   then click **Retrieve citation-validated answer**. Choose planned outcomes
   for the complete **seven-record** listing with types, time frames and
   trial-bound citations. Switching trials/questions hides the old answer.
2. **Community Explorer:** search NCT00206232 or a title. Inspect the saved
   **B3 Louvain seed-42** membership, actual shared source nodes and trial-bound
   planned-outcome lists. There are **904 groups / 820 singletons**. Groups are
   exploratory derived memberships, not clinical subtypes or registered edges.
   Candidate ordering uses exact source intersections, not MiniLM. Community
   attribute counts use distinct trials, not repeated source occurrences.
   Feedback is session-local and downloadable; it does not change data.
3. **Phase and Intervention Explorer:** all 2,824 trials; filter NA + DRUG to
   inspect **115** trials. Categories overlap. Filters are descriptive, not a
   learned ranking. Open source-linked filter evidence if needed.
4. **Operational Risk Dashboard:** inspect **88** descriptive cells and their
   source denominators/intervals, plus **13** unadjusted factor comparisons.
   The separate independent V1 evaluation is **329 binary-evaluable trials**,
   ROC-AUC **0.487**, AP **0.157**, Brier **0.1100**; predictive release remains
   **BLOCKED**. Do not confuse this with the older 462-record classifier test.
5. **Digital Trial-Twin Scenario Lab:** load **257** eligible historical
   development profiles. Acknowledge the research-only warning before replaying
   saved-model scores. NCT03015402 supports the prior 26 → 39 enrollment example.
   This is exploratory, in-sample, noncausal model arithmetic, not a patient
   twin, validated prospective risk estimate or optimal-design recommendation.
   Recruitment, safety, efficacy, delay and phase-transition forecasts are not modeled.

Missing-evidence demonstration: NCT00000475 has no loaded planned outcomes;
the complete-answer validator abstains. Unknown NCT99999999 is outside this
cohort, not proof of nonexistence in the registry. The optional question box
accepts only the selected single NCT scope: “Did spironolactone improve survival
in NCT00206232?” abstains. Source values may include later amendments; original
registration-time availability is not asserted.

**Unvalidated Ollama interpretation and feedback-driven generation are disabled
in v6**, with no enabling flag. Deterministic source explanations and human
feedback remain. Planned measures must never be described as observed results.

## Separate semantic-search demonstration

The preserved [MiniLM + GraphRAG app](../../../full_cohort_graphrag/semantic_v1/demo_v2/README.md)
is supplementary, not embedded or started here. It requires separately
provisioned read-only Neo4j, pinned MiniLM/model assets and its three environments:

```bash
.venv-full-system/bin/python -B -m streamlit run full_cohort_graphrag/semantic_v1/demo_v2/app.py --server.address 127.0.0.1 --server.port 8502
```

Do not reuse the previously exposed credential. Resolve the credential-rotation
gate in [PROVISIONING.md](PROVISIONING.md) before any future live connection.
GraphSAGE remains an experimental comparison, not the default ranker. The saved
ranking benchmark is observed-graph registered-association retrieval, not clinical
prediction or proof of unseen-trial generalization.

## Integrity, provisioning and tests

- [Provisioning, asset distribution and security](PROVISIONING.md)
- [Exact runtime inventory and integrity receipt](runtime_integrity_v1.json)
- [Phase 2 validation record](VALIDATION_PHASE2.md)

The receipt binds existing authoritative manifests and current application code.
It does not rewrite the earlier integration manifest or certify old changed test
logs. The preserved v4 core and base/integrated packages remain dependencies;
copying only this folder is insufficient. `trial_intelligence_v5.py` retains its
historical filename but is the v6-local guided view.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv-full-system/bin/python -B -m unittest discover -s reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/tests -p 'test_*.py' -v
```

Tests use real local CSVs/saved inference plus isolated temporary tamper fixtures;
they do not connect to services, download, train, or alter research evidence.
Passing locally is **not proof of clean-clone reproducibility**. External runtime
artifacts, redistribution permissions and clean-environment execution remain a
separate GitHub handoff gate. No automatic publishing is part of this package.
