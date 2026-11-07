# Static deployment readiness — NOT deployed

GitHub Pages is suitable for this buildless, dependency-free static folder. The
[official custom-workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
describes Pages configuration and artifact deployment. On November 6, 2026, a
read-only `GET repos/akwasianing/HeartTrialTwin/pages` returned HTTP 404: no Pages
site was accessible through the current account. This is not proof about all
possible external hosting. No setting, environment or hosting resource changed.

## Proposed handoff, requiring separate explicit approval

1. Review/merge the source-only demo PR. The existing submission remains usable
   without this demo; do not merge incomplete work for the deadline.
2. Separately authorize GitHub Pages. Choose GitHub Actions as its publishing
   source after reviewing account/repository permissions.
3. Review the inert `deployment/pages.yml.example` here. Only after approval,
   copy it to `.github/workflows/public-evidence-pages.yml` in a separate change.
   It has manual dispatch only and requires the main branch. It is **not** an
   active workflow in this PR.
4. Upload **only `demos/public_evidence_v1/site/`**. Never upload the repository
   root, runtime bundles, .env, local environments, databases or model files.
5. Manually run the approved workflow; verify the actual returned Pages URL,
   seven-outcome listing, citations, HTTPS/package hash and abstention before
   advertising it. No URL is presented here as already live.

The same folder can be served by another approved static HTTPS host. Its relative
asset URLs work under a project subpath. No server secrets or backend are needed.
The static site does not need a database and cannot change Neo4j. It is an
evidence replay, not a replacement for the full Community v6 research application.

Browser requirements: JavaScript modules and WebCrypto SHA-256 (modern browser,
HTTPS or localhost). Offline operation after HTTP delivery is limited to the
packaged trial; there is no service worker/offline cache claim. Browser integrity
failure disables the replay rather than showing unverified fallback content.
