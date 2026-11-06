"""Vector 48 x 36 inch scientific poster; consumes saved results only."""
import csv,json
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FINAL=Path(__file__).resolve().parents[1];OUT=FINAL/'poster'
FONT='/System/Library/Fonts/Supplemental/'
pdfmetrics.registerFont(TTFont('Arial',FONT+'Arial.ttf'))
pdfmetrics.registerFont(TTFont('Arial-Bold',FONT+'Arial Bold.ttf'))
NAVY='#122B45';TEAL='#098A88';ORANGE='#BC5A22';PURPLE='#795AA6';GRAY='#53616F'
W,H=3456,2592;CW=1054;XS=[64,1201,2338]

def rows(name):
    with (FINAL/name).open(newline='') as f:return list(csv.DictReader(f))

def main():
    out=OUT/'HeartTrialTwin_Final_Capstone_Poster_20261102.pdf'
    c=canvas.Canvas(str(out),pagesize=(W,H),pageCompression=1,invariant=1)
    c.setTitle('HeartTrialTwin: Evidence-Grounded Trial Intelligence and Phase-Aware Operational Research')
    c.setAuthor('Obed Akwasi Aning | University of Missouri-Kansas City')
    def text(x,y,t,size=24,bold=False,color=NAVY):
        c.setFillColor(HexColor(color));c.setFont('Arial-Bold' if bold else 'Arial',size);c.drawString(x,y,t)
    def line(x,y,xx,yy,color='#BCC8D1',width=2):
        c.setStrokeColor(HexColor(color));c.setLineWidth(width);c.line(x,y,xx,yy)
    def rect(x,y,w,h,color):c.setFillColor(HexColor(color));c.rect(x,y,w,h,fill=1,stroke=0)
    def para(x,y,t,size=25,w=CW,color=NAVY):
        style=ParagraphStyle('body',fontName='Arial',fontSize=size,leading=size*1.28,textColor=HexColor(color))
        p=Paragraph(t,style);_,h=p.wrap(w,2200);p.drawOn(c,x,y-h)
        assert y-h>=105,(t[:80],y,h)
        return y-h-22
    def heading(x,y,t):
        text(x,y-34,t,36,True);line(x,y-51,x+CW,y-51,TEAL,3);return y-75
    def bars(x,y,rr,key,denom,labelkey='value',labels=None,step=43):
        maximum=max(int(r[key]) for r in rr) or 1
        for i,r in enumerate(rr):
            yy=y-i*step;lab=labels.get(r[labelkey],r[labelkey]) if labels else r[labelkey].replace('_',' ').title()
            text(x,yy,lab,22);width=460*int(r[key])/maximum;rect(x+340,yy-5,width,25,TEAL)
            text(x+825,yy,f"{int(r[key]):,} ({100*int(r[key])/denom:.1f}%)",21)
        return y-len(rr)*step-14
    labels={'EARLY_PHASE1':'Early Phase 1','PHASE1':'Phase 1','PHASE1/PHASE2':'Phase 1/2','PHASE2':'Phase 2',
        'PHASE2/PHASE3':'Phase 2/3','PHASE3':'Phase 3','PHASE4':'Phase 4','NA':'Not Applicable'}
    a=json.loads((FINAL/'analysis/results.json').read_text());m=json.loads((FINAL/'modeling/results.json').read_text())
    phase=rows('analysis/phase_status_full.csv');na=rows('analysis/na_intervention_composition.csv')
    rect(0,H-28,W,28,TEAL)
    text(64,2440,'HeartTrialTwin',90,True)
    text(64,2368,'Evidence-Grounded Trial Intelligence and Phase-Aware Operational Research',43,True)
    text(64,2310,'Obed Akwasi Aning  |  University of Missouri-Kansas City  |  CS 5588 Data Science Capstone  |  November 2, 2026',27)
    rect(64,2225,W-128,52,'#EDF5F5')
    text(86,2240,'2,824 selected trials     28,777 graph nodes     79,125 source relationships     19,740 registered planned-outcome associations',30,True)
    for xx in [1160,2296]:line(xx,165,xx,2170,'#DCE4E8',2)
    # Column 1: complete-cohort analysis, not a selected trial demonstration.
    x=XS[0];y=heading(x,2170,'1  Research objective and data')
    y=para(x,y,'Connect source-grounded heart-failure trial intelligence with transparent operational research. '
        'Separate registered facts, descriptive associations and exploratory prediction; do not infer treatment benefit.')
    y=para(x,y,'<b>Data:</b> pinned AACT/ClinicalTrials.gov snapshot, September 5, 2026. '
        'All 2,824 selected trials are interventional and have observed terminal status: '
        '<b>2,237 Completed, 393 Terminated, 194 Withdrawn.</b> This is not all HF trials worldwide or a cohort of ongoing trials.',24)
    y=heading(x,y,'2  Phase distribution: all 2,824 trials')
    y=bars(x,y-8,phase,'n',2824,labels=labels)
    y=para(x,y,'Combined phases are retained. No phase values are missing. '
        '<b>1,505 / 2,824 (53.29%)</b> are Phase Not Applicable (NA); <b>1,319</b> have applicable phases.',23)
    y=heading(x,y,'3  What do the 1,505 NA trials study?')
    y=bars(x,y-8,na,'na_trials',1505,'intervention_type',step=38)
    y=para(x,y,'Types overlap: percentages are not additive. Device, Other and Behavioral are common. '
        '<b>115 NA trials include drugs:</b> 74 drug-only and 41 mixed-type. All 115 have a source-linked audit; '
        'NA is not automatically an error or proof of nonclinical research.',23)
    y=para(x,y,'<b>Exercise/rehabilitation name cues:</b> 134 NA trials (152 in the full cohort). '
        'These are transparent lexical indicators, not independently adjudicated clinical categories.',23)
    # Column 2: applicable-phase findings and separately eligible early-snapshot modeling.
    x=XS[1];y=heading(x,2170,'4  All 1,319 phase-applicable trials')
    for i,r in enumerate(phase[:-1]):
        yy=y-12-i*47;text(x,yy,labels[r['value']],22);xx=x+275
        for s,col in [('COMPLETED',TEAL),('TERMINATED',ORANGE),('WITHDRAWN',PURPLE)]:
            width=610*int(r[s])/int(r['n']);rect(xx,yy-7,width,28,col)
            if width>48:text(xx+6,yy,str(r[s]),19,True,'#FFFFFF')
            xx+=width
        text(x+910,yy,f"n={r['n']}",21)
    y-=350
    for i,(label,color) in enumerate([('Completed',TEAL),('Terminated',ORANGE),('Withdrawn',PURPLE)]):
        rect(x+i*350,y-5,23,23,color);text(x+33+i*350,y,label,21)
    y-=45
    y=para(x,y,'<b>1,015 Completed; 214 Terminated; 90 Withdrawn.</b> Recorded termination fractions differ '
        'across phases, but sparse early/combined phases limit precision. Current enrollment is mostly Actual, '
        'not an original planned target.',23)
    y=para(x,y,'Exploratory adjusted association: phase-block likelihood-ratio <b>p=0.629</b> '
        '(phase-applicable subset; full cohort p=0.529). Models consider calendar year, drug presence, sponsor class, '
        'allocation and masking. Residual confounding and selection remain; this does not establish phase equivalence.',23)
    y=heading(x,y,'5  Historical eligibility before prediction')
    y=para(x,y,'651 prior candidates -> 615 cached observations -> 554 historical eligibility passes -> '
        '548 after six chronology quarantines -> <b>486 strict Completed/Terminated records</b> after weak-family, '
        'Withdrawn and cross-window family exclusions. Reasons can overlap.',24)
    y=para(x,y,'<b>2017-2018 development:</b> 258 trials / 47 Terminated.<br/>'
        '<b>2019-2020 reassessment:</b> 228 / 39 Terminated (17.11%).<br/>'
        'Early 0-45-day snapshots are not verified original registrations. The later period was previously inspected: '
        '<b>not an independent final test.</b>',24)
    y=heading(x,y,'6  Fixed, exploratory logistic models')
    text(x,y,'Model',23,True);text(x+540,y,'ROC-AUC',23,True);text(x+740,y,'AP',23,True);text(x+890,y,'Brier',23,True);y-=48
    pretty={'intercept':'Intercept only','phase_only':'Phase only','metadata_without_phase':'Metadata without phase','metadata_with_phase':'Metadata with phase'}
    for name,d in m['models'].items():
        r=d['exploratory_temporal_evaluation'];text(x,y,pretty[name],23)
        for xx,k in [(540,'auroc'),(740,'auprc_average_precision'),(890,'brier')]:text(x+xx,y,f'{r[k]:.4f}',23)
        y-=45
    y-=10
    y=para(x,y,'AP = average precision; prevalence reference <b>0.1711</b>. '
        'Adding phase: AP difference <b>-0.00235</b>, paired family-bootstrap 95% interval '
        '<b>[-0.01334, +0.00527]</b> (500 resamples). No clear incremental benefit. '
        'Both metadata Brier scores are worse than the constant reference. <b>Risk release remains blocked.</b>',23)
    y=heading(x,y,'7  Recruitment: source-linked reason coding')
    y=para(x,y,'All <b>587</b> stopped records reviewed by a conservative text rule; <b>543</b> have nonblank reasons. '
        'Explicit recruitment-difficulty cues occur in <b>99/393 Terminated</b> and <b>23/194 Withdrawn</b> records. '
        'Another 115 recruitment mentions need review; 44 reasons are missing. '
        'These are registry-reported cues, not adjudicated causes or a validated recruitment-risk target.',24)
    # Column 3: original graph application is preserved, with new opt-in offline companion.
    x=XS[2];y=heading(x,2170,'8  Integrated research system')
    steps=[('Pinned registered evidence','2,824 trials; original source IDs and snapshot provenance'),
        ('Existing MiniLM -> Neo4j -> GraphRAG','Semantic candidates; read-only evidence; verified citations'),
        ('Existing Streamlit + new offline companion','Exact NCT lookup; phase/intervention filters; complete listings')]
    for title,description in steps:
        rect(x,y-118,CW,118,'#EDF5F5');text(x+18,y-36,title,27,True)
        para(x+18,y-58,description,23,CW-36);y-=152
        if title!=steps[-1][0]:line(x+CW/2,y+28,x+CW/2,y+5,GRAY,3)
    y=para(x,y+5,'Separate historical AACT snapshots feed the new risk experiment. Current graph values are '
        '<b>not backfilled</b> into prediction-time features. Only aggregate experimental metrics are shown; '
        'no individual prospective risk score or causal digital twin is deployed.',24)
    y=heading(x,y,'9  Actual source-grounded demonstration')
    y=para(x,y,'<b>NCT00206232</b><br/>Registered intervention: <b>Spironolactone</b><br/>'
        'Lead sponsor: <b>Baylor College of Medicine</b><br/>'
        'All <b>7</b> registered planned outcomes returned with trial-bound citations, types and time frames.<br/>'
        'Example: <b>Six minute walk distance</b> (primary), baseline then 3 and 6 months after randomization.',24)
    y=para(x,y,'Source: <b>design_outcomes.txt</b>; NCT-bound source IDs and citation bindings retained in the '
        'downloadable trace. The new companion was executed against verified local CSVs, <b>not a new live Neo4j test</b>. '
        'Zero Ollama calls. Unsupported survival-benefit questions abstain.',22)
    y=heading(x,y,'10  What worked, and what did not')
    y=para(x,y,'<b>Working:</b> authoritative evidence retrieval, complete deterministic listings, '
        'missing-evidence abstention and source-linked descriptive exploration. '
        '<b>166 relevant offline tests passed</b> (25 new; 141 existing).',24)
    y=para(x,y,'<b>Experimental GraphSAGE:</b> prior frozen association-ranking test MRR 0.01124 versus '
        'MiniLM 0.07619 and context pooling 0.07841. GraphSAGE remains a research comparison, not the default ranker. '
        'No old experiment was retrained or retuned for this poster.',24)
    y=heading(x,y,'11  Limitations and next steps')
    y=para(x,y,'Terminal-outcome selection prevents population-wide ongoing-trial risk claims. '
        'Historical availability is restricted; registry updates can lag events. Family screening and '
        'confounder control are incomplete. NA drug-phase rationale is not adjudicated. '
        'Sparse events, wide intervals and prior evaluation exposure limit prediction claims.',24)
    y=para(x,y,'Next: independently adjudicate chronology, related trials and recruitment reasons; '
        'acquire original/time-stamped plans; prospectively freeze independent confirmation data. '
        'A scenario explorer remains <b>conceptual</b>, not evidence that changing a design causes a change in risk.',24)
    y=heading(x,y,'Conclusion')
    y=para(x,y,'HeartTrialTwin delivers reproducible trial intelligence and comprehensive operational description. '
        '<b>Phase is informative for describing the cohort, but incremental forecasting value is not established.</b>',25)
    line(64,140,W-64,140,TEAL,3)
    text(64,100,'Research only. Registered planned outcomes are not observed clinical results. Experimental - not validated for clinical decision-making.',25,True)
    text(64,57,'Sources: AACT HTT-P1-AACT-20260905; graph manifest 3ef82624d131...; local result tables and SHA-256 manifests accompany this poster.',21)
    url='https://github.com/akwasianing/HeartTrialTwin';text(2460,57,url,21)
    c.linkURL(url,(2460,49,3395,83),relative=0)
    c.showPage();c.save();print(out)

if __name__=='__main__':main()
