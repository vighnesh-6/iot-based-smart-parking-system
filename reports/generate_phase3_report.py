"""Create the Phase 3 methodology PDF from actual dataset and test evidence."""

from collections import Counter
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak,Paragraph,Preformatted,SimpleDocTemplate,Spacer,Table,TableStyle

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'reports/phase3_historical_dataset_preparation.pdf'
NAVY,TEAL,PALE=(colors.HexColor(x) for x in ['#15364B','#007F86','#EDF5F7'])


def main():
    def read(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))
    manifest=read('ml/data/phase3_dataset_manifest.json')
    validation=read('reports/evidence/phase3_dataset_validation.json')
    tests=read('reports/evidence/phase3_tests.json')
    checks=validation['checks']
    patterns=checks['synthetic_daily_weekly_patterns']['evidence']
    transitions=checks['slot_arrivals_departures_and_dwell']['evidence']
    splits=checks['chronological_70_15_15_purged_boundaries']['evidence']
    sizes=checks['storage_below_50_MB']['evidence']
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
        'code':ParagraphStyle('code',fontName='Mono',fontSize=7.6,leading=10,spaceAfter=10,textColor=NAVY),
    }
    story=[]
    def p(text,style='body'):story.append(Paragraph(text,styles[style]))
    def sub(text):p(text,'sub')
    def code(text):story.append(Preformatted(text,styles['code']))
    def page(number,title):
        if story:story.append(PageBreak())
        p(f'PHASE 3 / HISTORICAL DATASET PREPARATION / {number:02d}','small')
        p(title,'heading')
    def table(headers,rows,widths):
        data=[[Paragraph(escape(str(v)),styles['header']) for v in headers]]
        data += [[Paragraph(escape(str(v)),styles['cell']) for v in row] for row in rows]
        item=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
        item.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('ROWBACKGROUNDS',(0,1),(-1,-1),[PALE,colors.white]),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
            ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        story.append(item);story.append(Spacer(1,8))

    page(1,'Historical dataset preparation')
    story.append(Spacer(1,14))
    p('Smart Parking System<br/>Eight-Week Synthetic History','title')
    p('Exactly twelve slots | One-minute observations | Fifteen-minute forecast','sub')
    p('Prepared 11 November 2026. This phase provides a reproducible offline historical dataset, causal features, target alignment and chronological evaluation partitions. Every observation is explicitly synthetic. No real-world forecast accuracy or Wokwi runtime success is claimed.')
    table(['Deliverable / check','Actual result'],[
        ('Raw history',f"{manifest['raw_rows']:,} rows: 14 September through 8 November 2026, Asia/Kolkata (IST)."),
        ('ML-ready observations',f"{manifest['processed_rows']:,} rows; {len(manifest['features'])} numeric predictors; target and provenance stored separately."),
        ('Final data acceptance',f"{len(checks)} critical checks; overall PASS={validation['critical_passed']}."),
        ('Software tests',f"{tests['tests_run']} tests; passed={tests['passed']}, failures={tests['failures']}, errors={tests['errors']}, skipped={tests['skipped']}."),
        ('Data / model storage',f"{sizes['total_bytes']:,} bytes ({sizes['total_bytes']/1e6:.3f} MB); limit 50,000,000 bytes. No model artifact."),
    ],[151,348])
    p('The preferred Parquet format could not be used: Windows Application Control blocks the existing PyArrow native DLL. The verified processed artifact is deterministic gzip-compressed CSV. Security policy, dependencies and frozen Phase 1/2 implementation were preserved.')
    p('Scope ends at validated ML-ready data. No model training, prediction endpoint, live-data ingestion change, Streamlit integration or notebook generator is included. The existing four notebooks remain title-only.','small')

    page(2,'Architecture, provenance and memory budget')
    table(['Stage','Input -> output / responsibility'],[
        ('Seeded simulator','Fixed calendar + seed 42 + twelve-slot state machine -> raw CSV.'),
        ('Strict raw reader','Timezone normalization and value checks before narrowing to uint8. Invalid input fails rather than being silently repaired.'),
        ('Causal feature engineering','Current observations + past-only lags/windows + known calendar -> numeric features.'),
        ('Target and partitioning','Exact t+15 label -> warmup/tail removal -> two purge gaps -> 70/15/15 chronological groups.'),
        ('Compact storage','One processed CSV.gz plus schema/provenance manifest. Splits are labels, not duplicate files.'),
        ('Independent validation','Full-artifact arithmetic, transitions, target timestamps, causality interventions, reproducibility and storage checks -> JSON/checklist/PDF.'),
    ],[150,349])
    sub('Separation from real observations')
    p('data_source is synthetic in every raw and processed record. The generator has no MQTT or SQLite dependency and does not read, merge, replace or append live Wokwi observations. Live slot status remains the responsibility of the frozen backend. Synthetic data does not repair or conceal the outstanding simulator connectivity issue.')
    sub('Lightweight representation')
    p('A wide minute row stores P1-P12 once, avoiding twelve repeated timestamp/source values per minute. State and counts use uint8; engineered fractional features use float32; repeated labels are categorical on load. Raw CSV and processed gzip CSV are the only full representations. No model, train/validation/test copies, uncompressed processed export or generated EDA images are stored.')
    p(f"Measured DataFrame storage: raw {manifest['dataframe_bytes']['raw']:,} bytes; processed {manifest['dataframe_bytes']['processed']:,} bytes. These are table-memory measurements, not a peak-process-RAM benchmark. Temporary arrays used for tests are small and purposeful; reproducible compressed bytes are checked with a hashing sink rather than another dataset file.")

    page(3,'Synthetic arrival and departure methodology')
    p('The simulation runs for 56 continuous days. Each minute first removes vehicles whose sampled departure time has arrived, samples Poisson arrival demand, and fills available slots using preference weights from 1.15 (P1) to 0.85 (P12). Excess demand is discarded when capacity is exhausted. Just-departed slots are unavailable until the next minute so all arrivals/departures remain visible in sampled slot transitions.')
    code('G(h; mu, sigma) = exp(-0.5 * ((h-mu)/sigma)^2)\nweekday lambda(h) = 0.0015 + 0.055*G(h;8.8,1.25)\n                    + 0.025*G(h;13,1.8) + 0.015*G(h;17.5,1.5)\nweekend lambda(h) = 0.001 + 0.025*G(h;12.8,2.3)\n                    + 0.015*G(h;18,1.5)\narrivals_attempted(t) ~ Poisson(lambda(h)*daily_demand)\ndaily_demand ~ LogNormal(-0.5*0.18^2, 0.18)')
    p('Duration is drawn at arrival: lognormal sigma=0.5, with pre-clipping mean 300 minutes for weekday arrivals from 06:00 to before 11:00; 110 minutes for other weekday arrivals; 100 minutes on weekends. Values are rounded and clipped to 10-720 minutes. The latent scheduled departure is never exported as a feature. Slots start vacant at midnight and are never reset at day boundaries.')
    table(['Measured synthetic behavior','Value'],[
        ('Weekday business hours 09:00-16:59',f"{patterns['weekday_business_mean']:.4f} occupied slots on average"),
        ('Weekend same hours',f"{patterns['weekend_business_mean']:.4f} occupied slots on average"),
        ('Weekday night 00:00-04:59',f"{patterns['weekday_night_mean']:.4f} occupied slots on average"),
        ('Lag-one autocorrelation',f"{patterns['lag1_autocorrelation']:.6f}"),
        ('Completed stays / dwell',f"{transitions['completed_stays']}; min {transitions['dwell_min']}, median {transitions['dwell_median']}, max {transitions['dwell_max']} minutes"),
    ],[260,239])
    p('These checks demonstrate the intended synthetic patterns and persistence only. They are not empirical evidence that a particular real site follows these distributions. Boundary-censored stays are excluded from completed-dwell summaries, not discarded from state history.','small')

    page(4,'Raw and processed schema')
    table(['Raw column(s)','Meaning / type'],[
        ('timestamp','One local minute with explicit +0530 UTC offset; timezone-aware on load.'),
        ('data_source','Constant synthetic; categorical on load.'),
        ('P1-P12','Twelve uint8 values: 0 VACANT, 1 OCCUPIED. All twelve exist on every row.'),
        ('total_occupied','uint8 sum of the twelve states; always 0-12.'),
        ('arrivals / departures','uint8 counts of 0->1 and 1->0 transitions in that minute; each 0-12.'),
    ],[157,342])
    sub('Processed table: 42 columns')
    p('The processed table has timestamp and data_source, 37 allowlisted predictors, target_timestamp, occupied_15min_ahead and split. Target is uint8, range 0-12. Split is train, validation or test. Detailed per-column dtypes are recorded in phase3_dataset_manifest.json. Metadata and targets must not be passed to a model merely because a column is numeric.')
    sub('Cleaning and validation policy')
    p('Generated raw observations contain no missing values. Input validation rejects missing/nonbinary slots, invalid count ranges, duplicate or irregular timestamps and non-synthetic provenance. Numeric ranges are checked before uint8 conversion, preventing an invalid value such as 256 from wrapping into an apparently valid zero. Time is normalized to Asia/Kolkata; no DST discontinuities occur in this fixed interval.')
    p('No backward fill, interpolation or future-based imputation is performed. Initial lag/rolling gaps are expected and removed as a declared warmup. The final 15 origins have no future label and are excluded from ML-ready rows. Boundary purge rows remain in raw history and may supply causal past context.')
    sub('Storage format decision')
    p('Raw is ordinary UTF-8 CSV. Processed is CSV.gz with fixed gzip header mtime=0, empty embedded filename and stable numeric formatting. Nine significant digits preserve float32 values on round-trip. The loader restores dtypes/timezones from the manifest. A Zstandard Parquet code path exists, but Windows blocks PyArrow and that path is not runtime-verified here. No dependency installation or security bypass was attempted.')

    page(5,'Feature calculations and leakage prevention')
    table(['Predictor group','Calculation / information available at forecast origin t'],[
        ('Current state / counts: 15','P1-P12, their total, arrivals and departures observed at t.'),
        ('Calendar: 8','Hour, minute, weekday (Mon=0), weekend; daily sine/cosine using minute-of-day / 1440; weekday sine/cosine using weekday / 7.'),
        ('Lag: 7','total(t-k) for k=1,5,15,30,60,1440,10080 minutes.'),
        ('Trailing mean: 4','Mean of total(t-w) through total(t-1), w=5,15,60,1440.'),
        ('Trailing std: 2','Population standard deviation of the same past-only window, w=15,60; ddof=0.'),
        ('Change: 1','total(t)-total(t-15), with signed/floating arithmetic.'),
    ],[156,343])
    code('mean_w(t) = sum(total(i), i=t-w,...,t-1) / w\nstd_w(t) = sqrt(mean(total(i)^2) - mean_w(t)^2)\nlabel(t) = total(t+15 minutes)\nlabel_time(t) = timestamp(t+15 minutes)')
    p('All predictor values use observations at or before t or calendar facts known at t. For example, a five-minute mean at 09:00 uses 08:55-08:59. A weekly lag uses the same minute seven days earlier. Target_timestamp, target, split, source and raw timestamp are outside FEATURE_COLUMNS. Scheduled departure times and future simulation parameters are not predictors.')
    p('There are no fitted scalers, global occupancy aggregates, imputers, random splits or centered rolling windows. Any preprocessing added in a later model phase must be fitted on training data only. Availability of the current t observation is an explicit forecast-origin assumption; changing that deployment timing would require shifted features.')
    sub('Leakage tests actually executed')
    p('Every stored lag is checked against exact raw indices. All rolling values are independently checked using cumulative sums/squared sums, not just the feature function. Every calendar/current/change feature is verified. Future observations are altered while every past feature is compared; prefix-only feature computation must equal the same prefix computed with later rows present. Target alignment is checked for every processed row.')

    page(6,'Chronological 70/15/15 split and purges')
    code('Raw observations                      80,640\nRemove weekly-lag warmup              -10,080\nRemove targetless final 15 minutes        -15\nReserve two 15-minute boundary gaps       -30\nFinal usable forecast origins         70,515\nTrain = floor(0.70 * 70,515)           49,360\nValidation = floor(0.15 * 70,515)      10,577\nTest = remainder                      10,578')
    table(['Split','Rows / fraction','First / last origin (IST)','Last label time (IST)'],[
        (name,f"{info['rows']:,} / {100*info['fraction']:.5f}%",info['first'].replace('+05:30','')+' / '+info['last'].replace('+05:30',''),info['last_target'].replace('+05:30',''))
        for name,info in splits.items()], [65,115,195,124])
    p('Integer rounding accounts for the tiny deviation from 70%, 15%, 15%. There is no shuffling. Origins 25 October 06:40-06:54 and 1 November 15:12-15:26 are excluded. The last origin before each gap and first origin after it are 16 minutes apart.')
    p('The final training label is 25 October 06:54, strictly before validation starts at 06:55. The final validation label is 1 November 15:26, strictly before testing starts at 15:27. Thus neither preceding partition has a label whose outcome occurs at or after the next partition starts.')
    p('Validation/test lags may read earlier observed history from the previous partition or purge gap. This is causal context available at the later forecast origin, not leakage. No fitted transform sees held-out rows, and no model has yet been trained or tuned. The test period must remain untouched during future model selection.')
    p('Raw history still represents all eight weeks. The first seven days are retained as lookback context, even though no ML-ready origin is emitted during that warmup. Last raw timestamp is 8 November 23:59; last processed origin is 23:44, whose exact label is 23:59.')

    page(7,'Full-artifact acceptance checklist')
    table(['Critical verification','Result','Evidence scope'],[
        (name.replace('_',' '),item['status'],{
            'eight_weeks_one_minute':'All 80,640 raw timestamps',
            'all_twelve_slots':'P1-P12 columns and binary raw states',
            'synthetic_provenance':'Both complete tables',
            'missing_values_and_numeric_ranges':'All values, all predictor columns',
            'total_equals_slot_sum':'Every raw minute',
            'slot_arrivals_departures_and_dwell':'Every slot transition and completed stay',
            'synthetic_daily_weekly_patterns':'Business/weekend/night means and persistence',
            'exact_fifteen_minute_target':'All 70,515 future timestamps and labels',
            'current_features_match_observation':'Every current slot/count feature',
            'all_lags_are_past_only':'All seven lags at every origin',
            'all_rolling_windows_exclude_future':'Independent cumulative-sum oracle',
            'calendar_and_change_features':'All known-calendar and delta values',
            'future_intervention_and_prefix_invariance':'All 37 features; 10,181 prefix rows',
            'chronological_70_15_15_purged_boundaries':'Counts, ordered origins and separated labels',
            'schema_predictor_allowlist':'Exact schema and excluded metadata/targets',
            'fixed_seed_full_reproducibility':'Regenerate all 80,640 observations',
            'artifact_checksums':'Raw/processed SHA-256 match manifest',
            'storage_below_50_MB':'Data + model directories below 50 MB',
        }.get(name,'')) for name,item in checks.items()], [222,52,225])
    p('The machine-readable record is reports/evidence/phase3_dataset_validation.json; the human checklist is reports/phase3_acceptance_checklist.md. A failed critical check makes validation exit nonzero. Software execution, frozen-scope preservation and final document review are recorded separately in phase3_tests.json and phase3_final_checks.json.','small')

    page(8,'Software tests and slot-level transition evidence')
    groups=Counter(name.split('.')[1] for name in tests['test_ids'])
    table(['Suite','Tests','Coverage'],[(name,count,{'GenerationTests':'Calendar, twelve states, totals, transitions/dwell, seed behavior and provenance',
        'FeatureTests':'Each lag/window, causal prefix/future intervention, exact labels, partitions and invalid input',
        'SerializationTests':'CSV round-trip, overflow rejection, no overwrite, stored hashes and deterministic processed bytes'}[name]) for name,count in groups.items()], [140,45,314])
    p(f"Actual archived run: {tests['tests_run']} tests in {tests['seconds']} seconds; passed={tests['passed']}; {tests['failures']} failures, {tests['errors']} errors, {tests['skipped']} skips. Test IDs, runner output and source hashes are saved, rather than replaced by illustrative success text.")
    table(['Slot','Arrivals','Departures','Occupied fraction'],[(slot,d['arrivals'],d['departures'],f"{d['occupied_fraction']:.5f}") for slot,d in transitions['per_slot'].items()],[85,110,110,194])
    p('The full-seed regeneration content hash matches raw input and manifest. Recomputing all processed features and writing to a hashing sink yields the same gzip byte hash and size as the stored artifact, without a duplicate output file.')
    p('Initial Parquet preparation failed because Application Control blocked PyArrow; the empty new partial output was removed. The initial sandbox test attempt encountered temporary-directory access/cleanup restrictions. The permitted rerun passed all tests. Security controls and installed dependencies were not changed.','small')

    page(9,'Measured outputs and reproducibility commands')
    table(['Data/model file','Actual bytes'],[(path.replace('ml/data/',''),size) for path,size in sizes['files'].items()],[370,129])
    p(f"Total = {sizes['total_bytes']:,} bytes = {sizes['total_bytes']/1e6:.6f} MB = {sizes['total_bytes']/1048576:.3f} MiB. Limit is decimal 50 MB. No model files were created. Reports/test evidence are separate documentation artifacts, not duplicate datasets.")
    sub('Normal commands from repository root')
    code('.\\.venv\\Scripts\\python.exe -B -m ml.generate_data\n.\\.venv\\Scripts\\python.exe -B -m ml.prepare_data\n.\\.venv\\Scripts\\python.exe -B -m ml.validate_data\n.\\.venv\\Scripts\\python.exe -B -m unittest discover -s ml/tests -v')
    p('Commands refuse existing outputs. To reproduce without replacing the released artifacts, choose new paths:')
    code('.\\.venv\\Scripts\\python.exe -B -m ml.generate_data `\n  --output tmp/repro_raw.csv\n.\\.venv\\Scripts\\python.exe -B -m ml.prepare_data `\n  --raw tmp/repro_raw.csv --output tmp/repro_ml.csv.gz `\n  --metadata tmp/repro_manifest.json\n.\\.venv\\Scripts\\python.exe -B -m ml.validate_data `\n  --manifest tmp/repro_manifest.json --evidence tmp/repro_validation.json `\n  --checklist tmp/repro_checklist.md')
    sub('Content fingerprints and environment')
    for label,item in [('Raw',manifest['raw_file']),('Processed',manifest['processed_file'])]:
        p(f"<b>{label} SHA-256</b><br/>{item['sha256']}",'small')
    p('Recorded versions: '+', '.join(f'{k} {v}' for k,v in manifest['versions'].items())+'. Seed 42; fixed start date and timezone. Reproduce with these versions; generator changes can intentionally change data.','small')

    page(10,'Assumptions, limitations and continuation')
    table(['Assumption / limit','Practical implication'],[
        ('Synthetic, uncalibrated demand','Temporal plausibility is checked; real-site demand, generalization and forecast accuracy are not established.'),
        ('Perfect binary observation','No UNKNOWN states, sensor dropout, delayed MQTT, gateway failures or distance noise. Real-data preprocessing requires an explicit missingness/freshness policy.'),
        ('Fixed calendar and demand families','No holidays, weather, exceptional events, tariffs, reservations, special access or structural demand shifts.'),
        ('Capacity and arrivals','Twelve spaces only; excess demand is lost. No queue, user identifiers or travel behavior model.'),
        ('Current minute available','Feature timing assumes the t observation has arrived before issuing its t+15 forecast.'),
        ('One chronological holdout','No model training, hyperparameter search, cross-validation or real-world performance claim.'),
        ('Parquet policy restriction','Only gzip CSV was verified. Optional Parquet needs a permitted native Arrow environment; no bypass is proposed.'),
    ],[155,344])
    sub('Acceptance and preservation')
    p('Data acceptance requires every listed critical check to pass. Final phase acceptance additionally requires successful software tests, unchanged frozen Phase 1/2 files, preservation of live observations, a visually inspected PDF and the storage budget. Final verification evidence and the checklist record those outcomes before the one-file commits and single push.')
    p('Frozen ESP32/firmware/circuits, backend, database configuration, dependency snapshot, Phase 1/2 PDFs/evidence and existing notebooks are not edited. Only ML data-preparation implementation and new Phase 3 documentation/evidence are added; the shared reports index gains a Phase 3 reference.')
    sub('Next phase')
    p('Use FEATURE_COLUMNS as X and occupied_15min_ahead as y; select rows by split. Fit any learned preprocessing on training only, tune on validation, and evaluate the untouched test period once. Compare with persistence and seasonal baselines. Establish real-site validation before any operational accuracy or live forecast claim. No backend or Streamlit integration is part of this deliverable.')
    p('Reference files: ml/README.md; ml/generate_data.py; ml/features.py; ml/prepare_data.py; ml/validate_data.py; ml/tests/test_phase3.py; manifest; validation/test/final-check JSON files; acceptance checklist. This report is generated by reports/generate_phase3_report.py using the bundled ReportLab environment, leaving project dependencies unchanged.','small')

    def furniture(canvas,doc):
        width,height=doc.pagesize
        canvas.setStrokeColor(TEAL);canvas.setLineWidth(1.5);canvas.line(48,height-39,width-48,height-39)
        canvas.setFont('Bold',8);canvas.setFillColor(NAVY);canvas.drawString(48,height-28,'SMART PARKING / PHASE 3 / SYNTHETIC DATA ONLY')
        canvas.setLineWidth(.5);canvas.line(48,39,width-48,39);canvas.setFont('Body',7.5)
        canvas.drawString(48,25,'11 Nov 2026 | Reproducible history and causal features | No real-world accuracy claim')
        canvas.drawRightString(width-48,25,str(doc.page))
    doc=SimpleDocTemplate(str(OUTPUT),pagesize=(595.28,841.89),leftMargin=48,rightMargin=48,topMargin=59,bottomMargin=54,
                          title='Phase 3 Historical Dataset Preparation - Smart Parking',author='Smart Parking Project')
    doc.build(story,onFirstPage=furniture,onLaterPages=furniture)
    print(OUTPUT)


if __name__=='__main__':main()
