# GitHub Pages deployment review v1

## Scope and authorization boundary

PR #2 is merged. Preparation starts from published main
`c0f9f6904c09bb10eda954c9df0d7daa82000739` on the separate branch
`codex/public-evidence-pages-v1`. This review does not authorize merging the
deployment PR, enabling Pages, or dispatching the workflow. Obtain explicit
owner approval before those operations. The poster QR remains unchanged.

The six-file deployment change consists of the manual workflow, three focused
deployment tests, the hosting instructions, this review, and the landing-page
HTML/CSS adjustment. Existing source evidence, browser validation/rendering code,
Python replay, citation pins and all research/application assets are unchanged.

## Prepared configuration

- `.github/workflows/public-evidence-pages.yml`: manual dispatch only; `main`
  guard; ten-minute job limit; no stored checkout credentials; minimum required
  permissions; `github-pages` environment; no automatic Pages enablement.
- Tests plus `build_site.py --check` run before upload. The evidence is checked,
  not regenerated. Upload path is **only** `demos/public_evidence_v1/site/`.
- The guarded static inventory is exactly `index.html`, `style.css`, `app.mjs`,
  `evidence.mjs`, `integrity.mjs`, `evidence.json`, under 100 KB total, no symlinks.
- Landing buttons: **Launch Demo** → `#evidence-demo`; **View GitHub** →
  `https://github.com/akwasianing/HeartTrialTwin`. Assets use relative URLs so
  the repository's nested source folder is correctly served at the Pages root.
- Actions follow the official GitHub custom-workflow configuration:
  https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages

## Completed checks before approval

| Check | Observed result |
| --- | --- |
| Python replay/deployment suite | 14 passed, 0 failed |
| JavaScript browser-core suite | 8 passed, 0 failed |
| Static evidence integrity | VERIFIED; original 18,960 bytes; 1 sponsor, 1 intervention, 7 outcomes |
| Evidence package SHA-256 | `1eda3e31cd5315f6aab145c8cd3d9548416127b9c0a473309532e40eb517f6f3` |
| Local HTTP startup/assets | Successful; browser package initialized |
| Desktop layout | 1,280 CSS pixels wide; no horizontal overflow; visually reviewed |
| Launch navigation | Correct `#evidence-demo` fragment; interactive form reached |
| Public repository destination | Opens the original public repository; unauthenticated page displays Sign in |
| Sponsor | Baylor College of Medicine; `cite:3db774038cf4618ff9294543` |
| Intervention | Spironolactone; `cite:21f56031bbf8289fe76bfdcb` |
| Outcomes | COMPLETE_LISTING; seven records with original types, time frames and citations |
| Unsupported effectiveness | ABSTAIN; zero factual records |
| Unknown identifier | NOT_FOUND within this replay; zero factual records |
| Browser warnings/errors | None reported for the local demo |
| Diff whitespace check | Passed |

Commands from repository root:

```bash
python3 -I -B -m unittest discover -s demos/public_evidence_v1/tests -p 'test_*.py' -v
python3 -I -B demos/public_evidence_v1/build_site.py --check
node --test demos/public_evidence_v1/tests/test_browser.mjs
git diff --check
python3 -I -B -m http.server 8521 --bind 127.0.0.1 --directory demos/public_evidence_v1/site
```

The browser's requested 390-pixel override did not apply: measured widths stayed
at 1,280, even after reload and a fresh tab. Therefore **new mobile visual QA is
NOT VERIFIED**, rather than falsely reported as passed. The prior PR #2 mobile
screenshots remain historical evidence of the original page. Responsive CSS is
retained; repeat the real mobile check after deployment, using a working viewport
or physical device. Local screenshots are kept outside this publication change.

## Security and scientific boundary

Only previously published, pinned trial evidence is uploaded. No .env, private
connection string, credential, database, raw dataset, model, external runtime
archive, poster or Community v6 file is included. No Neo4j/Ollama call is needed.
Only static HTML/CSS/modules/JSON are served; no third-party browser scripts,
analytics, dynamic HTML injection or arbitrary-question generator is added.

Targeted publication checks and exact file review are not an exhaustive secret
audit. The previously exposed Neo4j credential remains unconfirmed rotated or
revoked, and was not accessed or used here. Private owner remediation remains
necessary before live reuse; it is independent of this credential-free replay.

The site remains **saved-evidence replay**, not live GraphRAG or validated
clinical prediction. Planned outcomes are registered measures, not observed
treatment effects. Snapshot values may include amendments. Integrity checking
is not independent registry validation or proof of account security.

## Post-approval acceptance checks

The Pages API currently returns HTTP 404; no deployment is claimed successful.
After approval, merge normally, select GitHub Actions as Pages source and dispatch
the workflow from main. Read its actual returned URL, then verify public HTTPS,
all six asset requests, unauthenticated navigation, desktop/mobile rendering,
seven-outcome/citation completeness, sponsor/intervention and abstention.

Expected, **unverified** landing URL:
`https://akwasianing.github.io/HeartTrialTwin/`.
Expected, **unverified** Launch Demo URL:
`https://akwasianing.github.io/HeartTrialTwin/#evidence-demo`.
Only after those checks pass should a separately approved poster copy use the
verified landing URL as its QR payload. Preserve the current poster unchanged.
