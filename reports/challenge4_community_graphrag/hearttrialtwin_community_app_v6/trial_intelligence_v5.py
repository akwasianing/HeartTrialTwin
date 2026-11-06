"""Guided, read-only Trial Intelligence view for HeartTrialTwin v6.

Uses the already loaded pinned graph; does not predict trial outcomes.
"""

import re


KINDS = [
    ("intervention", "Registered interventions"),
    ("submitted", "Submitted conditions"),
    ("browse", "Browse conditions"),
    ("outcome", "Registered planned outcomes"),
]


def _present(record, keys):
    return {k: record[k] for k in keys if record.get(k) not in (None, "")}


def guided_trial_intelligence(st, graph, characteristics_fn):
    st.title("Trial Intelligence | Guided evidence lookup")
    st.caption(
        "Frozen AACT snapshot: 2026-09-05. Enter an NCT identifier to see "
        "available registered evidence automatically—no field selection required."
    )
    st.warning(
        "Registered planned outcomes are not observed trial results. "
        "This page does not produce discontinuation predictions."
    )

    nct = st.text_input(
        "NCT identifier", value="NCT00206232", key="v6_guided_nct"
    ).strip().upper()
    if not re.fullmatch(r"NCT\d{8}", nct):
        st.info("Enter an NCT ID in the format NCT00206232.")
        return
    if nct not in graph["trials"]:
        st.warning(
            "This ID is not in the frozen 2,824-trial heart-failure cohort. "
            "That does not mean the trial does not exist in ClinicalTrials.gov."
        )
        return

    row = graph["trials"][nct]
    facts = graph["facts"][nct]
    profiles = {r.get("nct_id"): r for r in characteristics_fn()}
    profile = profiles.get(nct, {})

    st.subheader(row.get("brief_title") or nct)
    details = {"NCT ID": nct}
    for label, keys in (
        ("Recorded phase", ["phase"]),
        ("Intervention type(s)", ["intervention_types"]),
        ("Lead sponsor class(es)", ["lead_sponsor_classes"]),
        ("Recorded status", ["overall_status", "status"]),
    ):
        for key in keys:
            value = profile.get(key) or row.get(key)
            if value:
                details[label] = value
                break
    st.json(details)
    if "Recorded status" not in details:
        st.caption("A verified trial-status field is not available in this view.")

    st.subheader("Available registered evidence")
    columns = st.columns(4)
    for col, (kind, label) in zip(columns, KINDS):
        col.metric(label, len(facts[kind]))
    st.caption(
        "Counts are loaded graph records for this trial, not evidence of "
        "treatment efficacy or a complete ClinicalTrials.gov record."
    )

    overview, evidence, compare, validated = st.tabs([
        "Overview", "Source records", "Compare two trials", "Original citation-validated lookup"
    ])
    with overview:
        for kind, label in KINDS:
            items = facts[kind]
            st.markdown(f"**{label}**")
            if items:
                st.dataframe(
                    [{"name": x.get("name", ""), "source_id": x.get("source_id", "")}
                     for x in items[:12]],
                    hide_index=True, use_container_width=True,
                )
                if len(items) > 12:
                    st.caption(f"Showing 12 of {len(items)} records here; all are in Source records.")
            else:
                st.caption("No records loaded for this category. Do not infer a clinical negative.")
    with evidence:
        kind = st.selectbox(
            "Evidence category", [k for k, _ in KINDS],
            format_func=lambda k: dict(KINDS)[k], key="v6_evidence_kind"
        )
        st.dataframe(facts[kind], hide_index=True, use_container_width=True)
        st.caption(
            "Intervention, submitted-condition, browse-condition and outcome "
            "records remain separate; source IDs are shown as stored."
        )
    with compare:
        second = st.text_input(
            "Second NCT identifier", value="NCT01625819", key="v6_second_nct"
        ).strip().upper()
        if second not in graph["trials"]:
            st.info("Enter a second NCT ID from this frozen cohort.")
        elif second == nct:
            st.info("Choose a different trial for comparison.")
        else:
            st.write("**Comparison:**", nct, "and", second)
            st.caption("Direct shared source-node intersections; not clinical equivalence.")
            for kind, label in KINDS[:3]:
                a = {x["node_id"]: x for x in facts[kind]}
                b = {x["node_id"]: x for x in graph["facts"][second][kind]}
                shared = [
                    {"name": a[k].get("name", ""), "shared_node_id": k,
                     "anchor_source_id": a[k].get("source_id", ""),
                     "candidate_source_id": b[k].get("source_id", "")}
                    for k in sorted(a.keys() & b.keys())
                ]
                with st.expander(f"{label}: {len(shared)} exact shared nodes"):
                    if shared:
                        st.dataframe(shared, hide_index=True, use_container_width=True)
                    else:
                        st.caption("No direct shared node in this category.")
            st.info(
                "Planned-outcome lists must be compared as trial-bound records; "
                "similar names are not evidence of matching clinical results."
            )
            for trial_id in (nct, second):
                with st.expander(f"Planned outcomes for {trial_id}"):
                    st.dataframe(
                        graph["facts"][trial_id]["outcome"],
                        hide_index=True, use_container_width=True
                    )
    with validated:
        st.caption(
            "Use the preserved original offline answer service, with its "
            "existing citation/evidence checks. No request is made until you click."
        )
        field = st.selectbox(
            "Question to verify", [
                "planned outcomes", "lead sponsor", "intervention",
                "title", "phase", "conditions"
            ], key="v6_verified_field"
        )
        custom = st.text_input("Optional single-trial question (unsupported requests abstain)",
                               max_chars=2000, key="v6_custom_question")
        question = custom.strip() or f"What {field} were registered for {nct}?"
        st.caption("Request: " + question)
        if st.button("Retrieve citation-validated answer", key="v6_verified_get"):
            from client import request
            requested_ids = set(re.findall(r"\bNCT\d{8}\b", question.upper()))
            if requested_ids != {nct}:
                result = {"status": "ABSTAIN", "model_attempts": 0,
                          "answer": "ABSTAIN: Request exactly the selected trial ID; no cross-trial substitution is allowed."}
            else:
                with st.spinner("Checking source integrity and trial-bound citations…", show_time=True):
                    result = request({"action": "answer", "question": question})
            st.session_state["v6_verified_answer"] = {"nct": nct, "question": question, "result": result}
        saved = st.session_state.get("v6_verified_answer", {})

        if saved.get("nct") == nct and saved.get("question") == question:
            result = saved["result"]
            status = result.get("status", "UNKNOWN")
            answer = result.get("answer", "No answer published.")

            st.write("**Citation-validation status:**", status)
            st.text(answer)
            st.caption(f"Model requests: {result.get('model_attempts', 0)} · "
                       f"Elapsed: {result.get('client_elapsed_seconds', 0):.2f} s · verified local CSVs, not live Neo4j")

            errors = (
                result.get("answer_trace", {})
                .get("validation", {})
                .get("errors", [])
            )

            if errors:
                st.caption(
                    "Validation codes: " + ", ".join(str(e) for e in errors)
                )

            if status == "ABSTAIN":
                if (
                    "MISSING_SOURCE_RECORDS" in errors
                    or "MISSING_SOURCE_RECORDS" in answer
                ):
                    st.warning(
                        "Evidence completeness limitation: The original "
                        "citation validator could not establish a complete "
                        "source set for this trial. Individual registered "
                        "records may still be available under Source records. "
                        "This abstention does not mean the trial had no "
                        "interventions or other registered information."
                    )
                else:
                    st.info(
                        "The original evidence service did not approve an "
                        "answer. Check the validation code and available "
                        "source records. No answer has been fabricated."
                    )

            if result.get("prepared_evidence"):
                with st.expander("Prepared evidence and citation bindings"):
                    st.json(result["prepared_evidence"])

