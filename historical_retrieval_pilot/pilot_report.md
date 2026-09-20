# HeartTrialTwin historical-record retrieval pilot

**Pilot:** `HTT-HISTORY-RETRIEVAL-PILOT-20260919`  
**Parent dataset:** `HTT-P1-AACT-20260905`  
**Decision:** **NO-GO** for the intended three-task vertical slice by September 21 using the available historical retrieval methods.

## Scope and selection

The pilot attempted 18 records selected without reading outcome labels:

- 4 earliest development records from 1999–2004 (legacy records).
- 4 development records from 2006–2011 selected by salted SHA-256 ordering of NCT ID.
- 4 development records from 2012–2017 selected the same way.
- 6 validation records from 2018–2020 selected the same way.

Only `nct_id`, `study_first_submitted_date`, `submission_year`, and `temporal_group` were loaded from the frozen manifest. The final-test group was not accessed for pilot selection.

## Methods attempted

1. **Official public Record History pages.** The script requested version 1 at `https://clinicaltrials.gov/study/<NCT_ID>?tab=history&a=1` using the existing Python environment and `requests`.
2. **Official browser-interface comparison.** The visible ClinicalTrials.gov interface was checked for selected validation and legacy records.
3. **Known internal structured-history route.** A single prior feasibility request to the route used by the third-party `cthist` implementation returned HTTP 403. It was not retried, altered, or bypassed during this pilot.

The public HTML responses were 94,323-byte Angular application shells. They contained no NCT ID, version content, or historical field data. All 18 responses had the same SHA-256, confirming that HTTP 200 represented the shared client shell rather than 18 retrieved records.

## Results

| Period | Attempted | HTTP 200 shell | Historical records retrieved | Historically eligible |
|---|---:|---:|---:|---:|
| Development, legacy 1999–2004 | 4 | 4 | 0 | 0 |
| Development, 2006–2011 | 4 | 4 | 0 | 0 |
| Development, 2012–2017 | 4 | 4 | 0 | 0 |
| Validation, 2018–2020 | 6 | 6 | 0 | 0 |
| **Total** | **18** | **18** | **0** | **0** |

No version identifier, version submission/publication dates, historical field paths, or historical content hashes could be captured programmatically. The response hashes in `pilot_attempts.csv` are explicitly labeled as shell hashes and must not be treated as record hashes.

## Official-interface comparison

- `NCT03414632` (validation) displayed version 1 dated 2018-01-23 in the official browser interface, matching its frozen first-submitted date. This is promising manual metadata, but the record was not counted as retrieved or eligible because its historical payload could not be captured reproducibly.
- `NCT00000475` (legacy development) displayed version 1 dated 2005-06-23, while the frozen first-submitted date is 1999-10-27. The version-date mismatch and previously observed completed/post-trial content make this record unsuitable for a registration-time predictor set.

The comparison confirms that the browser can render data that are absent from the downloadable HTML shell; it does not establish a scalable extraction method.

## Field coverage

Programmatically verified historical coverage was zero for every proposed predictor, including phase, estimated enrollment, sponsor class, number of arms, allocation, masking, intervention model, title, and brief summary. No current September 2026 value was used as a substitute.

The only cohort-wide verified predictor remains `submission_year`, derived from the frozen manifest's immutable first-submitted date.

## Rejection reasons

- All 18 attempts: public history URL returned the client application shell rather than the selected historical record payload.
- Structured internal history endpoint: HTTP 403; no repeated probing or access-control workaround was attempted.
- Legacy example: earliest displayed version did not align with the recorded first-submission date and contained post-prediction information.
- Manually visible records were not promoted to eligible because manual browsing is not reproducible or scalable for model development.

## Scalability and decision

A sufficiently sized, outcome-blind development and validation subset cannot realistically be collected before September 21 with the accessible method:

- Programmatic retrieval succeeded for 0 of 18 records.
- Manual interface inspection is record-by-record and cannot support hundreds of records with field-level provenance and hashes in the remaining time.
- R and the `cthist` dependency stack are unavailable and were explicitly outside the approved pilot.
- The accessible public API and the pinned September 2026 AACT snapshot provide current records, not the needed initial versions.

Therefore the recommendation is **NO-GO** for the intended verified-historical-predictors → Logistic Regression → SHAP → exact-evidence vertical slice by the deadline. Training with current snapshot values would violate the prediction-point constraint.

## Closest defensible fallback, not approved or implemented

The closest P1-connected fallback is a transparently labeled **single-predictor temporal baseline** using only verified `submission_year`:

- **P1 task 1:** demonstrates a real temporally validated Logistic Regression probability, but only from submission year.
- **P1 task 2:** demonstrates numerically consistent SHAP attribution, limited to the temporal feature.
- **P1 task 3:** demonstrates deterministic grounding in the NCT ID, first-submitted date, stored model probability, and stored SHAP value.

It would not demonstrate useful trial-design factors or a rich exact-evidence explanation and must not be presented as the intended multi-factor HeartTrialTwin system. No fallback work should begin without human approval.

## Files

- `run_history_pilot.py` — reproducible outcome-blind selection and public-page test.
- `pilot_attempts.csv` — one row per attempted NCT ID.
- `pilot_audit.json` — manifest hash, selection method, aggregate results, and method limitations.
- `pilot_report.md` — this report.

The frozen cohort, original notebook, existing manifests, and existing application draft were not modified. No model was trained.
