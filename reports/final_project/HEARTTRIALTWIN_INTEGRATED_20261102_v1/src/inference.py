"""Acknowledged, training-profile-only arithmetic sensitivity; not forecasting."""
import copy,gzip,importlib.metadata,json,math
import numpy as np
import joblib
from identity import *

legacy_paths()
import train_exploratory as trained

MODELS=('intercept','phase_only','metadata_without_phase','metadata_with_phase')
WARNINGS=[
    'Experimental model-behavior demonstration; not validated prospective risk or clinical advice.',
    'Target: Terminated (1) versus Completed (0), conditional on observed terminal outcomes; Withdrawn excluded.',
    'Only original 2017–2018 development profiles are selectable. These are in-sample scores, not new validation.',
    'Early snapshots are not certified original registration records; no current values backfill historical inputs.',
    'Weak discrimination, calibration and previously inspected evaluation prevent forecasting release.',
    'Hypothetical score changes are not causal effects or optimal-design recommendations.',
    'Marginal enrollment limits do not establish scientific feasibility or joint design support.',
]


class ResearchInference:
    def __init__(self):
        verify_base()
        self.results=load(BASE/'modeling/results.json')
        require(importlib.metadata.version('scikit-learn')==self.results['environment']['scikit-learn'],
                'Use the verified .venv-vector-rag scikit-learn environment')
        self.rows={r['nct_id']:r for r in read_csv(BASE/'modeling/analysis_cohort.csv') if r['window']=='development'}
        require(len(self.rows)==258,'Development membership mismatch')
        history_path=ROOT/'full_system_feasibility/snapshot_strategy/historical_snapshot_eligibility_audit_HTT-P1-AACT-HIST-A45-20260921.csv'
        verify_source(history_path)
        self.history={r['nct_id']:r for r in read_csv(history_path)}
        self.eligible={n:r for n,r in self.rows.items() if r['log_planned_enrollment'] and self._enrollment(r)>0}
        self.models={name:joblib.load(BASE/'modeling'/f'{name}.joblib') for name in MODELS}
        enroll=[self._enrollment(r) for r in self.eligible.values()]
        self.enrollment_range=(min(enroll),max(enroll));self.central_range=tuple(map(float,np.percentile(enroll,[5,95])))
        self._source_cache={}

    @staticmethod
    def _enrollment(row):
        return int(round(float(np.expm1(float(row['log_planned_enrollment'])))))

    def _row(self,nct):
        require(isinstance(nct,str) and nct in self.eligible,
                'Select a source-backed development profile with positive historical Anticipated enrollment; no current/held-out/arbitrary profiles')
        row=copy.deepcopy(self.eligible[nct]);h=self.history[nct]
        require(h['observation_date']==row['observation_date'] and h['snapshot_record_sha256']==row['source_record_sha256'],
                'Historical source association mismatch')
        require(trained.q.normalized(h['enrollment_type'])=='ANTICIPATED' and int(h['enrollment'])==self._enrollment(row),
                'Enrollment is not the verified historical Anticipated target')
        return row,h

    def _raw(self,row,h):
        obs=row['observation_date']
        if obs not in self._source_cache:
            candidates=sorted((ROOT/'full_system_feasibility/snapshot_strategy/archive_extracts').glob(obs+'*.json.gz'))
            require(len(candidates)==1,'Historical cache identity unavailable')
            pins=load(BASE/'reports/source_preservation_manifest.json')['source_sha256']
            expected=pins.get(str(candidates[0].relative_to(ROOT)))
            require(expected and sha(candidates[0])==expected,'Historical cache checksum failure')
            with gzip.open(candidates[0],'rt') as f:self._source_cache[obs]=json.load(f)['tables']
        tables=self._source_cache[obs]
        raw={name:tables[name].get(row['nct_id'],[]) for name in trained.q.TABLES}
        digest=hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        require(digest==row['source_record_sha256'],'Historical record checksum failure')
        return raw

    def profiles(self):
        return {'version':VERSION,'mode':'HISTORICAL_DEVELOPMENT_ONLY','count':len(self.eligible),
            'excluded_development_profiles_missing_target':len(self.rows)-len(self.eligible),
            'profiles':[{'nct_id':n,'title':self.history[n]['brief_title'],'historical_phase':r['historical_phase'],
                'observation_date':r['observation_date'],'planned_enrollment':self._enrollment(r),'scenario_bounds':self.bounds(r)} for n,r in sorted(self.eligible.items())],
            'development_enrollment_range':list(self.enrollment_range),
            'warnings':WARNINGS,'forecasting_release':'BLOCKED_UNCHANGED'}

    def bounds(self,row):
        enrollment=self._enrollment(row);arms=trained.num(row['number_of_arms'])
        minimum=max(self.enrollment_range[0],math.ceil(enrollment/2),math.ceil(arms) if arms else 1)
        maximum=min(self.enrollment_range[1],enrollment*2)
        return {'minimum':minimum,'maximum':maximum,'baseline':enrollment,
            'modifiable':bool(arms and enrollment>=arms and minimum<=maximum),
            'policy':'Only Anticipated enrollment; integer, observed development range, 0.5x–2x baseline, at least recorded arm count. Phase/design held fixed.',
            'central_development_p5_p95':list(self.central_range)}

    def score(self,nct,*,planned_enrollment=None,acknowledge=False):
        require(acknowledge is True,'Explicit research-only acknowledgment required')
        row,h=self._row(nct);raw=self._raw(row,h);bounds=self.bounds(row)
        baseline=copy.deepcopy(row);modified=copy.deepcopy(row);enrollment=self._enrollment(row)
        if planned_enrollment is not None:
            require(type(planned_enrollment) is int,'Hypothetical enrollment must be an integer, not Boolean or free text')
            require(bounds['modifiable'],'Recorded arm count is missing/inconsistent; hypothetical enrollment changes unavailable')
            require(bounds['minimum']<=planned_enrollment<=bounds['maximum'],'Hypothetical enrollment outside conservative support bounds')
            enrollment=planned_enrollment
            if enrollment!=self._enrollment(row):modified['log_planned_enrollment']=float(np.log1p(enrollment))
        scores=[]
        for name in MODELS:
            values=trained.predict(self.models[name],[baseline,modified],name)
            require(np.isfinite(values).all() and np.all((values>=0)&(values<=1)),'Invalid model output')
            scores.append({'model':name,'baseline_score':float(values[0]),'hypothetical_score':float(values[1]),
                'score_difference':float(values[1]-values[0]),'interpretation':'Conditional classifier score; not validated future-risk probability',
                'evaluation':self.results['models'][name]['exploratory_temporal_evaluation']})
        numeric,categorical=trained.inputs([baseline],'metadata_with_phase')[1:]
        features=[{'field':f,'baseline_historical_value':baseline[f],'hypothetical_value':modified[f],
            'changed':baseline[f]!=modified[f]} for f in numeric+categorical]
        references=[]
        for table in ['studies.txt','designs.txt','interventions.txt','sponsors.txt']:
            records=raw[table]
            if table=='sponsors.txt':records=[r for r in records if r['lead_or_collaborator'].lower()=='lead']
            references.extend({'source_table':table,'source_record_id':r.get('id') or nct,'nct_id':nct,
                'observation_date':h['observation_date'],'snapshot_archive':h['snapshot_file'],
                'snapshot_source_url':h['snapshot_source_url'],'six_table_record_sha256':row['source_record_sha256']} for r in records)
        warnings=list(WARNINGS)
        if not self.central_range[0]<=enrollment<=self.central_range[1]:warnings.append('Enrollment is in a development-distribution tail outside the 5th–95th percentile; estimates may be unstable.')
        missing=[f for f in numeric+categorical if not baseline[f] or baseline[f]=='__MISSING__']
        if missing:warnings.append('Saved training-only imputation/encoding handles missing fields: '+', '.join(missing))
        return {'version':VERSION,'status':'EXPERIMENTAL_SENSITIVITY_ONLY','forecasting_release':'BLOCKED_UNCHANGED',
            'nct_id':nct,'historical_title':h['brief_title'],'observation_date':h['observation_date'],
            'source_profile_origin':'ORIGINAL_2017_2018_DEVELOPMENT_RECORD','baseline_planned_enrollment':self._enrollment(row),
            'hypothetical_planned_enrollment':enrollment,'changed_fields':[f['field'] for f in features if f['changed']],
            'bounds':bounds,'features':features,'scores':scores,'source_references':references,
            'baseline_is_recorded':True,'modified_is_hypothetical':planned_enrollment is not None,
            'phase_modified':False,'source_evidence_written':False,'model_fits':0,'warnings':warnings,
            'individual_confidence_interval':None,'uncertainty_note':'No validated individual-score interval. Reported model metric intervals apply to aggregate exploratory evaluation, not this scenario.',
            'model_checksums':{name:sha(BASE/'modeling'/f'{name}.joblib') for name in MODELS},
            'prior_package_manifest_sha256':BASE_MANIFEST_SHA}
