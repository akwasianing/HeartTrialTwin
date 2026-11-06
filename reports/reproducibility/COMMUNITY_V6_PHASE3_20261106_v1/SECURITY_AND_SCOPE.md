# Security and publication scope — Phase 3

Owner confirmation: **rotation/revocation remains unconfirmed** (November 6,
2026). Do not read, authenticate with, copy or publish the previously exposed
credential. No live Neo4j or Ollama test is part of this phase. The main offline
app does not require either service.

The prior exposure was the dedicated local full-cohort Neo4j account referenced
by `FULL_GRAPHRAG_NEO4J_USERNAME` for `hearttrialtwin-full2824`, in an old local
`.env.example` and an unreachable local Git object. Prior checks found no known
private-password match in reachable reviewed history. This is not proof of no
external exposure or of an unchanged password's safety. The owner must privately
rotate/revoke that credential and any reuse before supplementary live access.
No secret value, username or private connection URI is included here.

## Proposed publication, not staging authority

[PUBLICATION_ALLOWLIST.json](PUBLICATION_ALLOWLIST.json) gives exact root-relative
paths, sizes and hashes for this proposed update. [PUBLICATION_FILES.txt](PUBLICATION_FILES.txt)
is its human-readable path list. Existing already-published Challenge 1/2 files
remain untouched. This is not an instruction to stage entire directories.

Exclude `.env` files, secrets, private endpoints/configuration, backups, local
environments, caches, raw AACT archives, historical extraction payloads, private
databases, new model weights, unrelated course files, duplicate READMEs and old
build/render workspaces. Preserve valuable local copies; do not delete them.
The two older already-tracked classification artifacts remain historical repository
content, not newly proposed weights or a claim that the entire repository has none.

New source, tests, integrity metadata and aggregate scientific evidence are
content-review candidates. A safe content scan does not certify account security,
third-party licenses or data redistribution rights. Runtime assets are inventoried
separately and are **not automatically included** in this allowlist.
The unchanged legacy `train_exploratory.py` module is explicitly held out of the
public update: its training main has a private local authorization-file path.
Its serving helpers remain available through the trusted external runtime copy;
the private attachment is not opened during inference or included in any bundle.

No commit, push, merge, history rewrite or force operation is authorized here.
The dedicated `codex/v6-submission-readiness` branch preserves `main` at its
existing commit. Any final publication requires a fresh exact-index review and
resolution of the declared security/distribution gates.
