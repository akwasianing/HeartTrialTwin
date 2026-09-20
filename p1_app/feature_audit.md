# HeartTrialTwin temporal-baseline feature audit

**Dataset:** `HTT-P1-AACT-20260905`  
**Prediction point:** initial ClinicalTrials.gov submission  
**Implementation status:** constrained technical proof of concept, not a clinically validated model

## Approved predictor

| Field | Verdict | Use |
|---|---|---|
| `submission_year` | **VERIFIED_ELIGIBLE** | Sole model predictor. Derived from the immutable `study_first_submitted_date` in the frozen manifest. |

`study_first_submitted_date` is retained as exact-NCT provenance but is not supplied separately to the model. `nct_id`, `temporal_group`, and `dataset_version` are identifiers or metadata, never predictors.

## Excluded fields

| Field group | Verdict | Reason |
|---|---|---|
| Overall status and `discontinued` | Label only | Direct target leakage if used as predictors. |
| Completion date, results, why-stopped text, termination reason | **VERIFIED_INELIGIBLE** | Post-prediction information. |
| Enrollment and study dates from the 2026 snapshot | **VERIFIED_INELIGIBLE** | May contain actual or amended values. |
| Phase, sponsor, study design, eligibility | **UNRESOLVED** | Initial-version values could not be retrieved programmatically at scale. |
| Brief title, summary, and title-derived features | **UNRESOLVED** | The frozen snapshot may contain amendments made after registration. |
| Conditions and MeSH terms | Cohort logic only | Not predictors in this proof of concept. |
| Study type | Excluded | Constant after the interventional-trial cohort restriction. |
| Temporal group and cohort flags | Split metadata only | They define evaluation membership and cannot be predictive inputs. |

## Historical-retrieval result

The 18-record outcome-blind pilot retrieved zero historical record payloads programmatically. Official history URLs returned a shared client application shell, while the structured internal route returned HTTP 403 and was not bypassed. Current September 2026 values therefore cannot be promoted to registration-time predictors.

## Split safeguards

- Development: 1999–2017; used to fit preprocessing and Logistic Regression.
- Validation: 2018–2020; used only for assessment and documented development decisions.
- Final test: 2021–2024; labels are masked in the derived feature artifact and are not evaluated automatically.

## Interpretation limits

The model estimates an association between submission year and the frozen discontinuation label. Submission year does not reveal trial design, enrollment, sponsor, operational complexity, or clinical causes. SHAP describes the model's log-odds attribution and is neither a causal effect nor a probability-point change.
