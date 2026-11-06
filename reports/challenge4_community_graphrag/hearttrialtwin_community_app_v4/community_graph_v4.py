
"""Interactive source-evidence graph for HeartTrialTwin."""

from html import escape


def render_evidence_graph(st, anchor, candidate, bundle):
    try:
        import plotly.graph_objects as go
    except ImportError:
        st.warning("Plotly is not installed.")
        return

    st.subheader("Interactive Evidence Graph")
    st.caption(
        "Explore exact shared registered source nodes. "
        "Hover to inspect evidence, zoom or drag to navigate, "
        "and select a node below for its complete source record. "
        "Community membership does not establish clinical equivalence."
    )

    categories = [
        ("intervention", "Intervention", "#22c55e"),
        ("submitted", "Submitted condition", "#eab308"),
        ("browse", "Browse condition", "#a78bfa"),
    ]

    records = []

    for kind, title, color in categories:
        for item in bundle["registered_shared_nodes"].get(kind, []):
            records.append((kind, title, color, item))

    if not records:
        st.info(
            "No exact shared registered source nodes were found "
            "for this trial pair."
        )
        return

    total = len(records)
    display_records = records[:24]

    if total > 24:
        st.info(
            f"Displaying 24 of {total} shared nodes. "
            "The evidence tables contain the complete listing."
        )

    count = len(display_records)

    fig = go.Figure()

    for i, (kind, title, color, item) in enumerate(display_records):
        y = (count - 1) / 2 - i

        for start_x in [-2, 2]:
            fig.add_trace(
                go.Scatter(
                    x=[start_x, 0],
                    y=[0, y],
                    mode="lines",
                    line=dict(color="#64748b", width=1.5),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

        name = str(item.get("name") or item.get("shared_node_id"))
        short_name = name[:30]

        hover = (
            f"<b>{escape(title)}</b><br>"
            f"Name: {escape(name)}<br>"
            f"Node ID: {escape(str(item.get('shared_node_id', '')))}<br>"
            f"{escape(anchor)} source: "
            f"{escape(str(item.get('anchor_source_id', '')))}<br>"
            f"{escape(candidate)} source: "
            f"{escape(str(item.get('candidate_source_id', '')))}"
        )

        fig.add_trace(
            go.Scatter(
                x=[0],
                y=[y],
                mode="markers+text",
                text=[short_name],
                textposition="top center",
                textfont=dict(size=10),
                marker=dict(
                    size=18,
                    color=color,
                    line=dict(color="#334155", width=1),
                ),
                hovertext=[hover],
                hovertemplate="%{hovertext}<extra></extra>",
                name=title,
                showlegend=(i == next(
                    j for j, r in enumerate(display_records)
                    if r[0] == kind
                )),
            )
        )

    for x, trial, color, label in [
        (-2, anchor, "#38bdf8", "Anchor trial"),
        (2, candidate, "#fb7185", "Candidate trial"),
    ]:
        fig.add_trace(
            go.Scatter(
                x=[x],
                y=[0],
                mode="markers+text",
                text=[trial],
                textposition="top center",
                marker=dict(size=29, color=color, symbol="square"),
                hovertext=[f"{label}: {trial}"],
                hovertemplate="%{hovertext}<extra></extra>",
                name=label,
            )
        )

    fig.update_layout(
        height=max(500, min(950, 250 + 40 * count)),
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(visible=False, range=[-3, 3]),
        yaxis=dict(visible=False),
        dragmode="pan",
        hovermode="closest",
        legend=dict(orientation="h", y=1.12),
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"scrollZoom": True},
    )

    st.markdown("**Inspect a registered evidence node**")

    labels = [
        f"{title}: {item.get('name') or item.get('shared_node_id')}"
        for _, title, _, item in records
    ]

    choice = st.selectbox(
        "Select source node",
        range(len(records)),
        format_func=lambda i: labels[i],
        key="c4_graph_source_selector",
    )

    kind, title, color, item = records[choice]

    st.json({
        "anchor_trial": anchor,
        "candidate_trial": candidate,
        "source_category": title,
        "shared_registered_node": item,
        "interpretation_limit": (
            "A shared source node does not establish clinical "
            "equivalence, efficacy, or treatment benefit."
        ),
    })
