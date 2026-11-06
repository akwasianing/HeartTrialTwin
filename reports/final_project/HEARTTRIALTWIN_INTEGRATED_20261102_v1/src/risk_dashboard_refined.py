"""Read-only Operational Risk Dashboard extension for HeartTrialTwin.

Loads original checksum-verified artifacts through the existing pages module.
Research-only descriptive displays; not a prospective risk model.
"""
import hashlib
import json
from pathlib import Path

import pandas as pd
import streamlit as st

EXPECTED_EVAL_SHA256 = '12e82d5fd01ca840f97ec6ed91ce5654fc1e160ab67b158856a22305210dd795'
EVAL_REL = Path('full_system_feasibility/independent_evaluation_2021_2024_v1/post_unseal_evaluation_results_status_only_v2.json')
REQUIRED_CELLS = {'phase','intervention_type','n','COMPLETED','TERMINATED','WITHDRAWN','discontinued_fraction','wilson_lower','wilson_upper','display_status'}


def _num(series):
    return pd.to_numeric(series, errors='coerce')


def render(*, root, base, package, verify_base, read_csv, load):
    """Called only by original pages.risk_dashboard()."""
    st.title('Operational Risk Dashboard')
    st.warning('Recorded terminal-outcome associations only. These are not validated predictions of future discontinuation or clinical recommendations. Intervention types can overlap; phase/type cells are not independent.')
    verify_base()  # fail closed on original pinned evidence before any dashboard display
    file_cells = package / 'data/phase_intervention_cells.csv'
    file_factors = package / 'data/factor_comparisons.csv'
    file_manifest = package / 'results/dashboard_manifest.json'
    for p in (file_cells, file_factors, file_manifest):
        if not p.is_file():
            st.error('Required pinned dashboard evidence is missing; no statistics displayed: '+p.name)
            st.stop()
    cells = pd.DataFrame(read_csv(file_cells))
    if not REQUIRED_CELLS.issubset(set(cells.columns)):
        st.error('Pinned phase/type cell schema is incomplete. Dashboard display blocked.')
        st.stop()
    if cells.duplicated(['phase','intervention_type']).any():
        st.error('Duplicate phase/intervention cells detected. Dashboard display blocked.')
        st.stop()
    if len(cells) != 88:
        st.error(f'Expected exactly 88 original phase/intervention cells, found {len(cells)}. Dashboard display blocked.')
        st.stop()
    for field in ('n','COMPLETED','TERMINATED','WITHDRAWN','discontinued_fraction','wilson_lower','wilson_upper'):
        cells[field] = _num(cells[field])
    # Source-provided rates/intervals are displayed, not recomputed under a different denominator definition.
    if (cells['n'].isna() | (cells['n'] < 0)).any():
        st.error('Invalid cell denominators; dashboard display blocked.')
        st.stop()
    st.caption('88 prespecified phase × intervention cells. Fractions and Wilson intervals are read from the original research artifact, without changing the endpoint or denominator.')

    st.subheader('Phase × intervention: interactive historical evidence')
    phases = list(dict.fromkeys(cells['phase'].fillna('UNKNOWN').astype(str)))
    types = list(dict.fromkeys(cells['intervention_type'].fillna('UNKNOWN').astype(str)))
    controls = st.columns(2)
    with controls[0]:
        phase = st.selectbox('Recorded phase', ['All'] + phases, key='htt_risk_phase_v2')
    with controls[1]:
        intervention = st.selectbox('Intervention type', ['All'] + types, key='htt_risk_type_v2')
    selected = cells.loc[((cells['phase'].astype(str)==phase) | (phase=='All')) & ((cells['intervention_type'].astype(str)==intervention) | (intervention=='All'))].copy()
    st.metric('Selected phase/intervention cells', len(selected))
    # Streamlit's Altair selection event connects a click to the detail panel.
    # This is a UI selection, not a change in the published research artifact.
    import altair as alt
    chart_data = selected.copy()
    chart_data['fraction_pct'] = chart_data['discontinued_fraction'] * 100
    chart_data['lower_pct'] = chart_data['wilson_lower'] * 100
    chart_data['upper_pct'] = chart_data['wilson_upper'] * 100
    chart_data['phase'] = chart_data['phase'].astype(str)
    chart_data['intervention_type'] = chart_data['intervention_type'].astype(str)
    # A cell with zero members or unpublished estimate must not appear to have 0% risk.
    chart_data.loc[chart_data['n'].eq(0) | chart_data['discontinued_fraction'].isna(), 'fraction_pct'] = float('nan')
    tooltip = [
        alt.Tooltip('phase:N', title='Recorded phase'),
        alt.Tooltip('intervention_type:N', title='Intervention type'),
        alt.Tooltip('n:Q', title='Trial count'),
        alt.Tooltip('COMPLETED:Q', title='Completed'),
        alt.Tooltip('TERMINATED:Q', title='Terminated'),
        alt.Tooltip('WITHDRAWN:Q', title='Withdrawn'),
        alt.Tooltip('fraction_pct:Q', format='.1f', title='Discontinued (%)'),
        alt.Tooltip('lower_pct:Q', format='.1f', title='Wilson lower (%)'),
        alt.Tooltip('upper_pct:Q', format='.1f', title='Wilson upper (%)'),
        alt.Tooltip('display_status:N', title='Evidence status'),
    ]
    cell_pick = alt.selection_point(
        name='cell_pick', fields=['phase', 'intervention_type'],
        on='click', clear='dblclick',
    )
    heat = (alt.Chart(chart_data)
        .mark_rect()
        .encode(
            x=alt.X('intervention_type:N', title='Intervention type', sort=types,
                    axis=alt.Axis(labelAngle=-38, labelLimit=160, labelFontSize=11)),
            y=alt.Y('phase:N', title='Recorded phase', sort=phases,
                    axis=alt.Axis(labelLimit=185, labelFontSize=11)),
            color=alt.Color('fraction_pct:Q', title='Historical discontinuation (%)',
                            scale=alt.Scale(scheme='blues', domain=[0, 100]),
                            legend=alt.Legend(orient='right')),
            stroke=alt.condition(cell_pick, alt.value('#fb923c'), alt.value('#e2e8f0')),
            strokeWidth=alt.condition(cell_pick, alt.value(3), alt.value(0.8)),
            tooltip=tooltip,
        )
        .add_params(cell_pick)
        .properties(height=max(190, 44 * len(set(chart_data['phase']))))
    )
    # Recent Streamlit supports on_select='rerun' and returns a selection dictionary.
    # Never pretend clicking works if an older Streamlit lacks this API.
    try:
        event = st.altair_chart(
            heat, on_select='rerun', selection_mode=['cell_pick'],
            key='htt_risk_heatmap_click_v1', use_container_width=True,
        )
    except TypeError:
        st.error('This Streamlit version does not support chart-to-detail selection. Upgrade the existing application environment before enabling cell clicks.')
        st.stop()
    st.caption('Click a heatmap square to inspect its evidence below; double-click to clear selection. Hover for the source counts and Wilson interval. No-record and suppressed estimates are not zero risk.')

    st.subheader('Selected cell: evidence and denominators')
    detail_cols = ['phase','intervention_type','n','COMPLETED','TERMINATED',
                   'WITHDRAWN','discontinued_fraction','wilson_lower',
                   'wilson_upper','display_status']
    if selected.empty:
        st.info('No phase/intervention cells match these filters.')
    else:
        picked = None
        try:
            value = (event or {}).get('selection', {}).get('cell_pick', [])
            if isinstance(value, list) and value:
                item = value[0]
                if isinstance(item, dict):
                    picked = (str(item.get('phase', '')), str(item.get('intervention_type', '')))
        except (AttributeError, TypeError, IndexError):
            picked = None
        matching = selected.index[(selected['phase'].astype(str) == picked[0]) &
                                  (selected['intervention_type'].astype(str) == picked[1])] if picked else []
        if len(matching):
            cell = selected.loc[matching[0]]
            st.success(f"Heatmap selection: {cell['phase']} × {cell['intervention_type']}")
            st.caption('To choose a different cell, click another heatmap square. Double-click to clear chart selection and use the dropdown below.')
        else:
            options = list(range(len(selected)))
            chosen = st.selectbox(
                'Inspect one cell (alternative to clicking the heatmap)', options,
                format_func=lambda i: f"{selected.iloc[i]['phase']} | {selected.iloc[i]['intervention_type']}",
                key='htt_risk_cell_fallback_click_v1',
            )
            cell = selected.iloc[chosen]
        a, b, c, d = st.columns(4)
        a.metric('Trials in cell', int(cell['n']))
        b.metric('Completed', int(cell['COMPLETED']) if pd.notna(cell['COMPLETED']) else 'Not reported')
        c.metric('Terminated', int(cell['TERMINATED']) if pd.notna(cell['TERMINATED']) else 'Not reported')
        d.metric('Withdrawn', int(cell['WITHDRAWN']) if pd.notna(cell['WITHDRAWN']) else 'Not reported')
        status = str(cell['display_status'])
        if pd.notna(cell['discontinued_fraction']) and pd.notna(cell['wilson_lower']) and pd.notna(cell['wilson_upper']):
            st.write(f"Published historical discontinuation fraction: **{cell['discontinued_fraction']:.1%}** (Wilson 95% CI **{cell['wilson_lower']:.1%}–{cell['wilson_upper']:.1%}**). Evidence status: **{status}**.")
        else:
            st.info('No published numeric estimate for this cell. Evidence status: ' + status)
        st.caption('Original denominators, definitions, and uncertainty retained. These are unadjusted descriptive associations, not prospective or individual risk estimates.')
        st.download_button(
            'Download this cell’s evidence (CSV)',
            pd.DataFrame([cell[detail_cols]]).to_csv(index=False),
            file_name='hearttrialtwin_selected_historical_cell.csv', mime='text/csv',
            key='htt_risk_selected_cell_download_click_v1',
        )
    with st.expander(f'Browse all {len(selected)} matching cells'):
        st.dataframe(selected[detail_cols], hide_index=True, use_container_width=True)
        st.download_button('Download all matching historical cells (CSV)',
            selected[detail_cols].to_csv(index=False),
            file_name='hearttrialtwin_phase_intervention_filtered.csv',mime='text/csv',
            key='htt_risk_all_cells_download_click_v1')

    st.subheader('13 original unadjusted factor comparisons')
    factors=pd.DataFrame(read_csv(file_factors))
    st.caption('Original research comparisons, including their original comparators, excluded groups and uncertainty. Do not interpret differences as causal effects.')
    if factors.empty:
        st.error('Factor-comparison artifact is empty; no comparisons displayed.')
        st.stop()
    st.dataframe(factors,hide_index=True,use_container_width=True)
    with st.expander('Original comparison figure'):
        fig=package/'figures/factor_comparison_heatmap.png'
        if fig.is_file():st.image(str(fig))
    st.download_button('Download original factor-comparison evidence (CSV)',factors.to_csv(index=False),file_name='hearttrialtwin_factor_comparisons.csv',mime='text/csv',key='htt_risk_factor_download_v2')

    st.subheader('Exploratory model evidence — not cleared for forecasting')
    st.error('The original classifier failed to establish useful independent discrimination. It is BLOCKED_EXPLORATORY_ONLY. Do not use its scores as calibrated prospective termination probabilities.')
    eval_path=root/EVAL_REL
    if eval_path.is_file():
        digest=hashlib.sha256(eval_path.read_bytes()).hexdigest()
        if digest==EXPECTED_EVAL_SHA256:
            result=json.loads(eval_path.read_text())
            if result.get('snapshot_id')==4481 and result.get('risk_release')=='BLOCKED_EXPLORATORY_ONLY':
                a,b,c,d=st.columns(4)
                a.metric('2021–24 ROC-AUC',f"{result['roc_auc']:.3f}")
                b.metric('Average precision',f"{result['average_precision']:.3f}")
                c.metric('Brier score',f"{result['brier']:.3f}")
                d.metric('Binary evaluable',result['flow']['BINARY_EVALUABLE'])
                st.caption(f"AACT archive 4481; {result['flow']['TERMINATED']} terminated, {result['flow']['COMPLETED']} completed, {result['flow'].get('STATUS_WITHDRAWN',0)} withdrawn excluded from the binary endpoint. ROC-AUC 95% family-cluster bootstrap interval: {result['bootstrap']['auc_ci95'][0]:.3f}–{result['bootstrap']['auc_ci95'][1]:.3f}. Family/chronology review pending. Status-only comparison; exact terminal event date unknown.")
                with st.expander('Checksum-verified independent evaluation evidence'):
                    st.json({'report_sha256':digest,'status':result['status'],'primary_metric_status':result['primary_metric_status'],'risk_release':result['risk_release'],'flow':result['flow'],'prevalence_reference_brier':result['prevalence_only_reference_brier'],'bootstrap':result['bootstrap']})
            else:
                st.error('Independent evaluation semantics do not match expected pinned source; no updated metrics displayed.')
        else:
            st.error('Independent evaluation report fingerprint mismatch; no updated metrics displayed.')
    else:
        st.info('Independent 2021–2024 evaluation artifact not found in this checkout. Original exploratory evidence remains below.')
    comp=base/'modeling/comparison.csv'
    if comp.is_file():
        st.caption('Previously inspected exploratory evaluation (original artifact):')
        st.dataframe(read_csv(comp),hide_index=True,use_container_width=True)
    scores=package/'figures/development_score_distribution.png'
    if scores.is_file():
        with st.expander('Original in-sample score distributions'):
            st.image(str(scores))
            st.caption('Development-profile scores are in-sample classifier outputs, not validated operational risk estimates.')
    old_fig=package/'figures/model_performance_comparison.png'
    if old_fig.is_file():
        with st.expander('Original model-comparison figure'):
            st.image(str(old_fig))

    st.subheader('Which operational dimensions are modeled?')
    manifest=load(file_manifest)
    domains=manifest.get('risk_dimensions')
    if not isinstance(domains,dict):
        st.error('Risk-dimension manifest is malformed; status table withheld.')
        st.stop()
    st.dataframe([{'dimension':k,'evidence_or_model_status':v} for k,v in domains.items()],hide_index=True,use_container_width=True)
    st.caption('Recruitment-related stopping reasons have missing and ambiguous classifications; these are not verified negatives. No validated safety, efficacy, recruitment, delay, or phase-transition forecasting output is available.')
