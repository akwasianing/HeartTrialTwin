# Static deployment handoff — approval required, NOT deployed

GitHub Pages is suitable for this buildless, dependency-free static folder. The
[official custom-workflow documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
describes Pages configuration and artifact deployment. On November 6, 2026, a
read-only `GET repos/akwasianing/HeartTrialTwin/pages` returned HTTP 404: no Pages
site was accessible through the current account. This is not proof about all
possible external hosting. No setting, environment or hosting resource changed.

PR #2 was merged to `main` at
`c0f9f6904c09bb10eda954c9df0d7daa82000739`. A subsequent read-only Pages API
check still returned HTTP 404. No site is claimed live. Deployment preparation
is isolated on `codex/public-evidence-pages-v1`.

## Prepared configuration

`.github/workflows/public-evidence-pages.yml` is the proposed active workflow.
It has **only manual dispatch**, a `main`-only guard and a ten-minute job limit.
It runs the Python/JavaScript tests and verifies the existing deterministic
evidence package without regenerating it. Tests require exactly six public site
files, no symlinks and under 100 KB total before upload. Checkout does not persist
credentials. Only `contents: read`, `pages: write` and `id-token: write` are used;
no repository/application secret is required. There is no automatic Pages
enablement. The historical inert example remains a reference, not a second
workflow to activate.

## Handoff, requiring separate explicit approval

1. Obtain owner approval to merge the **deployment** PR, enable Pages and run
   the manual workflow. PR #2's merge alone does not authorize these actions.
2. Merge through normal GitHub controls, without bypassing branch protections.
3. In repository Settings → Pages → Build and deployment, choose **GitHub
   Actions**. Preserve environment/branch protections. If access is denied, stop
   for the repository owner rather than changing privileges or substituting a host.
4. Run the manual workflow from `main`:

   ```bash
   gh workflow run public-evidence-pages.yml --repo akwasianing/HeartTrialTwin --ref main
   ```

5. Upload **only `demos/public_evidence_v1/site/`** via the workflow. Never upload
   the repository root, runtime bundles, .env, local environments, databases or
   model files. Relative HTML/module/fetch paths resolve correctly beneath the
   `/HeartTrialTwin/` project URL; nested repository paths do not appear in the
   deployed URL.
6. Read the successful deployment's **returned URL**, then verify it in an
   unauthenticated browser over HTTPS. Check landing navigation, sponsor,
   intervention, all seven outcomes/citations, provenance, abstention, desktop
   and mobile layouts, asset requests and JavaScript errors. Do not call it live
   based only on the expected address.

Expected landing address, **not yet live-verified**:
`https://akwasianing.github.io/HeartTrialTwin/`.
Expected Launch Demo target: the same verified landing address plus
`#evidence-demo`; this intentionally scrolls to the interactive replay in the
same page. View GitHub opens `https://github.com/akwasianing/HeartTrialTwin`.

Only after deployment and browser verification should a **separate poster
revision**, approved by its owner, point its QR to the actual landing URL.
Preserve the existing poster and repository QR until then.

The same folder can be served by another approved static HTTPS host. Its relative
asset URLs work under a project subpath. No server secrets or backend are needed.
The static site does not need a database and cannot change Neo4j. It is an
evidence replay, not a replacement for the full Community v6 research application.

Browser requirements: JavaScript modules and WebCrypto SHA-256 (modern browser,
HTTPS or localhost). Offline operation after HTTP delivery is limited to the
packaged trial; there is no service worker/offline cache claim. Browser integrity
failure disables the replay rather than showing unverified fallback content.

The original `validation/publication_review.json` describes the immutable PR #2
package, not the later deployment diff. New deployment changes are separately
reviewed. Prior Neo4j credential rotation remains unconfirmed; do not read/use it.
This static site has no connection to that account or Community v6 runtime.
