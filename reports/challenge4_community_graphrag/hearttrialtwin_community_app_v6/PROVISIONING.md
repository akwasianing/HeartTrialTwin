# v6 provisioning and publication boundary

## What has actually been tested

The existing Intel Mac / Python 3.12 setup passes read-only asset and dependency
preflight. The new checker also rejects a temporary empty checkout, missing
assets, changed bytes, modified receipts and unsafe paths. It does not silently
copy files, install packages, download models, connect to services or rebuild
research outputs. This is a **tested provisioning check**, not a demonstrated
clean-clone installation or a standalone public deployment.

The exact inventory is [runtime_integrity_v1.json](runtime_integrity_v1.json):
**187 files / 40,539,404 bytes**. Paths are relative to the project root. Hashes
come from the existing graph, base-package, dashboard and historical-source
manifests, plus a new snapshot of the reviewed current application dependencies.
The B3 pin comes from the preserved community exploration manifest's
`inputs_sha256`; it is not a newly computed replacement community result.

The verifier and its receipt pin are review-controlled source, not a digital
signature or protection against an attacker who can edit the whole application.
Keep runtime evidence read-only. No historical manifest was rewritten.

## Runtime assets and distribution decisions

| Category | Needed by main v6? | Provision/publication policy |
| --- | --- | --- |
| v6 source, tests, requirements, receipt and documentation | Yes | Suitable for focused publication after final security review; nothing is staged automatically |
| Preserved v4 core/evidence renderer; integrated `src/`; original CSV evidence adapter; full-cohort validation modules | Yes | Source dependencies must retain the relative paths in the inventory |
| Entire pinned 26-file graph payload (including source-cache JSONLs checked by the unchanged CSV adapter), membership and manifest; B3 JSON and provenance manifest | Yes | Separately provision exact archived versions; review registry redistribution terms before publishing derived records |
| Original `HEARTTRIALTWIN_FINAL_20261102` package | Yes | Existing `verify_base()` checks the whole package, including report/poster files. Preserve all listed bytes, even when a file is not displayed |
| Dashboard tables/figures and later independent-evaluation JSON | Yes | Lightweight evidence, but review scientific scope and source terms before committing |
| Historical eligibility audit and 22 development-observation archive caches | Yes for complete runtime preflight/scenario support | External checksum-verified source artifacts; no current-record substitution or fresh reconstruction |
| Four original fitted LR/joblib files | Yes under unchanged base-package guard and scenario replay | Trusted external owner-supplied artifacts; **do not add model weights automatically**. Hash verification precedes any deserialization |
| Python virtual environments | Yes locally, not as copied directories | Create/install separately; never commit environments |
| Neo4j, credentials, Ollama, Chroma, MiniLM/GNN weights or embedding arrays | No | Not needed by the main app; supplementary semantic demo has separate requirements |
| Raw 2.53 GB AACT ZIP, private databases, backup archives, unrelated build outputs | No | Keep local/excluded; never use blanket staging |

No patient-level records are introduced. Public registry provenance does not
automatically grant a new redistribution license for every derived bundle.
An approved external mirror must contain only the inventory paths, not a copy
of the developer's whole working directory or private configuration.

## New-team procedure (installation recipe not executed in this milestone)

1. Obtain the reviewed source revision and an owner-approved, checksum-pinned
   runtime bundle. Preserve the inventory's root-relative layout. A clone alone
   intentionally lacks several required artifacts. Do not replace missing
   frozen models with retraining or regenerate historical manifests.
2. On Python 3.12, create the two named environments **only if absent**. Do not
   overwrite the project's existing environments or upgrade them in place:

   ```bash
   python3.12 -m venv .venv-full-system
   .venv-full-system/bin/python -m pip install -r reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/requirements-ui.txt
   python3.12 -m venv .venv-vector-rag
   .venv-vector-rag/bin/python -m pip install -r reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/requirements-worker.txt
   ```

   The worker's historical directory name is part of the preserved subprocess
   interface; the main v6 worker does not require Vector RAG or a MiniLM model.
   Keep scikit-learn 1.9.1 in this worker, separate from the older classification
   application's scikit-learn 1.6.1. Existing Vector/GraphRAG environments remain
   intact; these minimal requirements are not instructions to remove packages.
3. Print the exact inventory if necessary, without exposing credentials:

   ```bash
   .venv-full-system/bin/python -B reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/provision.py --inventory
   ```

4. Validate an external mirror **without copying** it:

   ```bash
   .venv-full-system/bin/python -B reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/provision.py --assets-root /path/to/approved/project-layout
   ```

   Only an already-reviewed bundle with every expected hash is acceptable.
   The checker itself is read-only. An external mirror is not automatically
   installed, executed or published. After approved assets are provisioned at
   the project-relative paths, run the README's preflight and launch commands.
5. Require `READY_LOCAL` with no asset/environment failures, run the offline
   tests and rehearse all five pages. Record a separate clean-machine receipt
   before claiming clean-environment reproducibility.

This milestone installed nothing and tested the already provisioned local
environment, not package availability on another platform. Windows/Linux and
other Python versions remain unverified. The underlying source and worker
dependencies must be included deliberately in a future publication allowlist.

## Credential action — external service, not a main-app dependency

The prior publication review documents a real local password exposure in the
old `full_cohort_graphrag/.env.example` template and an unreachable local Git
object. The affected connection is the **dedicated full-cohort Neo4j account**
identified privately by `FULL_GRAPHRAG_NEO4J_USERNAME` for the local
`hearttrialtwin-full2824` database. This is not evidence that the five-trial Aura
password was exposed. No secret value or private connection string is included
here, and no authentication with the exposed value was attempted.

Required human action: privately rotate/revoke that Neo4j credential (and any
reused credential), or provision a fresh least-privilege read-only account and
revoke the old access. Keep new configuration only in ignored private storage.
The earlier scan found no known-secret match in reachable published/local-ref
history, but cannot rule out external copies or certify the unchanged password
safe. Removing a template value does not revoke a credential.

The main v6 app and its tests do not load `.env` or connect to Neo4j. It may be
demonstrated offline while this action remains pending. Do not run the separate
live Neo4j/MiniLM demonstration using the exposed credential. No passwords,
accounts, grants, data or private configuration were changed in this phase.
