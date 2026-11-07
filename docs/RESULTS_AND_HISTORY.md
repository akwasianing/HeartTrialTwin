# HeartTrialTwin: results and development history

The course challenges are successive design and implementation stages of one
capstone. This index preserves the original evidence rather than relabeling
historical experiments as current product performance. The complete
[previous README at the pre-documentation commit](https://github.com/akwasianing/HeartTrialTwin/blob/3c3b0be7951baf940681c59c357f3794e17213d9/README.md)
remains available, including its detailed challenge descriptions and older setup
commands. Its pre-hosting notices are historical, not current site status.

## Evidence map

| Stage | Contribution and scientific scope | Original records |
| --- | --- | --- |
| Challenge 2 | Human review and fail-closed classification vertical slice; its failed release-readiness baseline remains blocked | [Tests/results](../p1_app/TEST_RESULTS.md), [feature audit](../p1_app/feature_audit.md) |
| Earlier frozen classification prototype | Structured protocol fields + eligibility TF-IDF; older 462-record terminal-outcome test, not prospective validation or the later V1 assessment | [Original full-system code](../full_system_app/app.py), [model/data boundary](../DATA.md), previous README above |
| Challenge 3 semantic design | Human design, AI critique and human-controlled schema decisions; original five-trial graph: 26 nodes / 65 relationships | [Semantic notebook](../notebooks/HeartTrialTwin_Challenge3_Semantic_Design.ipynb), [five-trial validation](../artifacts/knowledge_graph/VALIDATION_REPORT.md), [course report](../reports/final_project/CHALLENGE_3_FINAL/HeartTrialTwin_Challenge3_Final_Report.pdf) |
| Full-cohort graph and GraphRAG extension | 2,824 selected trials, exact source identifiers, missingness, parameterized read-only retrieval, citations and abstention | [Graph manifest](../artifacts/cohort_scaling/HTT-KG-AACT-20260905-FULL2824-v1/full_cohort_manifest.json), [retrieval](../full_cohort_graphrag/README.md), [answer safeguards](../full_cohort_graphrag/ANSWER_GENERATION.md) |
| MiniLM and experimental GraphSAGE | Frozen registered-association ranking; observed held-out trial context, not inductive unseen-trial or clinical prediction | [Experiment](../gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/RESULTS.md), [original result JSON](../gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1/evaluation_test/results.json), [diagnostic](../gnn_graphrag/reviews/STEP_66G_1_DIAGNOSTIC_REPORT.md) |
| Challenge 4 community work | B1/B3 sensitivity and stability; exploratory memberships, not confirmed clinical classes | [B1 memberships](../reports/challenge4_community_graphrag/full_cohort_results/louvain_full_cohort_v1.json), [stability](../reports/challenge4_community_graphrag/full_cohort_results/community_stability_v1.json), [B3 sensitivity](../reports/challenge4_community_graphrag/full_cohort_results/community_sensitivity_v2.json) |
| Historical/descriptive extension | Full-cohort patterns, phase/intervention review, historical qualification and noncausal comparisons | [Cohort results](../reports/final_project/HEARTTRIALTWIN_FINAL_20261102/analysis/results.json), [traceable evidence index](../reports/reproducibility/COMMUNITY_V6_PHASE3_20261106_v1/RESULTS_INDEX.md) |
| Later V1 predictive assessment | Status-snapshot conditional TERMINATED-versus-COMPLETED evaluation; release remains BLOCKED | [V1 narrative](../V1_INDEPENDENT_EVALUATION_REPORT.md), [aggregate evidence](../reports/reproducibility/COMMUNITY_V6_PHASE3_20261106_v1/evidence/independent_evaluation_v1.json) |
| Community v6 and public handoff | Integrated five-page local research interface; separately hosted one-trial saved replay | [Community v6](../reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/README.md), [current execution guide](REPRODUCIBILITY.md), [live-site checks](PUBLIC_WEBSITE_VERIFICATION.md) |

## Do not mix populations or endpoints

- **2,824** selected trials: September 5, 2026 snapshot; 2,237 Completed,
  393 Terminated, 194 Withdrawn. Descriptive discontinuation combines
  Terminated + Withdrawn. Current snapshot associations are not future-risk
  predictions; Completed does not mean effective treatment.
- **258** historically qualified development records: a smaller, selected
  research population, not all 2,824 trials and not proof of original-registration
  feature availability. Scenario-replay eligibility is narrower again: the local
  app loads 257 eligible profiles. These are not interchangeable denominators.
- **329** later binary-evaluable V1 records: 289 Completed + 40 Terminated;
  29 Withdrawn excluded from 358 provisionally scored trials. ROC-AUC 0.486592
  (95% interval 0.384907–0.588509), AP 0.157487, Brier 0.110039. No terminal event
  date was inferred. Family and chronology limitations remain in the original
  report. Predictive discrimination and utility were not established.
- **462** earlier classifier test records: a different frozen model/population
  with Terminated/Withdrawn combined. Its reported ROC-AUC 0.6017 is historical
  and must not replace the later V1 result or justify a forecasting release.
- **24 trials / 72 archived observations**: longitudinal feasibility, with nine
  changing trials and ten changed adjacent comparisons. Registry observations
  do not date clinical discontinuation events or validate longitudinal prediction.

## Ranking and community interpretation

The GraphSAGE protocol fixed 1,976 training / 424 validation / 424 test trials,
all 2,824 ranking candidates, and 61,218 masked computational edges. The frozen
test used 2,219 embargo-eligible registered-outcome queries. Query-micro MRR:
TF-IDF 0.07074; MiniLM 0.07619; context pooling 0.07841; trained GraphSAGE 0.01124.
These are association-retrieval scores, not treatment or discontinuation outcomes.
The inspected test comparison is descriptive, not permission for further model
selection. GraphSAGE is retained as a negative research finding, not deployed.

B1 and B3 are trial-community construction versions compared for stability and
fragmentation. B1 seed 42 has 823 communities / 747 singletons; B3 has
904 / 820. Three saved seed-pair ARIs average 0.648 and 0.867 respectively.
Greater stability does not establish clinical validity or improved retrieval.

## Tests are version-specific evidence

The [Challenge 3 final audit](../reports/final_project/STEP_66G_5_v1/FINAL_PROJECT_AUDIT.md)
records **220** passing offline tests at that stage. Later v6 provisioning and
interface tests are recorded in [Phase 2](../reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/VALIDATION_PHASE2.md)
and [Phase 4](../reports/reproducibility/COMMUNITY_V6_PHASE4_20261106_v1/PHASE4_REPORT.md).
They were not all rerun for this documentation update. The public Pages workflow
separately passed **14 Python + 8 JavaScript tests** before deployment. Passing
functional tests is not validation of predictive performance or full-clone asset
availability.

Original course reports, source directories, notebooks, frozen experiments and
older posters remain unchanged. No missing original Human Design artifact is
invented or represented by a conceptual replacement. Future work needs improved
registration-time qualification, independently confirmed evaluation, community
usefulness studies and approved asset distribution—not retrospective test tuning.
