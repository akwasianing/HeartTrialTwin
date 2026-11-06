"""Separate offline capstone companion. Existing live MiniLM/Neo4j app unchanged."""
import csv, json, subprocess, sys
from pathlib import Path
import streamlit as st

FINAL=Path(__file__).resolve().parents[1];ROOT=FINAL.parents[2]
WORKER=FINAL/'integration/phase_explorer.py'
PYTHON=ROOT/'.venv-vector-rag/bin/python'

def read(name):
    with (FINAL/name).open(newline='') as f:return list(csv.DictReader(f))

def run(args):
    try:
        process=subprocess.run([str(PYTHON),'-B',str(WORKER),*args],cwd=ROOT,capture_output=True,text=True,timeout=60)
        if process.returncode:return {'status':'ABSTAIN','answer':'Evidence verification failed. No unsupported answer is displayed.'}
        return json.loads(process.stdout)
    except (subprocess.TimeoutExpired,OSError,json.JSONDecodeError):
        return {'status':'ABSTAIN','answer':'Local evidence service unavailable or timed out after 60 seconds. No automatic retry.'}

st.set_page_config(page_title='HeartTrialTwin | Phase-aware evidence',layout='wide')
st.title('HeartTrialTwin')
st.subheader('Phase-aware registered evidence and operational research')
st.warning('Experimental — not validated for clinical decision-making. No clinical-effectiveness or ongoing-trial risk prediction.')
st.caption('Offline pinned-CSV companion • 2,824 selected terminal-outcome trials • AACT snapshot 2026-09-05 • No Neo4j writes or Ollama calls')
mode=st.radio('Explore',['Registered trial evidence','Phase and intervention discovery','Verified descriptive results','Exploratory historical modeling'])
if mode=='Registered trial evidence':
    nct=st.text_input('Exact NCT identifier','NCT00206232')
    field=st.selectbox('Registered information',['planned outcomes','lead sponsor','intervention','title','phase','conditions'])
    question=f'What {field} were registered for {nct.strip()}?'
    st.caption('Complete source-bound lists or explicit abstention. Planned outcomes are registered measures, not observed results.')
    if st.button('Retrieve source-verified answer'):
        with st.spinner('Checking pinned source files and citations…',show_time=True):st.session_state['answer']=run(['answer',question])
    if 'answer' in st.session_state:
        result=st.session_state['answer'];st.write(result['status']);st.text(result['answer'])
        if result.get('prepared_evidence'):
            with st.expander('Original registered evidence and citations'):st.json(result['prepared_evidence'])
            st.caption(f"Source evidence records: {result['evidence_count']} • model attempts: 0 • {result['elapsed_seconds']:.3f} s after source initialization")
elif mode=='Phase and intervention discovery':
    phase=st.selectbox('Phase',['All','EARLY_PHASE1','PHASE1','PHASE1/PHASE2','PHASE2','PHASE2/PHASE3','PHASE3','PHASE4','NA'])
    typ=st.selectbox('Registered intervention type',['All','DRUG','DEVICE','BEHAVIORAL','PROCEDURE','BIOLOGICAL','DIETARY_SUPPLEMENT','DIAGNOSTIC_TEST','OTHER','COMBINATION_PRODUCT','GENETIC','RADIATION'])
    if st.button('Find registered trials'):
        args=['search','--limit','20']
        if phase!='All':args+=['--phase',phase]
        if typ!='All':args+=['--intervention-type',typ]
        with st.spinner('Validating records…',show_time=True):result=run(args)
        if 'records' in result:
            st.write(f"{result['total']} matches; first {result['returned']} shown, sorted by NCT ID.")
            st.dataframe(result['records'],hide_index=True)
        else:st.text(result['answer'])
elif mode=='Verified descriptive results':
    st.image(str(FINAL/'poster/figures/phase_distribution_full.png'))
    st.image(str(FINAL/'poster/figures/na_intervention_composition.png'))
    st.dataframe(read('analysis/phase_status_full.csv'),hide_index=True)
    st.info('Current snapshot associations, not individual future-risk estimates. Intervention categories overlap. NA is retained, not treated as a data error.')
else:
    p=FINAL/'modeling/comparison.csv'
    if p.exists():st.dataframe(read('modeling/comparison.csv'),hide_index=True)
    st.info('New strict Terminated vs Completed experiment: 258 development and 228 exploratory temporal evaluation records. The evaluation period was previously inspected; not an independent final test. No individual score or causal scenario simulation is offered.')
st.divider()
st.markdown('[Open the existing MiniLM + live GraphRAG demonstration](http://127.0.0.1:8502) (separately launched; requires the existing read-only Neo4j service and cached model).')
st.caption('This companion adds deterministic phase/intervention filters. It does not replace, modify, or claim to revalidate the original semantic ranker. September 2026 values may include amendments.')
