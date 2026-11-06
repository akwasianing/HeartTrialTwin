"""Offline, no model-service/database calls; new small risk models only."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
FINAL=Path(__file__).resolve().parents[1]
for directory in ['analysis','modeling','integration']:sys.path.insert(0,str(FINAL/directory))
from common import *
import train_exploratory as train
from phase_explorer import PhaseExplorer

class DataAndRiskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=rows(FINAL/'modeling/analysis_cohort.csv');cls.ledger=rows(FINAL/'modeling/eligibility_ledger_651.csv')
        cls.config=json.loads((FINAL/'modeling/experiment_config.json').read_text());cls.studies,_,cls.iv,_=load_current()

    def test_pinned_inputs_and_protected_artifacts(self):
        pins=verify_sources();self.assertEqual(len(pins['source_sha256']),94)
        self.assertGreaterEqual(len(pins['protected_sha256']),199)

    def test_completed_analysis_output_hashes(self):
        m=json.loads((FINAL/'analysis/output_manifest.json').read_text())
        for p,h in m['outputs'].items():self.assertEqual(sha(FINAL/p),h,p)

    def test_full_membership_and_phase_accounting(self):
        self.assertEqual(len(self.studies),2824)
        self.assertEqual(sum(r['phase']!='NA' for r in self.studies.values()),1319)
        self.assertEqual(sum(r['phase']=='NA' for r in self.studies.values()),1505)
        phase=rows(FINAL/'analysis/phase_status_full.csv');self.assertEqual(sum(int(r['n']) for r in phase),2824)
        self.assertEqual(sum(int(r['TERMINATED']) for r in phase),393)

    def test_na_drug_composition_source_membership(self):
        ids={n for n,r in self.studies.items() if r['phase']=='NA' and any(v['intervention_type']=='DRUG' for v in self.iv[n])}
        self.assertEqual(len(ids),115)
        self.assertEqual(ids,{r['nct_id'] for r in rows(FINAL/'analysis/na_drug_trial_audit.csv')})

    def test_651_ledger_and_strict_labels(self):
        self.assertEqual(len(self.ledger),651);self.assertEqual(len({r['nct_id'] for r in self.ledger}),651)
        self.assertEqual(len(self.data),486)
        self.assertEqual({r['terminal_status'] for r in self.data},{'COMPLETED','TERMINATED'})
        self.assertTrue(all((r['y']=='1')==(r['terminal_status']=='TERMINATED') for r in self.data))

    def test_six_chronology_records_excluded(self):
        bad={r['nct_id'] for r in self.ledger if 'ACTUAL_COMPLETION_' in r['reasons']}
        self.assertEqual(len(bad),6);self.assertFalse(bad&{r['nct_id'] for r in self.data})

    def test_weak_and_strong_family_isolation(self):
        weak={n for r in rows(ROOT/'gnn_graphrag/protocols/HTT-GNN-ASSOC-PROTOCOL-v2/family_pairs.csv') if r['strength']=='WEAK' for n in [r['left_nct_id'],r['right_nct_id']]}
        self.assertFalse(weak&{r['nct_id'] for r in self.data})
        a={r['family_id'] for r in self.data if r['window']=='development'};b={r['family_id'] for r in self.data if r['window']!='development'}
        self.assertFalse(a&b);self.assertNotIn('NCT04096040',{r['nct_id'] for r in self.data})

    def test_fixed_forward_folds(self):
        dev=[r for r in self.data if r['window']=='development']
        folds=list(train.forward_folds(dev));self.assertEqual(len(folds),3)
        for _,tr,va,_ in folds:
            self.assertLess(max(r['observation_date'] for r in tr),min(r['observation_date'] for r in va))
            self.assertFalse({r['family_id'] for r in tr}&{r['family_id'] for r in va})

    def test_features_exclude_audit_identifiers_and_future_fields(self):
        for name in ['phase_only','metadata_without_phase','metadata_with_phase']:
            X,num,cat=train.inputs(self.data[:3],name);fields=set(num+cat)
            self.assertFalse(fields&{'nct_id','y','terminal_status','window','observation_date','family_id','source_record_sha256','enrollment','completion_date','why_stopped'})
            self.assertEqual('historical_phase' in fields,name!='metadata_without_phase')

    def test_training_only_vocabulary_and_imputation(self):
        tr=copy.deepcopy(self.data[:20]);va=copy.deepcopy(self.data[20:21]);va[0]['masking']='NEVER_IN_TRAIN'
        m=train.fit_model(tr,'metadata_with_phase',self.config)
        cat=m.named_steps['prepare'].named_transformers_['categorical']
        self.assertNotIn('NEVER_IN_TRAIN',set(v for c in cat.categories_ for v in c))
        self.assertTrue(np.isfinite(train.predict(m,va,'metadata_with_phase')).all())
        expected=np.nanmedian(np.array(train.inputs(tr,'metadata_with_phase')[0][:,:15],float),axis=0)
        actual=m.named_steps['prepare'].named_transformers_['numeric'].named_steps['impute'].statistics_
        np.testing.assert_allclose(actual,np.nan_to_num(expected))

    def test_saved_models_reproduce_saved_new_predictions(self):
        pred=rows(FINAL/'modeling/exploratory_predictions.csv');byid={r['nct_id']:r for r in self.data};ev=[byid[r['nct_id']] for r in pred]
        for name in self.config['models']:
            m=train.joblib.load(FINAL/'modeling'/f'{name}.joblib')
            np.testing.assert_allclose(train.predict(m,ev,name),[float(r[name]) for r in pred],atol=1e-12,rtol=0)

    def test_model_run_manifest_and_nonrelease(self):
        manifest=json.loads((FINAL/'modeling/run_manifest.json').read_text())
        for p,h in manifest['artifacts'].items():self.assertEqual(sha(FINAL/'modeling'/p),h,p)
        result=json.loads((FINAL/'modeling/results.json').read_text())
        self.assertFalse(result['independent_test']);self.assertEqual(result['risk_release'],'BLOCKED_EXPLORATORY_ONLY')
        self.assertEqual(result['uncertainty']['valid_resamples'],500)

    def test_recruitment_all_stopped_and_source_codes(self):
        rr=rows(FINAL/'recruitment/reason_coding.csv');self.assertEqual(len(rr),587)
        self.assertEqual({r['nct_id'] for r in rr},{n for n,s in self.studies.items() if s['overall_status']!='COMPLETED'})
        for r in rr:
            self.assertEqual(r['why_stopped_verbatim'],self.studies[r['nct_id']]['why_stopped'].strip())
            if r['code']=='EXPLICIT_RECRUITMENT_DIFFICULTY':self.assertTrue(r['matched_spans']);self.assertEqual(r['explicit_negation_flag'],'False')


class OfflineIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch('socket.socket',side_effect=AssertionError('Network forbidden')):cls.e=PhaseExplorer()

    def test_search_exact_source_filters(self):
        result=self.e.search('NA','DEVICE',20);self.assertEqual(result['total'],497);self.assertEqual(result['returned'],20)
        self.assertTrue(result['has_more']);self.assertEqual([r['nct_id'] for r in result['records']],sorted(r['nct_id'] for r in result['records']))
        self.assertTrue(all(r['phase']=='NA' and 'DEVICE' in r['intervention_types'] for r in result['records']))

    def test_all_seven_outcomes_citations_and_types(self):
        r=self.e.answer('What planned outcomes were registered for NCT00206232?');self.assertEqual(r['status'],'COMPLETE_LISTING')
        facts=r['answer_trace']['listed_outcomes'];source=r['prepared_evidence']['trials'][0]['categories']['planned_outcomes']
        self.assertEqual(len(facts),7);self.assertEqual({f['evidence_id'] for f in facts},{f['evidence_id'] for f in source})
        self.assertEqual(r['model_attempts'],0)
        refs={v['citation_id']:v for v in r['prepared_evidence']['citations']}
        for f in facts:
            self.assertEqual(f['nct_id'],'NCT00206232')
            for cid in f['citation_ids']:
                self.assertEqual(refs[cid]['nct_id'],f['nct_id']);self.assertEqual(refs[cid]['evidence_id'],f['evidence_id'])

    def test_sponsor_and_intervention_grounding(self):
        for field,needle in [('lead sponsor','Baylor College of Medicine'),('intervention','Spironolactone')]:
            r=self.e.answer(f'What {field} is registered for NCT00206232?')
            self.assertEqual(r['status'],'GROUNDED');self.assertIn(needle,r['answer']);self.assertIn('[cite:',r['answer'])

    def test_unsupported_effectiveness_abstention(self):
        r=self.e.answer('Did spironolactone improve survival in NCT00206232?')
        self.assertEqual(r['status'],'ABSTAIN');self.assertEqual(r['model_attempts'],0)

    def test_unknown_missing_invalid_not_substituted(self):
        for question in ['What planned outcomes were registered for NCT99999999?',
                         'What planned outcomes were registered for NCT00000475?', 'What title is registered for NCT123?']:
            self.assertEqual(self.e.answer(question)['status'],'ABSTAIN')

    def test_bounded_search_rejects_invalid_filters(self):
        for kwargs in [{'limit':0},{'limit':51},{'phase':'invented'},{'intervention_type':'invented'}]:
            with self.assertRaises(ValueError):self.e.search(**kwargs)


if __name__=='__main__':unittest.main()
