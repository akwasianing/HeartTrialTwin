# Public HeartTrialTwin website: verified November 7, 2026

## Deployment and authorization

The project owner explicitly approved merging deployment PR #3, enabling GitHub
Pages with GitHub Actions, and publishing only the six verified static files.

- [Evidence-replay PR #2](https://github.com/akwasianing/HeartTrialTwin/pull/2): merged.
- [Deployment PR #3](https://github.com/akwasianing/HeartTrialTwin/pull/3): merged normally.
- Deployed main: `3c3b0be7951baf940681c59c357f3794e17213d9`.
- [Manual deployment run](https://github.com/akwasianing/HeartTrialTwin/actions/runs/42345436489): **success**, deploy job 15 seconds.
- Deployment environment ID: `7617416906`; success status returned the exact URL below.
- Pages settings: public, `build_type=workflow`, HTTPS enforced.

**Verified landing URL:** https://akwasianing.github.io/HeartTrialTwin/

**Verified Launch Demo URL:** https://akwasianing.github.io/HeartTrialTwin/#evidence-demo

**View GitHub destination:** https://github.com/akwasianing/HeartTrialTwin

The Launch button scrolls to the interactive replay on the same page. Browser
checks used the unauthenticated in-app browser, not the signed-in GitHub CLI.
The public repository target displayed Sign in and Public. No database/model
service was contacted.

## Actual public checks

| Check | Result |
| --- | --- |
| HTTPS landing and relative nested-path assets | PASS; all six public assets returned HTTP 200 and exactly matched reviewed source bytes |
| Desktop | PASS; measured 1,280 × 900 CSS-pixel viewport, no horizontal overflow, landing/navigation and seven-record replay inspected |
| Mobile | PASS; measured 390 × 844 CSS-pixel viewport, page/scroll width both 390; landing, Launch and outcome evidence inspected |
| NCT00206232 sponsor | Baylor College of Medicine, `cite:3db774038cf4618ff9294543` |
| NCT00206232 intervention | Spironolactone, `cite:21f56031bbf8289fe76bfdcb` |
| Registered outcomes | COMPLETE_LISTING; seven distinct records with original citations, registered types and time frames |
| Source-record disclosure | Correct NCT → HAS_PLANNED_OUTCOME → planned_outcome:1426532164 path and design_outcomes.txt record 1426532164 |
| Effectiveness/survival request | ABSTAIN; zero factual records |
| NCT99999999 | NOT_FOUND within this saved replay; zero records; no registry-nonexistence claim |
| Script-like invalid identifier | INVALID_INPUT; zero records; no markup execution |
| Browser warnings/JavaScript errors | None reported during the live checks |
| CI before upload | 14 Python + 8 JavaScript checks passed; static package verified |

The earlier local mobile override failed to apply. A fresh viewport capability
on the live tab **did** apply and was measured before testing; this supersedes
that verification limitation, not any scientific result. These are desktop/mobile
browser-width checks, not a claim of physical-device or every-browser testing.

Exact outcome citation identifiers observed:

```text
cite:0b1654c7b32dcf6c84b359b6
cite:7cc2203163d432f20b1f0dc9
cite:c39166004f6b4ec2880630ce
cite:afc21d2763ef61bb371ab945
cite:7b224cc3bc6196fe295bdb64
cite:5f7801d0898b5b5096a9fef4
cite:59a973a72a79cfe5535af0c7
```

Screenshots of the actual public desktop/mobile landing and mobile complete
listing were saved locally during verification; no mock screenshot is used as
live evidence. They are not required runtime assets and are not part of this
documentation publication proposal.

## Published surface and provenance

The deployed directory contains exactly six files, totaling **38,522 bytes**:

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| index.html | 5,397 | `9d757949ab74879c23de98cdd5abcd9b81f2962c0f590fd9017727833f66756f` |
| style.css | 5,444 | `1b1da4af41d41b013b8cd5cf78f0d1add7c7b4070a03d6cf73a9e20d89cda6f4` |
| app.mjs | 2,953 | `f600f0bf1f4489d89be239f0460c13a7f4f9608edb8babef48235b81cf8b69f8` |
| evidence.mjs | 5,022 | `8798ca4e509237569dbe52bf3204efe79dfb38aae9e191173a16d190a0491314` |
| integrity.mjs | 746 | `b2c070f6a91c1e66a4ac82df8a897775d432f55c5407c7b556a329091f875e27` |
| evidence.json | 18,960 | `1eda3e31cd5315f6aab145c8cd3d9548416127b9c0a473309532e40eb517f6f3` |

The static projection is derived from previously published traces pinned to
`b57afc6f0bfd24f3821c19bba9221c2b8ec8d471`. Source trace manifest SHA-256:
`37cb033b70248493f2df16de163a831a18042f15c5eae5eb8dee663754c92bb0`.
The browser verifies packaged bytes and trial/citation bindings; Python replay
additionally verifies original trace bytes. Neither check proves clinical truth.

No credentials, raw datasets, fitted models, private runtime archives or
repository-wide files were uploaded. No paid service was enabled. The unconfirmed
Neo4j rotation/revocation remains a separate private security task; that credential
was not read, used or tested. Scoped checks are not an exhaustive secret audit.

## Scientific and maintenance limits

The hosted site is **one-trial saved-evidence replay**, not live GraphRAG,
Community v6, an unrestricted LLM or validated clinical prediction. Planned
outcomes are registered measures, not observed treatment results. Snapshot
values may include amendments. Unsupported facts fail closed.

GitHub emitted a non-fatal Node.js 20 deprecation warning for current official
Pages actions forced to Node.js 24, plus an ubuntu-latest migration notice. The
deployment succeeded; no dependency replacement or workflow bypass was needed.
Monitor future official action updates rather than weakening validation.

The poster QR has **not** been changed. It still points to the repository.
A later owner-approved poster revision may point to the verified landing URL;
then re-export and decode that new PDF/PNG and test both landing options. Preserve
the current approved poster and earlier versions.
