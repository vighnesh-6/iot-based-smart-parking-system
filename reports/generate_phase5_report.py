"""Evidence-led Phase 5 PDF; never runs telemetry, training or cloud deployment."""
import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
NAVY, TEAL, PALE = (colors.HexColor(v) for v in ('#15364b', '#007f86', '#edf5f7'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, default=ROOT/'reports/evidence/phase5_dashboard_verification.json')
    parser.add_argument('--output', type=Path, default=ROOT/'reports/phase5_streamlit_dashboard.pdf')
    args = parser.parse_args()
    if args.output.exists(): parser.error('Choose a new output path; existing PDFs are never overwritten')
    evidence = json.loads(args.evidence.read_text(encoding='utf-8'))
    results = json.loads((ROOT/'ml/artifacts/phase4/model_results.json').read_text(encoding='utf-8'))
    if not evidence['local_functional_passed']:
        raise RuntimeError('Local verification must pass before a completion report is produced')
    fonts = Path('C:/Windows/Fonts')
    if fonts.exists():
        for name, filename in [('Body', 'arial.ttf'), ('Bold', 'arialbd.ttf'), ('Mono', 'consola.ttf')]:
            pdfmetrics.registerFont(TTFont(name, str(fonts/filename)))
        pdfmetrics.registerFontFamily('Body', normal='Body', bold='Bold', italic='Body', boldItalic='Bold')
        body, bold, mono = 'Body', 'Bold', 'Mono'
    else:
        body, bold, mono = 'Helvetica', 'Helvetica-Bold', 'Courier'
    styles = {
        'body': ParagraphStyle('body', fontName=body, fontSize=9.4, leading=13.3, spaceAfter=8, textColor=NAVY),
        'title': ParagraphStyle('title', fontName=bold, fontSize=27, leading=32, spaceAfter=17, textColor=NAVY),
        'heading': ParagraphStyle('heading', fontName=bold, fontSize=19, leading=24, spaceAfter=13, textColor=NAVY),
        'sub': ParagraphStyle('sub', fontName=bold, fontSize=11, leading=15, spaceBefore=7, spaceAfter=7, textColor=TEAL),
        'small': ParagraphStyle('small', fontName=body, fontSize=8, leading=11, spaceAfter=8, textColor=NAVY),
        'cell': ParagraphStyle('cell', fontName=body, fontSize=8.2, leading=11, textColor=NAVY),
        'head': ParagraphStyle('head', fontName=bold, fontSize=8.2, leading=11, textColor=colors.white),
        'code': ParagraphStyle('code', fontName=mono, fontSize=7.4, leading=10.3, spaceAfter=9, textColor=NAVY),
    }
    story = []
    def p(text, style='body'): story.append(Paragraph(text, styles[style]))
    def sub(text): p(text, 'sub')
    def page(number, title):
        if story: story.append(PageBreak())
        p(f'PHASE 5 / STREAMLIT DASHBOARD / {number:02d}', 'small')
        p(title, 'heading')
    def code(text): story.append(Preformatted(text, styles['code']))
    def table(headers, rows, widths):
        data = [[Paragraph(escape(str(v)), styles['head']) for v in headers]]
        data += [[Paragraph(escape(str(v)), styles['cell']) for v in row] for row in rows]
        item = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
        item.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), NAVY),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, PALE]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8), ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7), ('LINEBELOW', (0, -1), (-1, -1), .5, colors.HexColor('#cad9df'))]))
        story.append(item); story.append(Spacer(1, 11))

    page(1, 'Local-first, cloud-ready operations')
    p('Smart Parking<br/>Streamlit Dashboard', 'title')
    p('Implementation, actual verification and deployment continuation', 'sub')
    p('11 November 2026 | Twelve slots P1-P12 | Three ESP32 boards | Phase 5 local delivery', 'small')
    p('The dashboard presents existing FastAPI telemetry, honest freshness and availability, a modular 15-minute prediction interface, historical coverage and frozen model comparisons. The same frontend supports configurable hosting and in-process execution without embedding a laptop path.')
    table(['Acceptance area', 'Actual result'], [
        ['Local dashboard verification', f"PASS: {evidence['test_total']} tests across dashboard, backend and ML; AppTest plus local HTTP."],
        ['Live data at verification', '12 effective UNKNOWN; P1-P8 unseen, P9-P12 stale. No production live forecast claimed.'],
        ['Model execution', 'Both adapters verified with the saved bundle. Separate synthetic retrospective example executed.'],
        ['Cloud deployment', 'NOT PERFORMED. Hosting, durable infrastructure, network security and native Linux compatibility remain Phase 6 work.'],
    ], [153, 357])
    p('Evidence source: reports/evidence/phase5_dashboard_verification.json. Earlier sandbox/environment-check failures are retained and explained; they are not promoted into successful test results.', 'small')

    page(2, 'Architecture and preservation boundaries')
    code('ESP32 (3 x 4 slots) -> Mosquitto -> unchanged FastAPI + SQLite\n'
         '                                      | HTTP GET\n'
         '                                      v\n'
         '                      Streamlit / configurable API_BASE_URL\n'
         '                         |                  |\n'
         '                 causal API history    frozen score JSON\n'
         '                         |\n'
         '                 prediction interface\n'
         '                   /              \\\n'
         '              in-process       configured subprocess\n'
         '                   \\              /\n'
         '              frozen Phase 4 load_predictor().predict()')
    p('The frontend does not connect to SQLite or MQTT. API calls are GET-only and originate from API_BASE_URL. Existing backend statistics and response models are reused as pure helpers; no backend file or database schema is changed.')
    p('The local subprocess adapter is a configuration option for this Windows laptop. Its Python path is supplied through ML_PYTHON. Cloud-compatible in-process mode calls exactly the same frozen predictor. No model formula or feature logic is duplicated.')
    table(['Boundary', 'Preservation rule'], [
        ['Phase 1/2', 'Firmware, circuits, MQTT topics, broker settings and backend implementation remain unchanged.'],
        ['Phase 3/4', 'Datasets, feature/training source, eight executed notebooks, model bundle, results and PDFs remain byte-identical.'],
        ['Runtime/data', 'No dependencies installed or removed. No live database writes, resets or telemetry injections.'],
        ['Hosting', 'No cloud account, deployment, database migration or public network change performed.'],
    ], [110, 400])

    page(3, 'Implementation and configuration')
    table(['File / component', 'Responsibility'], [
        ['dashboard/app.py', 'Three-tab UI, 12 cards, counts, diagnostics, refresh, history and synthetic review.'],
        ['dashboard/config.py + example TOML', 'Environment-first portable settings, endpoint validation and repository-relative artifacts.'],
        ['dashboard/api_client.py', 'GET-only JSON, timeouts, optional gateway bearer header and bounded stable pagination.'],
        ['dashboard/data_views.py', 'Validated snapshot, conservative freshness, minute reconstruction and frozen feature reuse.'],
        ['dashboard/prediction.py', 'Shared prediction contract, checksum loading and both execution adapters.'],
        ['dashboard/tests + tools', 'Fixture tests, actual AppTest interactions, HTTP observation and evidence collection.'],
        ['dashboard/README.md + requirements', 'Local commands, configuration and separate deployment responsibilities.'],
    ], [181, 329])
    p('Key settings: API_BASE_URL; optional API_BEARER_TOKEN; PREDICTION_ADAPTER; ML_PYTHON for subprocess only; API_TIMEOUT_SECONDS; REFRESH_SECONDS; DASHBOARD_STALE_SECONDS; HISTORY_MAX_ROWS; artifact/manifest path overrides. DASHBOARD_CONFIG selects an optional TOML file; environment variables win.')
    p('Defaults: localhost:8000, in_process, 3-second HTTP timeout, 10-second refresh, 30-second conservative receipt ceiling and 20,000 history rows. Supported refresh choices are 5/10/15/30/60 seconds. No private .env is silently loaded or modified.')
    p('Secrets belong in environment variables or private hosting secrets. URLs reject embedded credentials. The optional bearer value is sent only as a header and excluded from settings repr. The current backend does not authenticate it; a future secured gateway must enforce authorization.')

    page(4, 'Twelve-slot UI and freshness semantics')
    p('The Live operations tab groups P1-P4, P5-P8 and P9-P12 by ESP32. Text accompanies colour so availability is not encoded by colour alone. Each observed card identifies receipt time, age and last-reported state/distance. Stale last-known VACANT never implies a usable space.')
    table(['Condition', 'Effective presentation'], [
        ['Fresh observed OCCUPIED / VACANT', 'Known state, provided receipt age and backend stale flags allow it.'],
        ['Fresh sensor UNKNOWN', 'Unknown; no distance is invented.'],
        ['Never observed / missing receipt', 'Unknown, with an explicit unseen explanation.'],
        ['Backend stale / local age exceeded', 'Unknown. Last report remains diagnostic only.'],
        ['Receipt ahead by more than 2 seconds', 'Unknown with a receipt-clock explanation.'],
        ['API failure or malformed snapshot', 'No fresh headline counts or forecast; all 12 cards show API unavailable.'],
    ], [202, 308])
    p('Counts use the frozen backend statistics helper on the same validated snapshot as the cards. The sum of occupied, vacant and unknown is 12. Stale and unseen diagnostics overlap, so they are not added together as separate capacity categories.')
    p('Automatic refresh uses Streamlit fragments and is active only with a connected session. A toggle and manual refresh are provided. Loading spinners, API timeouts and explicit errors replace silent failures. /health and /stats are separate diagnostic GETs, not an atomic combined snapshot.')
    p('MQTT connected/subscribed means transport readiness. It does not establish that all boards are publishing or that valid sensor readings arrived. Current ingestion counters are process-local and may be zero while SQLite retains older observations.')

    page(5, 'History reconstruction and causal features')
    p('Telemetry history is loaded on demand for one hour, 24 hours or seven days, optionally filtered by slot. All filters use backend reception time with timezone-aware bounds. The upper bound is fixed throughout pagination to prevent new arrivals shifting offsets.')
    p('Pages contain at most 1,000 observations. A configured row cap and 20-second paging budget bound work; an in-flight request can add its timeout. Changed page totals, malformed metadata and incomplete pages are rejected. Capped output is explicitly partial and cannot enable a forecast.')
    p('At each minute origin, a backward as-of join selects the latest accepted-current observation received by that minute, separately for each slot. The receipt-age tolerance applies. History-only, UNKNOWN, absent and expired values do not become known occupancy. No future observation, interpolation or backward fill is used.')
    table(['Calculation', 'Definition'], [
        ['Complete occupancy total', 'Sum of P1-P12 only when every slot is known; otherwise a gap.'],
        ['Coverage trace', 'Number of known slots, 0-12. It is not an occupancy estimate.'],
        ['Arrival / departure features', 'Signed differences between consecutive complete minute slot states.'],
        ['Feature pipeline', 'Reuse ml.features.engineer_features, including calendar cycles, lags, shift(1) rolling mean/std and occupancy change.'],
        ['Availability gate', 'Fresh current twelve-slot snapshot plus at least 10,081 complete minute rows.'],
    ], [157, 353])
    p('Calendar values use Asia/Kolkata, matching the frozen training data. Seven-day lag and past-only rolling features require real available history. A complete origin is a receipt-time reconstruction, not proof of synchronized device measurement or sensor accuracy.')
    p('High-frequency week-long history can exceed the default cap. Configure capacity only after measuring latency and memory. This phase deliberately makes no backend rollup, schema or retention change; insufficient coverage keeps the forecast unavailable.')

    page(6, 'Prediction interface and model comparison')
    p('predict(features, settings) isolates UI rendering from execution. In-process mode loads the trusted bundle in the current compatible runtime. Subprocess mode sends JSON to the configured interpreter with an argument list, no shell and a 30-second timeout. The worker calls the same Phase 4 loader/predictor.')
    p('The bundle checksum is verified; all 37 feature names and numeric inputs are validated by the frozen interface. Cached loading is keyed by path/hash. Outputs must align with input row count, identify Persistence, report horizon 15 and stay finite in [0,12]. No integer rounding, refitting or reselection occurs.')
    p('The displayed target is exactly the shown minute origin plus 15 minutes. Live forecast computation is withheld for unknown current states, incomplete history, truncation or model/runtime errors. The synthetic example instead reads one frozen validation row, verifies dataset hashes and runs the actual configured adapter; both predicted and actual future totals are explicitly synthetic.')
    rows = []
    for split in ('validation', 'test'):
        for name in ('persistence', 'linear_regression', 'random_forest'):
            score = results[split][name]['clipped']
            rows.append([split.title(), name.replace('_', ' '), f"{score['mae']:.6f}", f"{score['rmse']:.6f}", f"{score['r2']:.6f}"])
    table(['Partition', 'Model', 'MAE', 'RMSE', 'R2'], rows, [79, 151, 94, 94, 92])
    p('MAE = mean absolute error; RMSE = square root of mean squared error; R2 = 1 - residual sum of squares / target sum of squares. Persistence won the predeclared validation-MAE criterion. Better Linear Regression RMSE does not change that rule. All scores are frozen synthetic evaluation, not real-world accuracy.', 'small')

    page(7, 'Local commands and reproducibility')
    sub('Start only the dashboard; keep the existing backend instance')
    code("$env:API_BASE_URL = 'http://127.0.0.1:8000'\n"
         "$env:PREDICTION_ADAPTER = 'subprocess'\n"
         '$env:ML_PYTHON = "$env:LOCALAPPDATA/SmartParking/ml-runtime/Scripts/python.exe"\n'
         "$env:PYTHONDONTWRITEBYTECODE = '1'\n"
         '.\\.venv\\Scripts\\python.exe -B -m streamlit run dashboard/app.py `\n'
         '  --server.address 127.0.0.1 --server.port 8501 --server.headless true `\n'
         '  --browser.gatherUsageStats false')
    p('The Windows interpreter path is an operator example, not an application dependency. In a compatible single environment, use PREDICTION_ADAPTER=in_process and omit ML_PYTHON. No package installation into either existing environment was performed.')
    sub('Verify using a new evidence filename')
    code('$env:PHASE5_TEST_ML_PYTHON = $env:ML_PYTHON\n'
         '.\\.venv\\Scripts\\python.exe -B -m unittest discover -s dashboard/tests -v\n'
         '.\\.venv\\Scripts\\python.exe -B -m dashboard.tools.verify_local `\n'
         '  --ml-python $env:ML_PYTHON --output tmp/phase5_followup.json')
    p('The verifier captures actual dashboard/backend/ML suites, API GETs, local HTTP service status, AppTest interactions, dependency inventories and optional protected hashes. Existing evidence paths are refused. Tests create only their own fixtures and private temporary databases.')
    sub('Generate a new PDF without replacing this release')
    code('python reports/generate_phase5_report.py `\n'
         '  --evidence reports/evidence/phase5_dashboard_verification.json `\n'
         '  --output tmp/phase5_report_followup.pdf')
    p('Use approved ReportLab tooling; bundled tooling was used for this release. Render every page with Poppler and visually inspect it. Existing Phase 1-4 PDFs are never regenerated or overwritten.')

    page(8, 'Actual test evidence and observed limitations')
    table(['Verification', 'Actual result'], [
        [name.title() + ' suite', f"{suite['tests_run']} tests; {'PASS' if suite['passed'] else 'FAIL'}; exit {suite['exit_code']}"]
        for name, suite in evidence['suites'].items()
    ] + [
        ['HTTP server', '200 for / and /_stcore/health on local port 8501.'],
        ['Actual API / AppTest', '12 cards; occupied 0, vacant 0, unknown 12. History chart rendered; no complete twelve-slot total available.'],
        ['Synthetic retrospective', 'Actual saved-model execution succeeded; predicted 0.00 and actual future 0 for the selected frozen validation row.'],
        ['Both execution adapters', 'Native in-process and Windows subprocess returned identical example results.'],
        ['Live forecast complete-history path', 'PASS with explicit test fixtures and the actual saved model; NOT verified with production history.'],
        ['Browser timing / cloud', 'Not independently observed / not deployed.'],
    ], [159, 351])
    p('The production API exposed only five stored messages (twenty slot observations) from ESP32-03. The current backend reported connected/subscribed with received=0/stored=0. P1-P8 were unseen; P9-P12 were stale. A live prediction was correctly withheld. This is not an MQTT runtime pass.')
    p('An initial 28-test run had one sandbox temporary-directory permission error. A later 116-test run passed all suites but its acceptance check rejected an exact freeze comparison. Extra Jupyter packages were found to predate Phase 5 (metadata creation around 17:29 IST; phase snapshot 18:39 IST). No packages were removed or changed. Final acceptance checks preserve the frozen pins, record the extras and compare the isolated ML environment exactly.')
    p('Final evidence contains the actual failed-run records as well as the successful final run. AppTest is automated UI evidence; it is not a browser screenshot or independently measured wall-clock refresh demonstration.', 'small')

    page(9, 'Phase 6: frontend and API deployment')
    sub('Streamlit Community Cloud frontend')
    p('Select the intended repository/branch and dashboard/app.py entrypoint. The entrypoint-adjacent dashboard/requirements.txt reuses the frozen ML pins and declares UI dependencies. Use compatible Python 3.12 and test official native wheels on the chosen host before claiming compatibility. Community Cloud package installation and deployment are not performed in Phase 5.')
    p('Set root-level private Secrets/environment values: API_BASE_URL to the hosted HTTPS API; PREDICTION_ADAPTER=in_process; optional API_BEARER_TOKEN for the secured gateway. Omit Windows ML_PYTHON. Repository-relative artifacts remain packaged with the same app. Never commit secrets or use the frontend filesystem as the live database.')
    sub('Cloud-hosted FastAPI backend')
    p('Deploy separately behind a secured HTTPS reverse proxy/API gateway. The current frozen API is designed for trusted local use and lacks built-in public authentication/TLS. Enforce authorization at the gateway before exposure; the existing frontend can supply a configured bearer header. Review rate limits, request timeouts, health monitoring, logs and restart behavior. Keep one worker per existing MQTT client/database owner.')
    p('Cloud localhost refers to that cloud host, not this laptop. The Streamlit service must have network access to the hosted API. The frontend makes server-side Python requests, so browser CORS is not required for its existing calls. Hosting/security setup is separate from frontend rendering; no existing backend code is changed here.')
    sub('What remains to prove')
    p('Successful Community Cloud build; correct dependency-file selection; compatible native imports and bundle reload; authenticated HTTPS API reachability; secrets handling; browser rendering; measured refresh behavior; operational latency/memory and outage recovery. The same frontend should be deployed through configuration and hosting changes, but those claims need actual Phase 6 execution.')

    page(10, 'Phase 6: database, MQTT and ML hosting')
    sub('Persistent backend-owned SQLite')
    p('Configure an absolute DATABASE_PATH on a durable backend volume, outside the checkout and synchronized directories. Set it explicitly on Linux rather than relying on Windows LOCALAPPDATA. Preserve recognized schema, delete-journal mode and single-writer assumptions. Establish retention, backups, restore tests, disk monitoring and ownership. No live SQLite file belongs in Git or the Streamlit frontend. Database-engine changes or migrations require separate approval.')
    sub('MQTT broker and device connectivity')
    p('Provision broker reachability, credentials/access control, encrypted transport, firewall rules, persistence/session policy and monitoring. Preserve all production topics and JSON compatibility. host.wokwi.internal is the private-gateway alias for the local development PC, not a public cloud broker hostname. Any deployment-specific hostname/transport changes need their own approved configuration and all-device verification. Existing firmware and Mosquitto settings remain untouched.')
    sub('Cloud-compatible model execution')
    p('Use the same in-process adapter with approved compatible pinned dependencies and the trusted saved bundle. Verify artifact/selection hashes and compare reloaded predictions against reference rows before use. No retraining is required or performed. The UI still needs valid causal API history, uses identical features and clips outputs through the frozen interface. Plan memory, latency and bounded history access; no data-source relabelling or synthetic fallback is allowed.')
    sub('Troubleshooting without destructive changes')
    p('API unavailable: inspect URL, network and health; do not restart services automatically or infer vacancy. Model worker failed: inspect the approved interpreter and trusted artifact configuration locally; never weaken Application Control. Forecast unavailable: inspect current freshness, seven-day completeness and fetch caps. History gaps: reception filters and receipt-age tolerance can differ from device time. Cloud import failure: obtain a compatible approved runtime and verify it; do not silently alter frozen model versions.')

    page(11, 'Acceptance and continuation record')
    table(['Requirement', 'Status / evidence'], [
        ['Twelve slots, counts and freshness', 'PASS: fixture tests and actual API/AppTest; stale/unseen never count as vacant.'],
        ['API-only live access and errors', 'PASS: configured URL, GET-only client, bounded paging, loading/error UI and no direct live DB access.'],
        ['Modular ML execution', 'PASS: both adapters call the same frozen loader/predictor; actual reload/predictions agree.'],
        ['Causal history / live gating', 'PASS: as-of, gap, transition, pipeline and forecast fixture checks; production forecast unavailable.'],
        ['Historical trends and model metrics', 'PASS: chart/filter tests, actual history extraction and six frozen score sets.'],
        ['Refresh controls', 'PASS: interval registration, disable and manual reruns in AppTest; browser timing unverified.'],
        ['Frozen artifacts / dependencies', 'PASS: protected hashes and original pins preserved; pre-existing Jupyter extras explicitly recorded.'],
        ['New comprehensive PDF', 'Generated from actual evidence; final rendering and visual inspection recorded separately.'],
        ['Cloud deployment', 'PENDING PHASE 6; no hosting or network changes performed.'],
    ], [174, 336])
    p('Implementation acceptance is limited to verified local functionality. Production telemetry completeness, live-history forecasting, actual browser refresh timing and cloud deployment are not promoted into passes. This distinction is part of the acceptance, not a synthetic-data substitute.')
    p('After visual review, complete all local checks, create one meaningful changed-file commit at a time, push once, then verify remote HEAD and a clean Git status. Commit/push verification is reported at delivery rather than invented inside a report generated beforehand.')
    sub('Official references and continuation files')
    for title, url in [
        ('Streamlit fragments', 'https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment'),
        ('Streamlit AppTest', 'https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest'),
        ('Community Cloud file organization', 'https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization'),
        ('Community Cloud dependencies', 'https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies'),
        ('Community Cloud secrets', 'https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management')]:
        p(f'<link href="{url}" color="#007f86">{title}</link>', 'small')
    p('Reviewed 11 November 2026. See dashboard/README.md, the Phase 5 acceptance checklist, evidence JSON and unchanged Phase 3/4 reports for reproducibility and limitations.', 'small')

    def footer(canvas, document):
        canvas.setStrokeColor(TEAL); canvas.setLineWidth(.7); canvas.line(42, 807, 552, 807)
        canvas.setFont(bold, 8); canvas.setFillColor(NAVY)
        canvas.drawString(42, 819, 'SMART PARKING / PHASE 5 / LOCAL VERIFICATION')
        canvas.setFont(body, 7.5)
        canvas.drawString(42, 25, '11 Nov 2026 | Synthetic evaluation labelled | Cloud deployment pending')
        canvas.drawRightString(552, 25, str(document.page))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(args.output), pagesize=(595, 842), leftMargin=42, rightMargin=43,
        topMargin=51, bottomMargin=43, title='Phase 5 - Smart Parking Streamlit Dashboard',
        author='Smart Parking Project', pageCompression=1).build(story, onFirstPage=footer, onLaterPages=footer)
    print(args.output, args.output.stat().st_size)


if __name__ == '__main__': main()
