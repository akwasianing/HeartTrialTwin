# Temporal baseline test results

**Run date:** 2026-09-20  
**Command:** `.venv/bin/python -m pytest p1_app/tests/test_p1.py -v`

## Result

**8 passed, 0 failed, 0 skipped.** The final recorded JUnit run completed in 7.97 seconds.

Machine-readable result: `p1_app/artefacts/pytest_results.xml`.

| Test | Result | Safeguard |
|---|---|---|
| Valid NCT selection | Passed | Exact one-to-one lookup for a frozen NCT ID |
| Invalid NCT ID | Passed | Unknown or missing IDs fail explicitly |
| Development-only training and split integrity | Passed | 1,904/464/456 split; final labels masked; scaler mean matches development only |
| Probability consistency and application block | Passed | Stored value equals `predict_proba`; failed model exposes no probability or SHAP metric in Streamlit |
| SHAP additivity | Passed | Maximum error `2.220446049250313e-16` within `1e-8` tolerance |
| Exact-NCT provenance | Passed | Correct date, field, version, checksum; no outcome fields |
| Failure-explanation fidelity and claim safety | Passed | Actual validation metrics preserved; unsupported causal claims absent |
| Missing evidence and functional revision | Passed | Missing evidence fails; revision changes emphasis without changing stored facts |

The tests exercise the safe failure state. They do not imply acceptable predictive performance.
