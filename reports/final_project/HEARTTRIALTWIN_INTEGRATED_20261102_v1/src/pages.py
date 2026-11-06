"""Modular UI pages. No training, arbitrary Cypher, or source writes."""
import copy,json,runpy
import streamlit as st
from identity import *
from client import request

@st.cache_data(show_spinner=False)
def characteristics():
    verify_base();return read_csv(BASE/'analysis/all_trial_characteristics.csv')

def show_answer(result):
    st.write(result.get('status','UNKNOWN'))
    st.text(result.get('answer','No answer published.'))
    if result.get('prepared_evidence'):
        with st.expander('Verified evidence, source IDs and citation bindings'):st.json(result['prepared_evidence'])
    if 'client_elapsed_seconds' in result:st.caption(f"Elapsed: {result['client_elapsed_seconds']:.2f} seconds")

def trial_intelligence():
    source=st.radio('Evidence source',['Offline pinned CSV evidence','Existing live Neo4j + MiniLM'],horizontal=True,key='intelligence_source')
    if source=='Existing live Neo4j + MiniLM':
        st.caption('Unchanged existing application embedded under shared navigation. Read-only Neo4j and cached MiniLM required. No queries execute until you submit.')
        runpy.run_path(str(ROOT/'full_cohort_graphrag/semantic_v1/demo_v2/app.py'),run_name='hearttrialtwin_legacy_page')
    else:
        st.title('Trial Intelligence')
        st.caption('OFFLINE: original pinned graph CSVs, unchanged evidence/citation validators. No Neo4j or LLM request.')
        nct=st.text_input('NCT identifier','NCT00206232',key='offline_nct')
        field=st.selectbox('Registered field',['planned outcomes','lead sponsor','intervention','title','phase','conditions'],key='offline_field')
        if st.button('Retrieve verified offline evidence',key='offline_get'):
            with st.spinner('Verifying sources and citations…',show_time=True):
                result=request({'action':'answer','question':f'What {field} were registered for {nct.strip()}?'})
            st.session_state['integrated_offline_answer']=result
        if 'integrated_offline_answer' in st.session_state:show_answer(st.session_state['integrated_offline_answer'])
    with st.expander('Compare registered planned outcomes — offline, trial-bound evidence'):
        ids=st.multiselect('Select up to three trials',[r['nct_id'] for r in characteristics()],default=['NCT00206232','NCT00391846'],max_selections=3,key='comparison_ids')
        st.caption('Lists remain bound to their own trials. Missingness causes abstention for that trial, not invented outcomes or clinical equivalence.')
        if st.button('Compare source-linked lists',key='compare'):
            with st.spinner('Preparing complete lists…',show_time=True):result=request({'action':'compare','nct_ids':ids})
            st.session_state['integrated_comparison']=result
        if 'integrated_comparison' in st.session_state:
            result=st.session_state['integrated_comparison'];st.write(result['status'])
            for trial in result.get('trial_results',[]):show_answer(trial)

def phase_explorer():
    st.title('Phase and Intervention Explorer')
    st.caption('All 2,824 selected trials retained; 1,319 phase-applicable and 1,505 NA. Offline snapshot facts, not original-registration assertions.')
    rows=characteristics();phase=st.selectbox('Recorded phase',['All','EARLY_PHASE1','PHASE1','PHASE1/PHASE2','PHASE2','PHASE2/PHASE3','PHASE3','PHASE4','NA'])
    typ=st.selectbox('Registered intervention type',['All','DRUG','DEVICE','BEHAVIORAL','PROCEDURE','OTHER','BIOLOGICAL','DIETARY_SUPPLEMENT','DIAGNOSTIC_TEST','COMBINATION_PRODUCT','GENETIC','RADIATION'])
    selected=[r for r in rows if (phase=='All' or r['phase']==phase) and (typ=='All' or typ in r['intervention_types'].split(';'))]
    st.metric('Matching trials',len(selected));st.caption('Nonexclusive intervention types. Exact filters; first 50 NCTs shown, not a semantic ranking.')
    st.dataframe([{k:r[k] for k in ['nct_id','brief_title','phase','intervention_types','lead_sponsor_classes']} for r in selected[:50]],hide_index=True)
    if st.button('Open source-linked filter evidence',key='filter_sources'):
        with st.spinner('Checking relationship-level citations…',show_time=True):result=request({'action':'search','phase':None if phase=='All' else phase,'intervention_type':None if typ=='All' else typ,'limit':20})
        st.json(result)
    a,b=st.columns(2)
    with a:st.image(str(BASE/'poster/figures/phase_distribution_full.png'))
    with b:st.image(str(BASE/'poster/figures/na_intervention_composition.png'))
    with st.expander('All 115 NA drug-including source records'):
        st.caption('74 drug-only, 41 mixed-type. NA rationale is not individually adjudicated; records are not automatically errors.')
        st.dataframe(read_csv(BASE/'analysis/na_drug_trial_audit.csv'),hide_index=True)
    with st.expander('All applicable-phase results'):st.dataframe(read_csv(BASE/'analysis/phase_status_applicable.csv'),hide_index=True)

def risk_dashboard():
    # V2 dashboard reads existing pinned evidence; all other pages remain unchanged.
    from risk_dashboard_refined import render
    return render(root=ROOT, base=BASE, package=PACKAGE,
                  verify_base=verify_base, read_csv=read_csv, load=load)

def scenario_lab():
    st.title('Digital Trial-Twin Scenario Lab')
    st.error('Research-only arithmetic sensitivity. Not an ongoing-trial forecast, clinical recommendation, patient twin, causal effect or optimal-design tool. Risk release remains BLOCKED.')
    st.caption('Only source-backed 2017–2018 development profiles; phase, sponsor, intervention and design remain fixed. One hypothetical control: planned enrollment.')
    if st.button('Load eligible historical profiles',key='load_profiles'):
        with st.spinner('Verifying frozen pipelines and cohort…',show_time=True):st.session_state['historical_profiles']=request({'action':'profiles'})
    data=st.session_state.get('historical_profiles')
    if not data:return
    if 'profiles' not in data:show_answer(data);return
    profiles={r['nct_id']:r for r in data['profiles']}
    st.caption(f"{data['count']} development profiles have positive historical Anticipated enrollment; one development profile without a valid target is not selectable.")
    nct=st.selectbox('Historical NCT profile',list(profiles),format_func=lambda n:n+' — '+profiles[n]['title'],key='scenario_nct')
    p=profiles[nct];st.write({'NCT':nct,'historical observation':p['observation_date'],'historical phase':p['historical_phase'],'recorded Anticipated enrollment':p['planned_enrollment']})
    bounds=p['scenario_bounds']
    if not bounds['modifiable']:st.info('The recorded arm count is unavailable/inconsistent. Only an unchanged baseline replay is supported for this profile.')
    target=st.number_input('Hypothetical planned enrollment (participants)',min_value=bounds['minimum'] if bounds['modifiable'] else p['planned_enrollment'],
        max_value=bounds['maximum'] if bounds['modifiable'] else p['planned_enrollment'],value=p['planned_enrollment'],step=1,
        disabled=not bounds['modifiable'],key='hypothetical_'+nct)
    st.caption('Backend additionally enforces the observed development range, 0.5–2× source target and recorded arm count. Marginal bounds do not prove joint scientific feasibility.')
    ack=st.checkbox('I understand these are unvalidated, in-sample classifier scores and noncausal hypothetical changes.',key='research_ack')
    if st.button('Compare saved-model outputs',disabled=not ack,key='scenario_run'):
        with st.spinner('Applying the same saved preprocessing and models to both rows…',show_time=True):
            result=request({'action':'scenario','nct_id':nct,'planned_enrollment':int(target) if bounds['modifiable'] else None,'acknowledge':ack})
        st.session_state['scenario_result']=result
    result=st.session_state.get('scenario_result')
    if not result:return
    if 'scores' not in result:show_answer(result);return
    st.subheader('Result for '+result['nct_id']+' at '+result['observation_date'])
    st.caption('Recorded baseline vs hypothetical enrollment: '+str(result['baseline_planned_enrollment'])+' vs '+str(result['hypothetical_planned_enrollment']))
    st.dataframe([{k:r[k] for k in ['model','baseline_score','hypothetical_score','score_difference']} for r in result['scores']],hide_index=True)
    import pandas as pd
    chart=pd.DataFrame(result['scores']).set_index('model')[['baseline_score','hypothetical_score']]
    # Streamlit swaps data and labels for horizontal bars; y_label names the numeric axis.
    st.bar_chart(chart,horizontal=True,stack=False,y_label='Unvalidated conditional classifier score (0–1)')
    st.info('Only log planned enrollment changes in the pipeline. Phase-only and intercept scores cannot respond to that change. Differences are model behavior, not a change in actual risk.')
    with st.expander('Historical source vs hypothetical feature values'):
        # Display mixed categorical/numeric source values as text; inference trace stays typed.
        st.dataframe([dict(r,baseline_historical_value=str(r['baseline_historical_value']),hypothetical_value=str(r['hypothetical_value'])) for r in result['features']],hide_index=True)
    with st.expander('Source-record citations and model checksums'):st.json({'sources':result['source_references'],'model_checksums':result['model_checksums'],'bounds':result['bounds']})
    for warning in result['warnings']:st.caption(warning)
    st.caption(result['uncertainty_note'])
    st.download_button('Download scenario audit trace',json.dumps(result,indent=2,ensure_ascii=False),file_name='hearttrialtwin_research_scenario.json',mime='application/json')
