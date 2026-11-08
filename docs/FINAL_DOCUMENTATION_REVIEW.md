# Final documentation publication review — November 7, 2026

## Scope

Documentation branch: `codex/hearttrialtwin-final-documentation`, based on main
`3c3b0be7951baf940681c59c357f3794e17213d9`. The documentation PR must remain open
for owner review; it does not authorize another merge or deployment.

Exact proposed files:

1. `README.md`: one integrated capstone overview, live demo, results, execution
   boundaries and navigation; approximately 1,300 words rather than lengthy
   challenge-by-challenge implementation descriptions.
2. `docs/REPRODUCIBILITY.md`: public replay versus externally provisioned local
   app and optional research paths, commands and fail-closed requirements.
3. `docs/RESULTS_AND_HISTORY.md`: original reports, different scientific
   populations, saved comparisons and the immutable previous README.
4. `docs/PUBLIC_WEBSITE_VERIFICATION.md`: actual deployment, public browser
   observations, exact public asset hashes and limitations.
5. `docs/FINAL_DOCUMENTATION_REVIEW.md`: this review and publication boundary.
6. [Final reviewed poster PDF](../reports/final_project/HEARTTRIALTWIN_POSTER_FINAL_REVIEWED_v1/final/HeartTrialTwin_Poster_FINAL_REVIEWED_48x36.pdf).
7. `demos/public_evidence_v1/README.md`: correct the now-stale hosting notice,
   current button wording and historical PR #2 inventory context.
8. `demos/public_evidence_v1/DEPLOYMENT.md`: record successful deployment above
   the clearly labeled archived preparation handoff. No workflow/site edit.

No source code, deployed site asset, frozen research record, fitted model,
protocol, original poster or Community v6 file changes. Original challenge
folders are not moved or deleted. The previous README remains available at its
immutable [main commit](https://github.com/akwasianing/HeartTrialTwin/blob/3c3b0be7951baf940681c59c357f3794e17213d9/README.md).

## Final poster identity and publication proposal

The final reviewed PDF and the newer author-named
`figures and charts /version 22/HeartTrialTwin_Poster_FINAL_Obed.pdf` have
**identical bytes**, not merely similar titles. Both are 1,566,262 bytes,
one 48 × 36-inch page, SHA-256:

`3f5b18ebab897d1c12ed031ddaf0714c48650b2bdde001baa93fd5a248621516`.

The PR proposes only the reviewed PDF at the path above, not duplicate exports,
editable sources, earlier posters or the local chart-data package. The named
manual copy and all prior versions remain unchanged. The earlier completed
scientific/rendering/QR review is retained rather than unnecessarily repeated.
The repository QR remains unchanged; no website QR is substituted here.

Read-only PDF checks confirm one page, expected dimensions, identical full text,
no embedded file attachments and no root OpenAction/AA/AcroForm. Targeted text
and metadata checks found no high-signal credential/private-path matches.
This plus the prior actual visual review supports publication of this research
poster; it is not an exhaustive forensic PDF or historical-secret audit. The
inherited terminal-status bitmap is low-resolution, as already documented; the
two revised scientific figures were verified separately at print placement.

The PDF becomes available through the documentation branch/PR. The new root
README and PDF link will reach main only after owner approval and normal merge.
No demonstration-video URL is invented.

## Scientific reconciliation

The update reads saved evidence only; it does not rerun extraction, clustering,
model inference, bootstrap, training or ranking evaluation.

| Claim | Authority/check |
| --- | --- |
| 2,824; 2,237 Completed / 393 Terminated / 194 Withdrawn | Existing cohort results and published review copy agree |
| 28,777 nodes / 79,125 original relationships / 19,740 outcome associations | Pinned full-cohort manifest validation counts |
| B3 904 groups / 820 singletons | Count saved seed-42 membership sizes |
| Mean B1/B3 ARI 0.648 / 0.867 | Saved three pairwise ARIs; no clustering rerun |
| Test MRR 0.07074 / 0.07619 / 0.07841 / 0.01124 | Original TF-IDF / MiniLM / pooling / trained-GraphSAGE query-micro results |
| Test Recall@10 values in README | Original frozen result JSON; no model selection |
| 329 V1 binary evaluable; 289 Completed / 40 Terminated; 29 Withdrawn excluded | Original aggregate flow and V1 narrative |
| V1 AUC 0.487; CI 0.385–0.589; AP 0.157; Brier 0.1100 | Original aggregate values rounded for display, BLOCKED flag retained |
| 258 historical development records, separate 257 scenario profiles | Existing cohort qualification and app walkthrough; not the full research cohort |

[Results/history](RESULTS_AND_HISTORY.md) links the original evidence. Older
462-record classifier metrics are explicitly historical and distinct from later
V1. Association ranking is not clinical prediction; B3 is exploratory; archived
status observation is not an event date. No prospective or causal claim is added.

## Reproduction and navigation checks

- The current public main was shallow-cloned without an overlay or private
  assets. Its head matched `3c3b0be7951baf940681c59c357f3794e17213d9`.
- A clean no-pip Python 3.14.6 interpreter ran **14 replay/deployment tests**:
  all passed, zero failures, 0.182 seconds.
- `build_site.py --check` verified the original 18,960-byte payload unchanged.
- Sponsor, intervention and seven-outcome CLI commands returned the expected
  verified values; successful replay reported zero model attempts. The survival
  question abstained with zero records. No private .env or service was loaded.
- The approved deployment separately passed **8 JavaScript tests** and the
  same 14 Python checks. No expensive application/research suite was repeated.
- Relative documentation targets are checked against published tracked files
  plus the exact proposed documentation/poster set, not merely local untracked
  file presence. Internal heading fragments and command script/requirements paths
  are checked. Public URLs are tested without credentials.
  The initial five Markdown files passed 59 relative links, one heading fragment,
  six command/reference paths and seven distinct public URL targets (HTTP 200).
  After the two supporting corrections, **all 65 relative targets in seven
  Markdown files passed**; the added official GitHub deployment guide is also
  accessible. The clone URL redirects to the correct public repository.
- Full Community v6 installation/provisioning instructions were reconciled with
  the existing requirements, startup code paths and Phase 4 guide. Prior fresh
  environment success is retained, not misrepresented as a new full-app install
  or public-clone reproduction.

## Live site and security

[Public website verification](PUBLIC_WEBSITE_VERIFICATION.md) records actual
unauthenticated HTTPS checks at desktop and mobile widths, all six asset byte
matches, sponsor/intervention, complete outcomes/citations, unknown/invalid IDs
and unsupported-effectiveness abstention. Browser warnings/errors were absent.
Only the original six static files are deployed; nothing in this documentation
change is automatically uploaded by the manual-only workflow.

Targeted text checks cover the exact proposed documentation; PDF text/metadata
and visual provenance were separately reviewed. No passwords, API keys, private
connection strings, .env files, raw registry datasets, private runtime archives,
external model weights or unrelated untracked files are included. This is a
scoped publication review, not proof of secret absence or a repeated exhaustive
history/OCR scan. The previously exposed Neo4j credential remains unconfirmed
rotated/revoked and was not accessed or used. Private owner remediation remains
necessary before live reuse.

Remaining limitations are scientific validity, approved full-app asset
distribution, physical-device/cross-browser coverage and the earlier unexplained
scenario initialization incident—not an unresolved public-demo deployment failure.
