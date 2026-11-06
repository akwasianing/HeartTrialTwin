# HeartTrialTwin — Model V1 Independent Evaluation Report

**Research status:** Completed, research only; predictive risk release blocked.  
**Evaluation snapshot:** AACT flat archive 4481, created 2026-11-01T05:21:32Z.  
**Assessment:** Status-snapshot conditional comparison of TERMINATED versus COMPLETED, not time-to-event incidence or universal trial-discontinuation probability.

## Design and evidence integrity

- Frozen model: metadata_without_phase logistic regression, SHA-256 `75c63d32bf56262fc2a6a8463401dc96ad84812d4ae9f369360bde134d85eb83`.
- Original protocol lock: `0b390ba1f5e4affc80a9d9eca38f72fb661d0f73faff378dfa4004e8cc9698cc`.
- Outcome-rule amendment lock: `10c5af6fe27a2a08bc5e3764aec8c26126475e9be064473f73c13c14c4af32a1`.
- V3 evaluator compatibility lock: `f9fb1401da60c257d0716a19e8bb0f83ccf380be48a9a51be2de7d94eb4f2d83`.
- Exact evaluator V3: `4b3c7b7e9af1032c2d235db92bf881327a221fdb9d34f6275df593396e8a5171`.
- Outcome-blind scores for 358 provisional trials: `21b17849e96d9daf472eb5d2e43ded31a35c097c4de60eb646996155018f7b8d`.
- Outcome evidence CSV from snapshot 4481: `7159679c39bc0bdf7ed4eba027965ca25ec8d5acad87ec41266b52caf82ca049`.
- Source data included 358/358 selected trial statuses; ZIP member CRC validated. Scores were frozen before unsealing and model/score files were not modified.

## Population and flow

358 provisionally eligible trials were scored. Of these, 289 were COMPLETED and 40 TERMINATED, yielding **329 binary-evaluable trials** and **12.16% observed termination fraction** among the binary-evaluable subset. The remaining **29 WITHDRAWN** were excluded under the prespecified status-only rule. Family/chronology reviews remain pending. At least 365 days of administrative observation opportunity was enforced. No terminal event dates were inferred.

## Primary and secondary results

| Statistic | Estimate | 95% bootstrap interval (if available) |
|---|---:|---:|
| ROC-AUC | 0.486592 | 0.384907–0.588509 |
| Average precision | 0.157487 | 0.092962–0.253863 |
| Brier score | 0.110039 | 0.081349–0.139989 |
| Observed termination fraction (binary-evaluable) | 0.121581 | — |
| Fixed original training-prior comparator Brier | 0.110470 | — |
| Cohort-prevalence reference Brier | 0.106799 | — |
| Calibration logistic intercept | −2.426796 | — |
| Calibration logistic slope | −0.195233 | — |

Bootstrap: 2,000 valid outcome-blind family-cluster percentile draws, seed 20261103; the 329 binary-evaluable trials correspond to 329 family clusters in the reported bootstrap run. Pending family review means these clusters cannot be interpreted as confirmed independent families.

At the **previously specified threshold 0.09**, the confusion matrix was TP 25, FP 173, TN 116, FN 15. Sensitivity 0.625, specificity 0.4014, precision 0.1263, F1 0.2101. This threshold is not suitable for operational alerts on this evidence.

Fixed-width calibration bins: 312 observations with mean prediction 0.09969 and observed termination frequency 0.12179; 17 observations with mean prediction 0.26347 and observed frequency 0.11765. Very small high-score group and negative calibration slope suggest unreliable ranking/calibration, but estimates are uncertain.

## Interpretation

The primary independent evaluation did **not establish discrimination better than chance**: ROC-AUC was 0.487 with CI spanning 0.5. Average precision (0.157) exceeded the binary-evaluable termination prevalence (0.122) by a modest amount, insufficient to establish utility. Brier was only slightly below the fixed historical-prior baseline, and was worse than an oracle within-cohort prevalence-only reference (which must **not** be presented as a prospective usable baseline). The previous 2019–2020 exploratory evaluation had ROC-AUC about 0.560 and AP about 0.215; its Brier cannot be directly compared without accounting for changed prevalence/case mix. The earlier model choice involved exploratory evaluation, so that set was not pristine.

### Limitations

- Outcome is observed overall status at a November 1, 2026 snapshot, **not** an observed terminal transition date. A trial's exact outcome timing is unknown, and 365-day opportunity is not proof of 365-day event ascertainment.
- Excluding withdrawn and other nonbinary statuses restricts the estimand to the status-defined terminal subset; it does not estimate risk across every ongoing trial.
- Provisional family and chronology checks remain pending, despite automated screens.
- Few terminated events (40) and uncertainty limit interpretation.
- Evaluator selected a model developed on the earlier cohort; other comparisons were exploratory. Later outcome labels are now known, removing the 2021–2024 set's untouched-test status for future V2 selection.

## Decision

**Keep model V1 frozen and blocked for predictive deployment.** Its predictions can be generated technically but must not be presented as validated trial-discontinuation probabilities. Continue research on Model V2 with an explicitly versioned protocol and genuinely untouched subsequent validation. Preserve all V1 lock and prediction artifacts unchanged.

*Source: terminal-produced `post_unseal_evaluation_results_status_only_v2.json` supplied by the project owner on 2026-11-03; this report has not independently reopened local raw source data.*
