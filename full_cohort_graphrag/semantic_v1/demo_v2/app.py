"""Separate Streamlit application. Run with the documented installed UI environment."""
import json
import sys
from pathlib import Path

# Streamlit launches a file, not a package. Do not mix third-party environments.
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from full_cohort_graphrag.semantic_v1.demo_v2.client import run_question

st.set_page_config(page_title='HeartTrialTwin | Registered trial evidence', page_icon='🔎', layout='wide')
st.title('HeartTrialTwin')
st.subheader('MiniLM discovery · Neo4j evidence · Verified answers')
st.caption('Research demonstration v2 · 2,824-trial candidate universe · AACT snapshot September 5, 2026')
st.warning('Experimental — not validated for clinical decision-making. This system does not predict clinical '
           'effectiveness, patient outcomes, or treatment benefit. GraphSAGE remains a separate experimental comparison.')

with st.sidebar:
    st.header('Explore registered evidence')
    mode = st.radio('Workflow', ['Exact-NCT lookup', 'Semantic discovery', 'Question input'])
    candidate_count = st.slider('Evidence-backed discovery candidates', 1, 3, 2)
    scan_limit = st.slider('Maximum ranked candidates examined', 3, 10, 5)
    use_ollama = st.checkbox('Optional Ollama constrained explanation', value=False,
                            help='Exact-NCT non-listing questions only. One attempt; 60-second request timeout. '
                                 'This selects verified facts, not unrestricted natural-language synthesis.')
    st.caption('Defaults use deterministic cited answers. Discovery examines an unchanged ranking prefix; '
               'missing evidence may cause candidates to be skipped, with reasons shown.')

if mode == 'Exact-NCT lookup':
    nct = st.text_input('NCT identifier', 'NCT00206232')
    field = st.selectbox('Registered field', ['title', 'lead sponsor', 'intervention', 'planned outcomes',
                                             'conditions', 'phase', 'study type'])
    question = f'What {field} {"were" if field in ("planned outcomes", "conditions") else "is"} registered for {nct.strip()}?'
elif mode == 'Semantic discovery':
    measure = st.text_input('Registered planned-outcome topic', 'quality of life')
    question = f'Find trials with registered planned outcomes about {measure.strip()}.'
else:
    question = st.text_area('Question', 'What intervention is registered for clinical trial NCT00206232?')
st.info('Supported: single-trial registered titles, lead sponsors, interventions, conditions, phases, study types '
        'and complete planned outcomes. Discovery: “Find trials with registered planned outcomes about quality of life.” '
        'Other or clinical-effectiveness questions abstain; this is not a general medical chatbot.')
st.code(question, language=None)
if st.button('Retrieve verified evidence', type='primary'):
    with st.status('Processing: local MiniLM (discovery only), then read-only Neo4j and citation validation.', expanded=True) as status:
        st.write('No automatic retries. Exact lookup does not call MiniLM. Complete outcome listings do not call Ollama.')
        with st.spinner('Retrieving and validating…', show_time=True):
            result = run_question(question, candidate_count=candidate_count, scan_limit=scan_limit,
                                  answer_mode='ollama' if use_ollama else 'deterministic')
        status.update(label='Finished — ' + result['status'], state='complete' if result['status'] != 'ABSTAIN' else 'error')
    st.session_state['demo_result'] = result

if 'demo_result' in st.session_state:
    result = st.session_state['demo_result']
    st.caption('Result for: ' + result.get('question', question))
    a, b, c = st.columns(3)
    a.metric('Status', result['status'])
    b.metric('Elapsed seconds', f'{result.get("client_elapsed_seconds", result.get("elapsed_seconds", 0)):.2f}')
    c.metric('Model requests', result.get('model_attempts', 0))
    st.subheader('Verified answer')
    # Render untrusted registered source values as text, never HTML/Markdown links.
    st.text(result['answer'])
    if result.get('ranking'):
        st.subheader('Original MiniLM ranking prefix')
        st.caption('Cosine similarity is not clinical evidence. Displayed ranks are never renumbered or tuned.')
        selected = set(result['selected_nct_ids'])
        skipped = {v['nct_id']: '; '.join(v['reasons']) for v in result['skipped_candidates']}
        examined = {v['nct_id'] for v in result['trial_results']}
        st.dataframe([dict(row, disposition='Selected' if row['nct_id'] in selected else
                          'Skipped: ' + skipped[row['nct_id']] if row['nct_id'] in skipped else
                          'Examined' if row['nct_id'] in examined else 'Not examined (budget/target reached)')
                      for row in result['ranking']['ranked_trials']], hide_index=True)
        st.json(result['selection'], expanded=False)
    if result.get('skipped_candidates'):
        with st.expander('Skipped candidates and evidence limitations'):
            st.json(result['skipped_candidates'])
    for item in result.get('trial_results', []):
        bundle = item['prepared_evidence']
        with st.expander(item['nct_id'] + (' — selected evidence' if item['published'] else ' — audit evidence, not published')):
            st.text(bundle['summary'])
            st.json(bundle['completeness'], expanded=False)
            st.subheader('Source citations and relationship provenance')
            st.json(bundle['citations'], expanded=False)
    # Raw model prose is audit-only in a downloadable local trace, never an answer.
    st.download_button('Download local audit trace (JSON)', json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False),
                       file_name='hearttrialtwin_demo_trace.json', mime='application/json')
st.divider()
st.caption('Registered planned outcomes are not observed clinical results. September 2026 records may include '
           'amendments and are not certified initial-registration values. Similarity proposes candidates; '
           'Neo4j provides authoritative registered evidence. Unknown or incomplete evidence is not evidence of absence.')
