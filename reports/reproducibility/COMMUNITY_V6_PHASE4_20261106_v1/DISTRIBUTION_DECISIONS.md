# Runtime distribution decisions — review, not release approval

## Exact gap and operational necessity

[Per-file decisions](ASSET_DISTRIBUTION_REVIEW.json) cover **all 190 assets**,
41,603,498 bytes, including the exact **144 missing files / 37,521,267 bytes**.
Every entry carries the original SHA-256, expected root-relative location,
authority, missingness, operational need, original-artifact status, source route,
redistribution hold, security notes and approved alternative.

| Missing group | Files | Why needed in the unchanged application |
| --- | ---: | --- |
| Pinned graph and source cache | 22 | Actual evidence; complete graph-manifest payload checked even when a cached table is not displayed |
| Historical registry caches | 22 | Source-grounded scenario record verification |
| Historical eligibility ledger | 1 | Historical profile/source linkage |
| Blocked independent-evaluation summary | 1 | Risk dashboard's saved metrics |
| Frozen base package and whole-package guard | 81 | Analysis/dashboard data and guard-required historical reports/figures, including an old poster |
| Frozen executable models | 4 | Scenario initialization/replay; trusted owner bytes only |
| Legacy runtime helper with private path | 1 | Imported preprocessing/prediction functions; unused training main retains local authorization-file pointer |
| Integrated dashboard/scenario assets | 12 | Saved profile catalogue, membership, scores and figures |
| **Total** | **144** | **None may be silently omitted under current guards** |

Some assets are mechanically guard-required rather than semantically necessary
to render an individual page. This audit does not authorize pruning guards,
editing historical manifests, inventing replacements or rebuilding a slimmer app.
The four small joblib models total 14,012 bytes; their hold is about trusted
executable serialization and owner rights, not large-file size. Phase 3's
`UNSUITABLE_FOR_PUBLIC_DISTRIBUTION` label is a conservative publication policy,
**not evidence of a legal prohibition on distributing owner-trained models**.

## Proposed versioned structure

```text
HTT-COMMUNITY-V6-RUNTIME-v1/
  README / TERMS_AND_ATTRIBUTION / checksum receipt  [future release metadata]
  payload/
    artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1/...
    full_system_feasibility/...                       [only enumerated files]
    reports/final_project/HEARTTRIALTWIN_FINAL_20261102/...
    reports/final_project/HEARTTRIALTWIN_INTEGRATED_20261102_v1/...
```

The tested private `.tar` stores only the exact 144 `payload/` entries. Version,
file hashes and destinations live in the pinned source inventory; archive hash
and byte counts are in [BUNDLE_RECEIPT.json](BUNDLE_RECEIPT.json). It is outside
the repository, mode 0600, and **not uploaded or proposed for Git**. No `.env`,
database, virtual environment, full AACT ZIP or unrelated backup is included.

**Simplest recommendation:** one exact-byte bundle plus trusted checksum and
source revision, supplied privately to an approved instructor/team initially.
After owner rights, content and third-party terms are explicitly cleared, the
same versioning/integrity scheme could be hosted as a GitHub Release asset or
institutional repository download. Neither service, URL, permanence, availability
nor permission is assumed here. If fitted models/private-path artifacts cannot
be publicly cleared, retain a private companion; a public data-only subset will
**not** satisfy the unchanged full-app guard. Source-only inspection remains
possible, but the full demonstration will need approved private access.

## Public source and rights assessment

- The official [ClinicalTrials.gov download guide](https://clinicaltrials.gov/data-api/how-download-study-records)
  explicitly directs users to its [terms](https://clinicaltrials.gov/about-site/terms-conditions)
  and AACT snapshots. Access to public records does not independently license
  every third-party text, project figure, code module or fitted model.
- The official [AACT site](https://aact.ctti-clinicaltrials.org/landing) describes
  a public relational database and historical downloads. The documented original
  September 5, 2026 ZIP is an upstream source, **not** a ready-made download of the
  exact derived graph/cache/model bytes. No fresh ZIP download or availability
  check was performed. Re-fetching current records would not reproduce the pins.
- [CTTI's citation policy](https://ctti-clinicaltrials.org/citation-policy/) asks
  acknowledgement for original and derivative uses. Include CTTI, ClinicalTrials.gov,
  snapshot date and project transformations. This policy alone is not a blanket
  clearance for this assembled package.
- The registry terms page returned only a dynamic shell to this audit tool and
  a guessed AACT terms endpoint was inaccessible. **Full current data-term and
  third-party-text clearance remains unestablished**. No public-domain/ODbL/CC
  license is assigned by inference. Owner/institution must review applicable terms.
- No top-level project LICENSE was located. Owner authorship/licensing permission
  for original code, models and charts must be recorded before a public release.
  Python packages stay on their own package-index/install route; they are not
  bundled here.

## Content and security holds

[RUNTIME_SECURITY_SCAN.json](RUNTIME_SECURITY_SCAN.json) records a bounded scan
of all 190 exact assets: text, decompressed JSON, PNG metadata, PDF text/metadata,
and printable model bytes. Zero credential-pattern findings is **not a proof of
secret absence**. No raster OCR, pickle execution for scanning, new history scan,
credential lookup, authentication test or credential-value matching was done.

Public release holds requiring owner review:

1. `reports/final_project/HEARTTRIALTWIN_FINAL_20261102/modeling/train_exploratory.py`
   retains an unused private authorization attachment pointer (line 129).
2. `reports/final_project/HEARTTRIALTWIN_FINAL_20261102/reports/REPRODUCIBILITY.md`
   retains a machine-local home path (line 6). Neither is a detected password.
3. `nodes_planned_outcome.csv` and `source_cache/design_outcomes.jsonl` retain
   email-like text in the registered description for NCT03688100, source
   `design_outcomes.txt` record 1426275237. This is public-registry descriptive
   text, not identified patient-level data; private permission/terms review is
   still needed before republishing. No address is reproduced here.
4. Four joblib files must be supplied as trusted originals. Never load unknown
   substitute models; no assertion of clinical release is implied by distribution.

The frozen copies remain unchanged. If an owner requires public redaction,
that would require separately versioned assets and explicit compatibility review;
it cannot be achieved by silently editing the present frozen bundle.

The previously exposed dedicated full-cohort Neo4j credential remains unconfirmed
revoked/rotated. It was not read or used. Owner must **privately rotate or revoke
that account credential before supplementary live reuse** and consider earlier
exposure findings. No database deletion/rebuild is needed. The offline demo does
not depend on it. This phase does not repeat or certify prior published-history
checks; see [the preserved security scope](../COMMUNITY_V6_PHASE3_20261106_v1/SECURITY_AND_SCOPE.md).
