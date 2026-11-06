
#!/usr/bin/env python3
"""HeartTrialTwin v6: verified local evidence and deterministic communities.

Run from Project root:
  .venv-full-system/bin/python -B reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/app.py --inspect
  .venv-full-system/bin/python -B -m streamlit run reports/challenge4_community_graphrag/hearttrialtwin_community_app_v6/app.py --server.address 127.0.0.1 --server.port 8510 --server.headless true --browser.gatherUsageStats false

Requires the unchanged adjacent hearttrialtwin_community_app_v4 folder and
trial_intelligence_v5.py (retained filename) in this v6 folder.
No LLM/database calls, training or research-file writes occur in this app.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from integrity import verify_runtime

V4_DIR = HERE.parent / "hearttrialtwin_community_app_v4"
V4_APP = V4_DIR / "app.py"

def load_core():
    """Call only after verifying preserved code and its input files."""
    if str(V4_DIR) not in sys.path:
        sys.path.insert(0, str(V4_DIR))
    return runpy.run_path(str(V4_APP), run_name="hearttrialtwin_v4_core")


def inspect():
    """Check all required assets, not merely file existence or current hashes."""
    print(json.dumps(verify_runtime(), indent=2))
    return 0


def run_app():
    import streamlit as st
    from trial_intelligence_v5 import guided_trial_intelligence
    from community_page import community_page

    st.set_page_config(
        page_title="HeartTrialTwin | Research demonstration v6",
        layout="wide",
    )

    try:
        verification = verify_runtime()
        core = load_core()
        original_src = core["ORIGINAL"] / "src"
        if str(original_src) not in sys.path:
            sys.path.insert(0, str(original_src))
        from identity import verify_base
        import pages

        verify_base()

        @st.cache_resource(
            show_spinner="Loading pinned community evidence…"
        )
        def cached_graph():
            return core["get_graph_data"]()

        graph = cached_graph()

    except (OSError, ValueError, KeyError, ImportError) as exc:
        st.error(
            f"Pinned inputs failed verification "
            f"({type(exc).__name__}). "
            "No research answers published."
        )
        st.stop()

    choices = [
        "Trial Intelligence",
        "Community Explorer",
        "Phase and Intervention Explorer",
        "Operational Risk Dashboard",
        "Digital Trial-Twin Scenario Lab",
    ]

    with st.sidebar:
        st.title("HeartTrialTwin")

        choice = st.radio(
            "Research page",
            choices,
            key="v6_page"
        )

        st.caption(
            "Version 6 · deterministic research demonstration "
            "· AACT 2026-09-05 "
            "· Research use only"
        )
        st.caption(f"Integrity: {verification['assets_verified']} assets verified. No Neo4j or Ollama required.")

    st.warning("Experimental — not validated for clinical decision-making. Registered planned outcomes are not "
               "observed clinical results. Predictive release remains BLOCKED.")
    with st.expander("Supplementary MiniLM + live GraphRAG demo (separately provisioned)"):
        st.caption("Community navigation is not semantic ranking. The separate demo requires cached MiniLM assets, "
                   "a provisioned Neo4j database and a fresh dedicated read-only credential. It is not started here.")
        st.code(".venv-full-system/bin/python -B -m streamlit run "
                "full_cohort_graphrag/semantic_v1/demo_v2/app.py --server.address 127.0.0.1 --server.port 8502")

    if choice == "Trial Intelligence":

        guided_trial_intelligence(
            st,
            graph,
            pages.characteristics
        )

    elif choice == "Community Explorer":

        community_page(st, graph, core)

    else:

        st.warning(
            "Experimental research application, not validated "
            "for clinical decisions. Registered planned outcomes "
            "are not observed results."
        )

        {
            "Phase and Intervention Explorer":
                pages.phase_explorer,

            "Operational Risk Dashboard":
                pages.risk_dashboard,

            "Digital Trial-Twin Scenario Lab":
                pages.scenario_lab,

        }[choice]()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--inspect",
        action="store_true"
    )

    args, _ = parser.parse_known_args()

    if args.inspect:
        try:
            sys.exit(inspect())

        except (
            OSError,
            ValueError,
            KeyError,
            TypeError
        ) as exc:

            print(
                f"STOPPED safely: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr
            )

            sys.exit(1)

    run_app()
