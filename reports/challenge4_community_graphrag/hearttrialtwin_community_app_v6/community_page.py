"""Deterministic v6 view over the unchanged v4 source-association utilities."""
import json
from collections import Counter


def community_page(st, graph, core):
    st.title("Community Explorer | HeartTrialTwin")
    st.caption("Exploratory B3 Louvain partition, seed 42 · AACT 2026-09-05")
    st.warning("Community membership is derived similarity, not a registered relationship, "
               "clinical equivalence or causal effect. Registered planned outcomes are not observed clinical results.")
    st.info("Unvalidated Ollama interpretation is disabled in v6. All explanations below are source-derived; "
            "no LLM or database request is made.")
    search = st.text_input("Find a trial by NCT ID or title", key="v6_community_search").strip()
    options = [n for n in sorted(graph["trials"]) if search.casefold() in
               (n + " " + graph["trials"][n].get("brief_title", "")).casefold()]
    if not options:
        st.info("No matching trial in this frozen cohort. This is not evidence that a trial does not exist.")
        return
    nct = st.selectbox("Anchor trial", options,
                       index=options.index("NCT00206232") if "NCT00206232" in options else 0,
                       key="v6_community_anchor")
    profile = core["offline_summary"](graph, nct)
    cols = st.columns(3)
    for col, label, value in zip(cols, ["B3 community size", "Other members", "All B3 communities"],
                                 [profile["size"], profile["size"] - 1, len(graph["communities"])]):
        col.metric(label, value)
    st.text(graph["trials"][nct].get("brief_title", ""))
    st.caption(f"Exploratory community ID: {profile['community_id']}; IDs do not denote clinical subtypes.")
    # Count distinct trials, not source-record occurrences with the same name.
    for kind, label in [("intervention", "Registered interventions"), ("submitted", "Submitted conditions")]:
        counts = Counter(name for member in profile["nct_members"]
                         for name in {r["name"] for r in graph["facts"][member][kind] if r["name"]})
        with st.expander(label + " in this community"):
            st.dataframe([{"name": name, "distinct_trial_count": count}
                          for name, count in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:20]],
                         hide_index=True, width="stretch")
    if profile["size"] == 1:
        st.info("Singleton under this projection: no community neighbors. Do not infer absence of registered evidence.")
        with st.expander("Anchor source records"):
            st.json(graph["facts"][nct])
        return
    limit = st.slider("Candidates to show", 5, 50, 15, 5, key="v6_neighbor_limit")
    neighbors = core["neighbor_rows"](graph, nct, limit)
    st.caption("Ordered by exact shared intervention, submitted-condition and browse nodes, then NCT ID. "
               "Not MiniLM ranking or an evaluated relevance model.")
    st.dataframe(neighbors, hide_index=True, width="stretch")
    selected = st.selectbox("Inspect a candidate trial", [r["nct_id"] for r in neighbors], key="v6_candidate")
    bundle = core["evidence_bundle"](graph, nct, selected)
    core["render_evidence_graph"](st, nct, selected, bundle)
    for kind, label in [("intervention", "Shared registered interventions"),
                        ("submitted", "Shared submitted conditions"), ("browse", "Shared browse terms")]:
        records = bundle["registered_shared_nodes"][kind]
        with st.expander(f"{label} ({len(records)})", expanded=kind == "intervention"):
            if records:
                st.dataframe(records, hide_index=True, width="stretch")
            else:
                st.info("No exact shared source node in this category; no clinical conclusion follows.")
    with st.expander("Trial-bound registered planned outcomes and source IDs"):
        for trial in (nct, selected):
            st.write(trial, "—", len(graph["facts"][trial]["outcome"]), "registered measures")
            st.dataframe(graph["facts"][trial]["outcome"], hide_index=True, width="stretch")
    st.caption("Full loaded outcome lists are shown separately by trial. Missing records are not evidence of absence. "
               "Use Trial Intelligence for citation-validated complete-listing status.")
    # Export complete source lists, unlike the earlier capped comparison display.
    bundle["anchor_planned_outcomes"] = graph["facts"][nct]["outcome"]
    bundle["candidate_planned_outcomes"] = graph["facts"][selected]["outcome"]
    bundle["outcome_display_limit"] = None
    bundle["dataset_version"] = "HTT-P1-AACT-20260905"
    bundle["graph_version"] = "HTT-KG-AACT-20260905-FULL2824-v1"
    bundle["snapshot_date"] = "2026-09-05"
    st.download_button("Download source relationship trace", json.dumps(bundle, ensure_ascii=False, indent=2),
                       file_name=f"community_evidence_{nct}_{selected}.json", mime="application/json")
    st.subheader("Source-derived explanation")
    st.text(f"{nct} and {selected} share exploratory community membership. The source graph records "
            + ", ".join(f"{len(v)} shared {k} node(s)" for k, v in bundle["registered_shared_nodes"].items())
            + ". These intersections do not demonstrate equivalent populations, treatment benefit or comparable clinical results.")
    st.subheader("Human review — session only")
    verdict = st.radio("Is this relationship useful for your research question?",
                       ["Uncertain", "Useful", "Partially useful", "Not useful"], key="v6_verdict")
    note = st.text_area("Researcher feedback (not verified evidence)", max_chars=1200, key="v6_feedback")
    if st.button("Record feedback in this session", key="v6_record_feedback"):
        st.session_state.setdefault("v6_feedback_records", []).append({
            "anchor_nct_id": nct, "candidate_nct_id": selected, "community_id": profile["community_id"],
            "verdict": verdict, "note": note, "label_source": "USER_ENTERED_UNVERIFIED"})
        st.success("Recorded only in this session; source data, models and community assignments are unchanged.")
    if st.session_state.get("v6_feedback_records"):
        st.download_button("Download session feedback", json.dumps(st.session_state["v6_feedback_records"], indent=2),
                           file_name="community_feedback.json", mime="application/json")
