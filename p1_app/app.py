#!/usr/bin/env python3
"""Streamlit interface for the HeartTrialTwin temporal baseline."""

from __future__ import annotations

import json
from collections.abc import Callable

import streamlit as st

from core import (
    get_exact_evidence,
    get_trial_result,
    load_runtime,
    make_review_record,
    missing_artefacts,
)
from explain import generate_explanation, generate_failure_explanation


st.set_page_config(
    page_title="HeartTrialTwin Model-Release Readiness Review",
    page_icon="🫀",
    layout="wide",
)


@st.cache_data
def cached_runtime():
    return load_runtime()


def render_provenance(evidence: dict) -> None:
    st.markdown("### Verified exact-NCT provenance")
    left, right = st.columns(2)
    left.markdown(
        f"**NCT ID:** `{evidence['nct_id']}`  \n"
        f"**Submission date:** `{evidence['study_first_submitted_date']}`  \n"
        f"**Submission year:** `{evidence['submission_year']}`  \n"
        f"**Cohort:** `{evidence['dataset_version']}`"
    )
    right.markdown(
        f"**Source file:** `{evidence['source_file']}`  \n"
        f"**Source field:** `{evidence['source_field']}`  \n"
        f"**Model version:** `{evidence['model_version']}`  \n"
        f"**Prediction point:** {evidence['prediction_point']}"
    )
    with st.expander("Historical-data limitation", expanded=True):
        st.write(evidence["historical_data_limitation"])


def render_review(
    selected: str,
    explanation: dict,
    revision_factory: Callable[[str], dict],
) -> None:
    st.markdown("### Human review")
    st.warning(
        "The reviewer audit log is session-only. Download the log before reloading or "
        "closing the browser if you need to preserve it."
    )
    action_label = st.radio(
        "Review decision",
        ["Accept", "Reject", "Request revision"],
        horizontal=True,
        key=f"review_action_{selected}",
    )
    comment = st.text_area(
        "Reviewer feedback",
        key=f"review_comment_{selected}",
        placeholder="Required for rejection or revision; kept separate from system-generated text.",
    )

    if action_label == "Request revision":
        if st.button("Generate revised explanation", type="primary"):
            if not comment.strip():
                st.error("Specific feedback is required to request a revision.")
            else:
                revised = revision_factory(comment)
                st.session_state.revised_explanations[selected] = revised
                st.session_state.review_log.append(
                    make_review_record(selected, "request_revision", comment, revised)
                )
                st.success("Explanation revised. Stored model and evidence values were unchanged.")
                st.rerun()
    elif st.button("Submit review", type="primary"):
        action = "accept" if action_label == "Accept" else "reject"
        try:
            record = make_review_record(selected, action, comment, explanation)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state.review_log.append(record)
            st.success(f"Review recorded: {action}.")

    if st.session_state.review_log:
        with st.expander("Reviewer audit log (session-only)"):
            st.json(st.session_state.review_log)
            st.download_button(
                "Download review log",
                data=json.dumps(st.session_state.review_log, indent=2),
                file_name="hearttrialtwin_review_log.json",
                mime="application/json",
            )


def main() -> None:
    st.title("HeartTrialTwin")
    st.subheader("Model-release readiness review for a selected clinical trial.")
    st.caption(
        "Human selects an NCT ID → exact-record provenance → model validation and "
        "release check → grounded readiness result → human review."
    )
    st.warning(
        "This workflow reviews whether an existing model result may be released. It does "
        "not perform clinical risk prediction or trial-design analysis."
    )

    missing = missing_artefacts()
    if missing:
        st.error(f"Application artifacts are missing: {', '.join(missing)}")
        st.stop()

    predictions, shap_values, evidence_cache, metrics, shap_audit = cached_runtime()
    validation = metrics["validation_metrics"]
    with st.sidebar:
        st.header("Validation assessment")
        st.metric("AUPRC", f"{validation['auprc']:.3f}")
        st.caption(f"No-skill prevalence baseline: {validation['prevalence_no_skill_auprc']:.3f}")
        st.metric("AUROC", f"{validation['auroc']:.3f}")
        st.metric("Brier score", f"{validation['brier_score']:.3f}")
        st.caption("Validation: 2018–2020. Final test: locked and not evaluated.")
        st.divider()
        st.caption(f"Dataset: {metrics['dataset_version']}")
        st.caption(f"Model: {metrics['model_version']}")

    if "revised_explanations" not in st.session_state:
        st.session_state.revised_explanations = {}
    if "review_log" not in st.session_state:
        st.session_state.review_log = []

    nct_ids = sorted(evidence_cache)
    default_id = "NCT03414632" if "NCT03414632" in nct_ids else nct_ids[0]
    selected = st.selectbox(
        "Select an eligible NCT ID",
        nct_ids,
        index=nct_ids.index(default_id),
        help="All selections come from frozen cohort HTT-P1-AACT-20260905.",
    )
    try:
        evidence = get_exact_evidence(selected, evidence_cache)
    except (KeyError, RuntimeError) as exc:
        st.error(str(exc))
        st.stop()

    st.markdown(f"## {selected}")
    render_provenance(evidence)

    # Safe failure state: provenance and review remain functional, but no trial-level
    # probability, SHAP attribution, or risk explanation is released.
    if metrics["release_status"] != "PASS":
        st.markdown("### Release-readiness result")
        r1, r2, r3 = st.columns(3)
        r1.metric("Cohort membership", "VERIFIED")
        r2.metric("Model release status", "BLOCKED")
        r3.metric("Trial-level risk output", "NOT RELEASED")
        st.error(
            "Trial-level risk output is blocked. The temporal baseline failed its "
            "predeclared basic validation release checks."
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Validation AUPRC", f"{validation['auprc']:.6f}")
        c2.metric("Prevalence baseline", f"{validation['prevalence_no_skill_auprc']:.6f}")
        c3.metric("Validation AUROC", f"{validation['auroc']:.6f}")
        st.caption(
            "Because AUPRC was below prevalence and AUROC was below 0.5, the app does "
            "not display a selected-trial probability, SHAP attribution, or risk explanation."
        )
        intervals = metrics["bootstrap_95_percent_intervals"]
        with st.expander("Uncertainty and evidence limits", expanded=True):
            st.write(
                "Validation AUPRC bootstrap 95% interval: "
                f"{intervals['auprc'][0]:.6f} to {intervals['auprc'][1]:.6f}."
            )
            st.write(
                "Validation AUROC bootstrap 95% interval: "
                f"{intervals['auroc'][0]:.6f} to {intervals['auroc'][1]:.6f}."
            )
            st.write(evidence["historical_data_limitation"])
        original = generate_failure_explanation(metrics, evidence)
        explanation = st.session_state.revised_explanations.get(selected, original)
        st.markdown("### Grounded release-readiness explanation")
        st.info(explanation["text"])
        st.caption(
            f"Generator: {explanation['generator']} · Revision mode: "
            f"{explanation['revision_mode']} · Not LLM-generated"
        )
        render_review(
            selected,
            explanation,
            lambda feedback: generate_failure_explanation(metrics, evidence, feedback),
        )
        st.stop()

    result, evidence = get_trial_result(selected, predictions, shap_values, evidence_cache)
    probability = float(result["predicted_probability"])
    shap_value = float(result["submission_year_shap_log_odds"])
    shap_ready = bool(result["shap_enabled"]) and bool(shap_audit["shap_enabled"])

    c1, c2, c3 = st.columns(3)
    c1.metric("Predicted discontinuation probability", f"{probability:.2%}")
    c2.metric("Verified submission year", str(evidence["submission_year"]))
    if shap_ready:
        c3.metric("Submission-year SHAP", f"{shap_value:+.6f} log-odds")
    else:
        c3.metric("Submission-year SHAP", "Disabled")
        st.error("SHAP additivity validation failed; no attribution is displayed.")

    if not shap_ready:
        st.stop()
    st.markdown("### Model attribution")
    st.code(
        f"{float(result['shap_base_log_odds']):+.6f} + {shap_value:+.6f} = "
        f"{float(result['model_decision_log_odds']):+.6f} log-odds"
    )
    st.caption(
        "The SHAP contribution is on the log-odds scale. It is not a probability-point "
        "change and does not establish causation."
    )

    original = generate_explanation(result, evidence)
    explanation = st.session_state.revised_explanations.get(selected, original)
    st.markdown("### Grounded deterministic explanation")
    st.info(explanation["text"])
    st.caption(
        f"Generator: {explanation['generator']} · Revision mode: "
        f"{explanation['revision_mode']} · Not LLM-generated"
    )
    render_review(
        selected,
        explanation,
        lambda feedback: generate_explanation(result, evidence, feedback),
    )


if __name__ == "__main__":
    main()
