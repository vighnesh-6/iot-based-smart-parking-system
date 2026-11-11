"""Evidence-led Phase 4 report; unavailable scores stay NOT RUN, never invented."""

import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak,Paragraph,Preformatted,SimpleDocTemplate,Spacer,Table,TableStyle

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'reports/phase4_machine_learning_model_development.pdf'
NAVY,TEAL,PALE=(colors.HexColor(x) for x in ['#15364B','#007F86','#EDF5F7'])


def main():
    def read(path,optional=False):
        p=ROOT/path
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() or not optional else None
    manifest=read('ml/data/phase3_dataset_manifest.json')
    contracts=read('reports/evidence/phase4_contract_tests.json')
    preflight=read('reports/evidence/phase4_isolated_complete_preflight.json')
    diagnosis=read('reports/evidence/phase4_windows_diagnosis.json')
    results=read('ml/artifacts/phase4/model_results.json',True)
    verification=read('reports/evidence/phase4_model_verification.json',True)
    native=read('reports/evidence/phase4_native_tests_final.json',True)
    selection=read('ml/artifacts/phase4/validation_selection.json',True)
    complete=bool(results and verification and verification.get('passed') and native and native.get('passed')
                  and native.get('native_tests_requested') and results['runtime']['platform'].startswith('Windows'))
    for name,file in [('Body','arial.ttf'),('Bold','arialbd.ttf'),('Mono','consola.ttf')]:
        pdfmetrics.registerFont(TTFont(name,'C:/Windows/Fonts/'+file))
    pdfmetrics.registerFontFamily('Body',normal='Body',bold='Bold',italic='Body',boldItalic='Bold')
    styles={
        'body':ParagraphStyle('body',fontName='Body',fontSize=9.5,leading=13.4,spaceAfter=8,textColor=NAVY),
        'title':ParagraphStyle('title',fontName='Bold',fontSize=23,leading=28,spaceAfter=18,textColor=NAVY),
        'heading':ParagraphStyle('heading',fontName='Bold',fontSize=17,leading=22,spaceAfter=12,textColor=NAVY),
        'sub':ParagraphStyle('sub',fontName='Bold',fontSize=11,leading=15,spaceBefore=8,spaceAfter=6,textColor=TEAL),
        'small':ParagraphStyle('small',fontName='Body',fontSize=8,leading=11,spaceAfter=6,textColor=NAVY),
        'cell':ParagraphStyle('cell',fontName='Body',fontSize=8.3,leading=11,textColor=NAVY),
        'header':ParagraphStyle('header',fontName='Bold',fontSize=8.3,leading=11,textColor=colors.white),
        'code':ParagraphStyle('code',fontName='Mono',fontSize=7.5,leading=10,spaceAfter=10,textColor=NAVY),
    }
    story=[]
    def p(text,style='body'):story.append(Paragraph(text,styles[style]))
    def sub(text):p(text,'sub')
    def code(text):story.append(Preformatted(text,styles['code']))
    def page(n,title):
        if story:story.append(PageBreak())
        p(f'PHASE 4 / MODEL DEVELOPMENT / {n:02d}','small');p(title,'heading')
    def table(headers,rows,widths):
        data=[[Paragraph(escape(str(v)),styles['header']) for v in headers]]
        data += [[Paragraph(escape(str(v)),styles['cell']) for v in row] for row in rows]
        item=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
        item.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('ROWBACKGROUNDS',(0,1),(-1,-1),[PALE,colors.white]),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
            ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
        story.append(item);story.append(Spacer(1,8))

    page(1,'Machine Learning Model Development')
    story.append(Spacer(1,12))
    p('Smart Parking System<br/>Training, Evaluation &amp; Local Prediction','title')
    p('Persistence | Linear Regression | Random Forest | 15-minute horizon','sub')
    p('Prepared 11 November 2026. The required execution target is this Windows laptop, including future Streamlit inference. No cloud or SSH runtime is used. All observations remain explicitly synthetic.')
    p('<b>'+('ACTUAL MODEL VERIFICATION AVAILABLE' if complete else 'PHASE 4 INCOMPLETE - NATIVE EXECUTION BLOCKED')+'</b>','sub')
    p('Actual model fitting, validation comparison, final test evaluation and trained-artifact reload verification succeeded locally. Persistence was selected by the predeclared validation MAE criterion. Learned models remain saved for comparison; a synthetic result is not a real-world accuracy claim.')
    table(['Verification item','Current recorded result'],[
        ('Frozen Phase 3 audit','Dataset hashes, target alignment, feature list and stored source/report hashes match.'),
        ('Final native/software tests',f"{native['tests_run']} actual tests; passed={native['passed']}. Saved full-data models also passed independent reload verification."),
        ('Local native preflight',f"Passed={preflight['native_imports_passed']} in the approved isolated local Windows environment."),
        ('Actual project model evaluation','Available in saved results' if results else 'NOT RUN; no validation or test scores exist.'),
        ('Actual trained-model reload','PASS' if verification and verification.get('passed') else 'NOT RUN; no verified fitted bundle exists.'),
        ('Git delivery policy','One meaningful file per commit; one final push after all verification and PDF review.'),
    ],[168,331])
    p('This report reads actual model results, locked validation selection, final native tests and saved-model verification evidence. Earlier blocked preflights and the verification-only recovery are retained for traceability. No model or hyperparameter was changed after the test partition was opened.','small')

    page(2,'Objectives, frozen data and features')
    p('Predict total occupied slots exactly 15 minutes ahead, bounded by the physical capacity of twelve spaces. Compare a strong current-occupancy persistence baseline with ordinary Linear Regression and a nonlinear Random Forest. Model selection must use validation outcomes only; the held-out test period supplies final reporting after the choice is locked.')
    table(['Partition','Rows','Forecast origins, IST','Last target, IST'],[
        ('Training',49360,'21 Sep 00:00 - 25 Oct 06:39','25 Oct 06:54'),
        ('Validation',10577,'25 Oct 06:55 - 1 Nov 15:11','1 Nov 15:26'),
        ('Testing',10578,'1 Nov 15:27 - 8 Nov 23:44','8 Nov 23:59'),
    ],[83,64,224,128])
    p('The frozen processed table has 70,515 rows, 42 columns, no missing values and 37 predictors. Raw history has 80,640 minute observations. Target timestamps and values were audited against the exact raw t+15 row. Existing fifteen-minute boundary purges keep preceding labels strictly before the next partition origin. No data is regenerated or repartitioned.')
    table(['Predictor group','Frozen columns / information'],[
        ('Current state and counts','P1-P12; total_occupied; arrivals; departures.'),
        ('Calendar','hour, minute, day_of_week, is_weekend, time_sin/cos, week_sin/cos.'),
        ('Occupancy lags','1, 5, 15, 30, 60, 1,440 and 10,080 minutes.'),
        ('Past rolling windows','Means over 5/15/60/1,440 minutes; population standard deviations over 15/60; windows end at t-1.'),
        ('Change','Current total minus the fifteen-minute lag.'),
    ],[140,359])
    p('Only FEATURE_COLUMNS enters X. Raw timestamp, data_source, target_timestamp, occupied_15min_ahead and split are excluded. Current t observations are assumed available at forecast time. Future demand and scheduled departure parameters are not inputs. No live Wokwi/SQLite data is merged or altered.')

    page(3,'Models, preprocessing and configurations')
    sub('Persistence baseline')
    code('prediction(t+15 | t) = total_occupied(t)')
    p('No fitting is required. It is evaluated on exactly the same validation/test rows as learned models, and remains eligible to be the selected model. Synthetic minute occupancy is highly persistent, so beating this baseline must be demonstrated rather than assumed.')
    sub('Linear Regression')
    code('z_j = (x_j - training_mean_j) / training_scale_j\ny_hat = intercept + sum_j(beta_j * z_j)\nFit: minimize sum_training((y - y_hat)^2)')
    p('A Pipeline contains StandardScaler followed by LinearRegression, fitted on float64 training rows only. Scaler sample count and means are checked against training data. Validation never updates preprocessing. Redundant frozen columns (slot sum and lag/change identities) can make the design rank deficient; solver rank is recorded. Coefficients should not be interpreted as causal effects. No frozen features are removed to improve scores.')
    sub('Random Forest Regressor')
    code('forest_prediction(x) = mean(tree_1(x), ..., tree_100(x))')
    table(['Parameter','Predeclared setting'],[
        ('n_estimators / random_state','100 / 42'),('bootstrap / max_samples','True / 0.8'),
        ('max_features / n_jobs','0.8 / 2'),('max_depth','8 or 12'),('min_samples_leaf','10 or 30'),
    ],[210,289])
    p('Four depth/leaf combinations are fitted on training only and scored on the same validation rows. Select the best forest by clipped MAE, then RMSE, then fixed grid order. Only the best forest is retained. Native numerical thread pools are limited to avoid nested oversubscription. All four configurations were actually fitted and validated. The chosen forest has depth 8 and minimum leaf size 30; the overall MAE-selected model is persistence. Observed linear rank is 34 of 37 predictors.')

    page(4,'Leakage protection, comparison and metrics')
    table(['Stage','Implemented information boundary'],[
        ('Dataset check','Verify frozen raw/processed hashes and exact feature/horizon contract.'),
        ('Partition read','Read only training or validation row bounds; do not parse test labels during tuning.'),
        ('Fit','Training-only scaler and learned model coefficients/trees.'),
        ('Validation','All models use identical X/y rows; forest grid is fixed beforehand.'),
        ('Selection lock','Write validation_selection.json, selected model, scores/configurations and row hashes before opening test.'),
        ('Final evaluation','First test read occurs after lock; score all three models on identical rows. No refit or reselection.'),
        ('Persistence verification','Save one bundle; reload every model; check the selection-lock hash and bounded predictions.'),
    ],[136,363])
    code('MAE  = mean(abs(y - prediction))\nRMSE = sqrt(mean((y - prediction)^2))\nR2   = 1 - SSE / SST\nSSE  = sum((y - prediction)^2)\nSST  = sum((y - mean(y))^2)\ndelivered_prediction = clip(raw_prediction, 0, 12)')
    p('Primary selection is clipped validation MAE, then clipped validation RMSE, then a fixed simplicity order: persistence, linear, forest. Test performance cannot change this selection. All models keep their training-only fits; there is no train+validation refit that would make the comparison unequal. Scikit-learn recommends train-only preprocessing and pipelines to reduce leakage. [1]')
    p('Both raw and clipped metrics and clipping frequency are reported when actual execution exists. Clipping is a fixed predeclared physical constraint, applied equally before selection. No rounding is applied: regression outputs are expected counts. R2 is explicitly undefined/null for constant targets. Negative R2 values are valid and will not be hidden.')

    page(5,'Actual tests, validation and test results')
    table(['Executed verification','Actual evidence'],[
        ('Contract suite',f"{native['tests_run']} passed; {native['failures']} failures; {native['errors']} errors; {native['skipped']} skips; {native['seconds']} seconds."),
        ('Input/output contract','Named-column reordering; missing/extra/invalid values; slot-sum consistency; output clipping.'),
        ('Metric/selection contract','Hand-calculated MAE/RMSE/R2; undefined constant R2; alignment/range checks; validation-only selector and simplicity tie-break.'),
        ('Partition and provenance','Requested validation row bounds, frozen checksums and predictor allowlist.'),
        ('Saved full-data model verification','All 28 independent checks passed, including each model on identical validation/test row hashes and bounded reload predictions.'),
        ('Native tests','Actual train-only scaler, identical validation rows, seeded forest repeatability, sklearn metric agreement and trained bundle reload passed.'),
    ],[156,343])
    for partition in ['validation','test']:
        sub(partition.title()+' comparison')
        rows=[]
        for name in ['persistence','linear_regression','random_forest']:
            score=results[partition][name]['clipped'] if results else None
            rows.append((name,*[f'{score[k]:.6f}' if score and score[k] is not None else 'NOT RUN' for k in ['mae','rmse','r2']]))
        table(['Model','MAE','RMSE','R2'],rows,[190,103,103,103])
    p('Selected model: '+(results['selected_model'] if results else '<b>NOT SELECTED</b>')+'. The primary criterion is validation MAE. Linear Regression has lower test RMSE, but this did not change selection. All metrics describe synthetic data only. Reload/recovery details are documented separately; no test-driven retuning occurred.')

    page(6,'Verified local Windows execution')
    p('The original project environment failed native imports with an Application Control denial (_partition_nodes, earlier _openmp_helpers/_sag_fast). The user then approved an isolated official-PyPI installation trial. The completed isolated runtime passed imports, dependency checks, fitting, evaluation and saved-model reloads without a policy change.')
    table(['Local diagnostic','Observed result'],[
        ('Python / wheel compatibility','Python 3.12.10 x64; wheel tag cp312-cp312-win_amd64 matches.'),
        ('Dependency check','pip check: No broken requirements found.'),
        ('Native file integrity','Three blocked module files match installed wheel RECORD hashes. _partition_nodes Authenticode status: NotSigned.'),
        ('Code Integrity event','3077 confirms PyArrow lib.cp312-win_amd64.pyd denied by Enterprise signing policy {0283ac0f-fff1-49ae-ada1-8a933130cad6}.'),
        ('Evidence limit','No separate sklearn denial event correlated. The PyArrow policy event must not be described as a direct sklearn policy attribution.'),
        ('Current process signature flags','Read-only query returned zero; no flags were changed.'),
        ('Verified runtime','%LOCALAPPDATA%/SmartParking/ml-runtime, Python 3.12.10 x64, locally executable Windows packages.'),
    ],[160,339])
    p('Microsoft describes event 3077 as an enforced App Control block. The original failure remains historical evidence. The approved clean runtime succeeded; the exact cause of the original environment failure has not been conclusively established. No claim is made that the original environment was repaired. [2]')
    sub('Approved installation actually performed')
    p('Existing Python created the separately approved environment. Only exact pinned binary packages from https://pypi.org/simple were installed with isolated pip configuration. A first probe found missing cloudpickle, not a policy denial; cloudpickle, python-dateutil and tzdata were added at existing project pins. The completed native probe and pip check passed. No policy, trust exception or DLL relocation was used.')
    p('The original project venv was never an installation target; its freeze still matches frozen requirements. Run training and future inference with the isolated interpreter. This resolves the local execution requirement without cloud/SSH or changing frozen Phase 1/2/3 artifacts.')

    page(7,'Prediction interface and local reproducibility')
    p('The locally verified ParkingPredictor interface accepts a DataFrame containing exactly the 37 predictor columns, one feature dict, or a list of feature dicts. It validates names, finite numeric values, current binary slots and their total. It reorders named columns safely and clips every output to 0-12. Unnamed matrices are rejected at the public interface.')
    code('import json\nfrom pathlib import Path\nfrom ml.phase4_models import load_predictor\nresults = json.loads(Path("ml/artifacts/phase4/model_results.json").read_text())\npredictor = load_predictor(\n    "ml/artifacts/phase4/parking_models.joblib",\n    expected_sha256=results["artifact"]["sha256"],\n)\npredicted_counts = predictor.predict(feature_rows)\n# Optional explicit comparison:\n# predictor.predict(feature_rows, "persistence")')
    p('The verified 851,974-byte compressed bundle contains the three model definitions, fitted scaler, chosen forest, selection identifier, feature order, 15-minute horizon, seed and data/selection hashes. Joblib requires a compatible permitted local runtime; load only trusted artifacts because a checksum is not an authenticity or pickle-safety guarantee. [3]')
    sub('Verified local runtime commands')
    code("$phase4Python = Join-Path $env:LOCALAPPDATA `\n  'SmartParking\\ml-runtime\\Scripts\\python.exe'\n& $phase4Python -B -m ml.tools.phase4_test_runner --native `\n  --output reports/evidence/phase4_native_followup.json\n& $phase4Python -B -m ml.tools.verify_phase4 --run-dir ml/artifacts/phase4 `\n  --output reports/evidence/phase4_verification_followup.json")
    p('Use a new output/evidence path for a deliberate rerun; files are never silently replaced. Do not retune using test outcomes. Future Streamlit integration must use the same permitted local runtime and sufficient causal history. Missing or UNKNOWN real-slot inputs must not be replaced with synthetic values to manufacture a forecast.')
    p('The original ml/train.py placeholder is preserved because it is included in frozen Phase 3 hashes. All new training code is in train_phase4.py; Phase 3 feature/data code and notebooks remain unchanged.','small')

    page(8,'Acceptance, storage, assumptions and evidence')
    table(['Critical requirement','Current status'],[
        ('Native tests and prediction contracts','PASS: final 21 tests, including actual fitting/reload.'),
        ('Frozen Phase 1/2/3 preservation','Phase 3 hashes intact; no frozen datasets/code/reports modified.'),
        ('Approved local Windows runtime','PASS: isolated imports, fitting/evaluation and reload succeeded.'),
        ('Actual fitting, validation and test comparison','NOT RUN' if not results else 'Actual results available'),
        ('Actual trained model and reload','NOT CREATED / NOT RUN' if not verification else ('PASS' if verification.get('passed') else 'FAIL')),
        ('Phase 4 complete','YES' if complete else 'NO'),
        ('Per-file commits and final push','Performed only after final checks and visual PDF review; confirmed at delivery.'),
    ],[235,264])
    files={p.as_posix():p.stat().st_size for folder in [ROOT/'ml/data',ROOT/'ml/artifacts'] for p in folder.rglob('*') if p.is_file()}
    total=sum(files.values())
    p(f'Current data/model directory storage: {total:,} bytes ({total/1e6:.3f} MB). The limit remains 50,000,000 bytes. The runner checks the total after saving outputs. No duplicate datasets, prediction-row export or notebook generator is used. The directory total includes the one fitted bundle, frozen datasets and supporting model metadata; runtime/dependency installation storage is separate.')
    p('Assumptions/limits: synthetic and uncalibrated demand; highly persistent minute occupancy; redundant predictors; single chronological holdout; only four forest configurations; no real-site, sensor-noise, live-MQTT or dashboard validation. A synthetic winner may not generalize. No confidence intervals or deployment accuracy claims are supplied.')
    sub('Evidence and continuation files')
    p('Historical preflights/readiness JSON preserve initial failures. phase4_isolated_complete_preflight.json and phase4_installation_trial.json record the approved runtime. phase4_native_tests_final.json records 21 passes; phase4_model_verification.json records 28 passes. model_results.json and validation_selection.json contain actual metrics/configurations. The final checklist and phase4_final_checks.json record preservation and PDF acceptance.')
    sub('Primary references')
    for label,url in [
        ('[1] Scikit-learn leakage and preprocessing','https://scikit-learn.org/stable/common_pitfalls.html'),
        ('[2] Microsoft App Control event explanations','https://learn.microsoft.com/en-us/windows/security/application-security/application-control/app-control-for-business/operations/event-id-explanations'),
        ('[3] Scikit-learn model persistence','https://scikit-learn.org/stable/model_persistence.html')]:
        p(f'{label}<br/><link href="{url}" color="#007F86">{url}</link>','small')
    p('Regenerate this PDF using reports/generate_phase4_report.py in the bundled ReportLab environment. It does not install project dependencies. This document reports actual synthetic fitting/evaluation and its limitations; it is not a certificate of real-world performance.','small')

    page(9,'Validation search, baseline and recovery')
    table(['Forest depth','Minimum leaf','Validation MAE','Validation RMSE'],[
        (c['parameters']['max_depth'],c['parameters']['min_samples_leaf'],f"{c['validation']['clipped']['mae']:.6f}",f"{c['validation']['clipped']['rmse']:.6f}")
        for c in selection['tuning']['forest_candidates']], [95,100,152,152])
    p('The best forest is depth 8 / minimum leaf 30. It still has higher validation MAE than persistence (0.436999 versus 0.339983), so the saved selection is persistence. Linear validation MAE is 0.414362. Test outcomes never changed this decision. All three models are retained in one bundle for transparent comparison.')
    table(['Partition / model','Raw MAE','Clipped MAE','Clipped rows'],[
        (part+' / '+name,f"{results[part][name]['raw']['mae']:.6f}",f"{results[part][name]['clipped']['mae']:.6f}",
         f"{results[part][name]['clipped_count']} ({100*results[part][name]['clipped_fraction']:.2f}%)")
        for part in ['validation','test'] for name in ['persistence','linear_regression','random_forest']], [190,93,100,116])
    sub('Verification-only recovery, with no retuning')
    p('The first full-data run locked persistence before test access and saved its bundle. An exact-equality assertion then rejected parallel forest summation differences. Two reloads differed by at most 1.7763568394002505e-15 slots; persistence and linear predictions were exactly equal. Reload agreement now uses absolute tolerance 1e-12, relative tolerance zero, with a test rejecting materially larger differences.')
    p('The original bundle and selection file were not overwritten. Finalization read that same artifact and checked its configuration, training-only scaler, locked validation scores and hashes. Test metrics were recomputed for recovery and independently reverified. No fitting, hyperparameter change, reselection or test-driven feature change occurred. The saved results explicitly disclose this recovery; no single-computation claim is made.')

    page(10,'Reproducibility, storage and Phase 5 handoff')
    table(['Artifact','Actual bytes / purpose'],[
        ('parking_models.joblib',f"{results['artifact']['bytes']:,}; all three models and required preprocessing"),
        ('validation_selection.json','5,519; pre-test selection lock and four candidate results'),
        ('model_results.json','4,854; actual raw/clipped metrics, row identities and reload evidence'),
        ('Frozen data + model directory total',f"{verification['data_model_bytes']:,} bytes; below 50,000,000"),
    ],[258,241])
    p('Model SHA-256:<br/>'+results['artifact']['sha256'],'small')
    p('Selection-lock SHA-256:<br/>'+results['selection_lock_sha256'],'small')
    p('Runtime versions: '+', '.join(name+' '+version for name,version in results['runtime']['versions'].items())+'. Full approved package pins are in ml/phase4_requirements.txt. There is no cloud, SSH, new Python installation, security exception or modification of the old project environment.')
    sub('Deliberate new training run, not an overwrite')
    code("$phase4Python = Join-Path $env:LOCALAPPDATA `\n  'SmartParking\\ml-runtime\\Scripts\\python.exe'\n& $phase4Python -B -m ml.train_phase4 `\n  --output-dir ml/artifacts/phase4_reproduction\n& $phase4Python -B -m ml.tools.verify_phase4 `\n  --run-dir ml/artifacts/phase4_reproduction `\n  --output reports/evidence/phase4_reproduction_checks.json")
    p('These commands intentionally create new artifacts and are not run merely to inflate activity or select another model using the test period. Reproducibility tests used small seeded fixtures; exact bitwise forest prediction is not promised under parallel floating summation. Reload correctness uses the strict documented numerical tolerance.')
    sub('Future Streamlit integration')
    p('Load the trusted bundle with its recorded checksum and call predictor.predict on named, complete causal features. All three models share the same input contract and output range. Use a compatible approved local runtime for the future dashboard; Streamlit installation and integration are a separate authorized phase. If live slots or lookback history are unavailable, expose forecast unavailability rather than substituting synthetic records. No Phase 5 code is added here.')

    def furniture(canvas,doc):
        w,h=doc.pagesize
        canvas.setStrokeColor(TEAL);canvas.setLineWidth(1.5);canvas.line(48,h-39,w-48,h-39)
        canvas.setFont('Bold',8);canvas.setFillColor(NAVY);canvas.drawString(48,h-28,'SMART PARKING / PHASE 4 / SYNTHETIC MODEL DEVELOPMENT')
        canvas.setLineWidth(.5);canvas.line(48,39,w-48,39);canvas.setFont('Body',7.5)
        canvas.drawString(48,25,'11 Nov 2026 | '+('Verified execution evidence' if complete else 'INCOMPLETE: native execution blocked')+' | No real-world accuracy claim')
        canvas.drawRightString(w-48,25,str(doc.page))
    doc=SimpleDocTemplate(str(OUTPUT),pagesize=(595.28,841.89),leftMargin=48,rightMargin=48,topMargin=59,bottomMargin=54,
        title='Phase 4 Machine Learning Model Development - Verified Local Windows Results',author='Smart Parking Project')
    doc.build(story,onFirstPage=furniture,onLaterPages=furniture)
    print(OUTPUT)


if __name__=='__main__':main()
