#!/usr/bin/env python3
"""Streamlit vertical slice for the immutable full-system LR model."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from explanation import generate_explanation, make_review_record
from runtime import DISCLAIMER, get_trial_input, load_runtime, score_trial


st.set_page_config(page_title="HeartTrialTwin Experimental Model", page_icon="🫀", layout="wide")


@st.cache_resource
def cached_runtime():
    return load_runtime()


def render_review(nct_id: str, result: dict, explanation: dict) -> None:
    st.markdown("### Human review")
    st.caption("Human review is recorded separately and never changes the frozen model output.")
    action_label = st.radio(
        "Review decision",
        ["Accept", "Reject", "Request revision"],
        horizontal=True,
        key=f"review_action_{nct_id}",
    )
    note = st.text_area(
        "Reviewer note",
        placeholder="Required for rejection or revision.",
        key=f"review_note_{nct_id}",
    )
    if action_label == "Request revision":
        if st.button("Generate revised explanation", type="primary"):
            if not note.strip():
                st.error("A reviewer note is required for revision.")
            else:
                revised = generate_explanation(result, note)
                st.session_state.revised_explanations[nct_id] = revised
                st.session_state.review_log.append(
                    make_review_record(nct_id, "request_revision", note, revised)
                )
                st.success("Explanation wording revised; numerical outputs remain frozen.")
                st.rerun()
    elif st.button("Submit review", type="primary"):
        action = "accept" if action_label == "Accept" else "reject"
        try:
            record = make_review_record(nct_id, action, note, explanation)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state.review_log.append(record)
            st.success(f"Review recorded: {action}.")

    if st.session_state.review_log:
        with st.expander("Session review log"):
            st.json(st.session_state.review_log)
            st.download_button(
                "Download review log",
                data=json.dumps(st.session_state.review_log, indent=2),
                file_name="hearttrialtwin_full_system_review.json",
                mime="application/json",
            )


def main() -> None:
    st.title("HeartTrialTwin")
    st.subheader("Experimental trial-discontinuation model and human review")
    st.error(DISCLAIMER)
    st.caption(
        "NCT ID → exact frozen input → frozen Logistic Regression → experimental score → "
        "model contributions → human review"
    )

    try:
        bundle = cached_runtime()
    except Exception as exc:
        st.error(f"Frozen runtime failed integrity checks: {exc}")
        st.stop()

    if "review_log" not in st.session_state:
        st.session_state.review_log = []
    if "revised_explanations" not in st.session_state:
        st.session_state.revised_explanations = {}

    metrics = bundle.manifest["temporal_test_metrics"]
    with st.sidebar:
        st.header("Frozen methodology")
        st.caption("Development: submission year ≤ 2020")
        st.caption("Locked temporal test: 2021–2024; evaluated once")
        st.metric("Temporal-test PR-AUC", f"{metrics['pr_auc']:.4f}")
        st.caption(f"Prevalence baseline: {metrics['prevalence_baseline']:.4f}")
        st.metric("Temporal-test ROC-AUC", f"{metrics['roc_auc']:.4f}")
        st.metric("Temporal-test Brier", f"{metrics['brier']:.4f}")
        st.caption("Enrollment was excluded following leakage analysis.")
        st.caption("No post-hoc calibration was retained.")

    nct_ids = sorted(bundle.inputs["nct_id"].astype(str))
    selected = st.selectbox("Select an NCT ID", nct_ids)
    try:
        result = score_trial(bundle, selected)
        input_row = get_trial_input(bundle, selected).iloc[0]
    except (KeyError, RuntimeError, ValueError) as exc:
        st.error(str(exc))
        st.stop()

    st.markdown(f"## {selected}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Experimental discontinuation score", f"{result['probability']:.2%}")
    c2.metric("Frozen research threshold", f"{result['threshold']:.4f}")
    position = "AT OR ABOVE" if result["threshold_position"] == "above_or_equal" else "BELOW"
    c3.metric("Threshold comparison", position)
    st.warning(
        "The threshold comparison is a research output. It is not a clinical, treatment, "
        "or trial-management recommendation."
    )

    st.markdown("### Exact frozen input evidence")
    structured_columns = [
        column for column in bundle.model.feature_names_in_ if column != "criteria"
    ]
    evidence = pd.DataFrame(
        {
            "field": structured_columns,
            "frozen value": [
                "MISSING" if pd.isna(input_row[column]) else str(input_row[column])
                for column in structured_columns
            ],
        }
    )
    st.dataframe(evidence, hide_index=True, width="stretch")
    with st.expander("Eligibility criteria text used by TF-IDF"):
        st.text(str(input_row["criteria"]))
    missing = result["input_missing_fields"]
    st.caption(
        "Missing model fields: " + (", ".join(missing) if missing else "none recorded")
    )

    st.markdown("### Selected-trial model contributions")
    st.caption(
        "Contributions are exact frozen Logistic Regression log-odds terms, not aggregate "
        "SHAP values and not causal effects."
    )
    structured = pd.DataFrame(result["top_structured_contributions"])
    if not structured.empty:
        structured["input_value"] = structured["input_value"].map(
            lambda value: "MISSING" if pd.isna(value) else str(value)
        )
        st.dataframe(structured, hide_index=True, width="stretch")
    st.metric(
        "Eligibility-text aggregate contribution",
        f"{result['criteria_text_contribution']:+.4f} log-odds",
    )
    left, right = st.columns(2)
    left.markdown("**Top text terms increasing the model score**")
    left.dataframe(pd.DataFrame(result["top_positive_text_terms"]), hide_index=True)
    right.markdown("**Top text terms decreasing the model score**")
    right.dataframe(pd.DataFrame(result["top_negative_text_terms"]), hide_index=True)
    st.code(
        f"intercept {result['intercept_log_odds']:+.6f} + contributions "
        f"{result['contribution_sum']:+.6f} = log-odds "
        f"{result['reconstructed_log_odds']:+.6f}"
    )
    st.caption(f"Additivity absolute error: {result['additivity_error']:.2e}")

    original = generate_explanation(result)
    explanation = st.session_state.revised_explanations.get(selected, original)
    st.markdown("### Grounded deterministic explanation")
    st.info(explanation["text"])
    st.caption(
        f"Generator: {explanation['generator']} · Revision mode: "
        f"{explanation['revision_mode']} · No runtime LLM"
    )

    st.markdown("### Provenance")
    p1, p2 = st.columns(2)
    p1.code(
        f"NCT ID: {result['nct_id']}\n"
        f"Model: {result['model_version']}\n"
        f"Model SHA-256: {result['model_sha256']}"
    )
    p2.code(
        f"Data: {result['data_version']}\n"
        f"Threshold: {result['threshold']:.4f}\n"
        f"Submission year (provenance only): {result['submission_year']}"
    )
    st.caption(bundle.manifest["data_limitation"])
    render_review(selected, result, explanation)


if __name__ == "__main__":
    main()
