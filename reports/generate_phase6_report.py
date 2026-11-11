"""Render the actual local Phase 6 evidence; never runs training or cloud services."""
import json
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, PageBreak, Spacer

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'reports/phase6_end_to_end_integration_and_deployment.pdf'


def main():
    if OUTPUT.exists():
        raise SystemExit('Existing PDF is never overwritten')
    e = json.loads((ROOT / 'reports/evidence/phase6_final_acceptance.json').read_text(encoding='utf-8'))
    if not e['local_acceptance_passed']:
        raise SystemExit('Critical local acceptance checks must pass first')
    results = json.loads((ROOT / 'ml/artifacts/phase4/model_results.json').read_text(encoding='utf-8'))
    fonts = Path('C:/Windows/Fonts')
    for name, filename in [('Body', 'arial.ttf'), ('Bold', 'arialbd.ttf')]:
        pdfmetrics.registerFont(TTFont(name, str(fonts / filename)))
    pdfmetrics.registerFontFamily('Body', normal='Body', bold='Bold', italic='Body', boldItalic='Bold')
    navy, teal = colors.HexColor('#15364b'), colors.HexColor('#007f86')
    styles = {name: ParagraphStyle(name, fontName=font, fontSize=size, leading=leading,
        spaceAfter=8, textColor=navy) for name, font, size, leading in
        [('body', 'Body', 9.5, 13.5), ('small', 'Body', 8, 11), ('title', 'Bold', 25, 31),
         ('heading', 'Bold', 18, 23), ('sub', 'Bold', 11, 15), ('cell', 'Body', 8.3, 11.5)]}
    story = []
    def p(text, style='body'):
        story.append(Paragraph(text, styles[style]))
    def page(number, title):
        if story: story.append(PageBreak())
        p(f'SMART PARKING / PHASE 6 / {number:02d}', 'small')
        p(title, 'heading')
    def table(headers, rows, widths):
        data = [[Paragraph(escape(str(v)), styles['cell']) for v in row] for row in [headers, *rows]]
        t = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d9edf0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f6f8')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8), ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]))
        story.extend([t, Spacer(1, 12)])
    tests = {name: int(re.search(r'Ran (\d+) tests', e[name]['output']).group(1))
             for name in ('dashboard_regressions', 'backend_regressions')}

    page(1, 'Sequential integration verified')
    p('Twelve slots.<br/>One simulator at a time.', 'title')
    p('Actual end-to-end evidence, essential dashboard corrections and zero-cost deployment readiness.', 'sub')
    p('Evidence recorded at ' + escape(e['recorded_at_utc']) + ' (UTC). Local timezone: Asia/Kolkata.', 'small')
    table(['Device / slots', 'Capture', 'Valid messages', 'SQLite observations'],
        [[b['device_id'] + ' / ' + ', '.join(b['slots']), f"{b['duration_seconds']:.3f}s",
          b['valid_messages'], b['valid_messages'] * 4] for b in e['boards']], [182, 80, 100, 148])
    p('<b>PASS:</b> Every captured, validated board payload matched exactly four persisted slot observations. '
      'All twelve slot identities were verified across three separate simulator runs. No synthetic publishers were used on production topics.')
    p('<b>Boundary:</b> This is sequential integration verification. It does not prove simultaneous three-board operation, '
      'a fresh twelve-slot snapshot, continuous monitoring, real-world model accuracy or successful cloud deployment.')
    p(f"Regression evidence: {tests['dashboard_regressions']} dashboard tests and {tests['backend_regressions']} backend tests passed. "
      'No packages, credentials or security-policy changes were needed.')
    p('Authority: reports/evidence/phase6_final_acceptance.json and the six per-board MQTT/persistence evidence files.', 'small')

    page(2, 'Architecture, identities and data ownership')
    p('ESP32/Wokwi -> local Mosquitto:1883 -> FastAPI MQTT network thread -> bounded queue -> persistence worker -> SQLite. '
      'Streamlit reads FastAPI over configurable API_BASE_URL. Model execution remains behind the existing prediction adapters.')
    table(['Board', 'Topic', 'Slots'], [[f'ESP32-{i:02d}', f'smartparking/esp32_{i:02d}/telemetry',
        f'P{4*i-3}-P{4*i}'] for i in range(1, 4)], [80, 300, 130])
    p('Unique client IDs: smartparking-esp32_01, smartparking-esp32_02, smartparking-esp32_03. '
      'Firmware uses Wokwi-GUEST, channel 6, host.wokwi.internal:1883, QoS 1, non-retained telemetry and a nominal five-second interval.')
    table(['Local sensor position', 'TRIG / ECHO GPIO'], [['1', '13 / 34'], ['2', '14 / 35'],
        ['3', '25 / 32'], ['4', '26 / 33']], [255, 255])
    p('The GPIO mapping repeats on each board. Existing ECHO voltage dividers, firmware, circuits, topics and broker service configuration were unchanged.')
    p('SQLite remains outside OneDrive under the existing LOCALAPPDATA/SmartParking location. '
      'The schema contains telemetry_messages, occupancy_observations, slot_current and the twelve-slot registry. '
      'Only the existing backend wrote live telemetry; verification connections used SQLite mode=ro.')
    p('Existing endpoints remain: GET /slots, /slots/{slot_id}, /history, /stats and /health. '
      'The backend was neither restarted nor modified.')

    page(3, 'Diagnosis and resource-safe resolution')
    p('Initially, broker connections consisted of the backend and subscriber terminals, with zero production messages. '
      'VS Code logs placed all three Wokwi starts in one window, with each extension host terminating before the next start. '
      'The installed extension implements a singleton session per window; starting another disposes the previous session.')
    p('Closing its simulator webview disposes its gateway. There is no verified transfer from a running VS Code simulation '
      'to an independent background process. The documented serial-forwarding interface requires configuration before startup; it was not added to frozen files.')
    p('Resource check: 7.69 GiB usable RAM, about 638 MiB free, and 24% CPU load at measurement. '
      'Three full simulator windows were unsuitable. The accepted resolution was one additional window reused sequentially; '
      'the separate main Codex window was not operated, closed or reloaded.')
    p('Computer Use initially encountered stale targeting/user-input guards and an owned file-picker dialog. '
      'Automation paused, refreshed its own JavaScript handles, and cleared only the additional window dialog. '
      'The final sequence stopped ESP32-01, loaded ESP32-02 in that window, stopped ESP32-02 after verification, and loaded ESP32-03.')
    p('Wokwi CLI was not installed. An earlier attempt to run the existing executable with --help was blocked by Windows '
      'Application Control. No bypass, DLL relocation, policy change, token request or credential use followed.')
    p('UART startup/publishing was visually observed in Wokwi Terminal. Continuous Serial log files were not established. '
      'The durable evidence consists of exact MQTT payloads, receive times and matching SQLite records, not invented Serial transcripts.')

    page(4, 'Verification method and message semantics')
    p('For each board, the observer subscribed to all three production topics at QoS 1, ignored retained packets, '
      'captured the designated board for 60 or 90 seconds, and archived only documented payload fields. '
      'The separate verifier reused backend.schemas.parse_telemetry and opened the existing SQLite database read-only.')
    p('Schema: schema_version=1; assigned device_id; unsigned sequence and uptime_ms; UTC publication timestamp or null; '
      'clock_synced consistent with publication time; exactly four assigned slots. Each slot contains slot_id, distance_cm, '
      'occupancy_status and measurement timestamp. Known distances are 2-400 cm; UNKNOWN requires null distance.')
    p('The verifier matched device, sequence, uptime and publication timestamp, then compared all four stored slot IDs, '
      'distances, states and measurement timestamps. SQLite quick_check and foreign_key_check passed.')
    table(['Device', 'Receipt cadence', 'Sequence / timing evidence'], [
        ['ESP32-01', 'Median 5.032s', 'Eight messages, sequences 379-386. Publication age about 37.7-38.2s.'],
        ['ESP32-02', 'Median 5.000s', 'Sixteen messages, sequences 0-14 with sequence 5 repeated; one history-only message.'],
        ['ESP32-03', 'Median 5.000s', 'Sixteen messages, sequences 0-15. First publication clock unsynchronized.']], [90, 115, 305])
    p('Firmware increments sequence only after acknowledged publication. An observed payload followed by a missing '
      'acknowledgement can be followed by another payload with the same sequence. Both were preserved; the repeated '
      'sequence did not replace current state. This is consistent with source logic, not a controlled reconnection test.')
    p('The original capture utility expects all three boards concurrently, so its capture_checks_passed is false for '
      'these intentional single-board captures. Per-board acceptance is in *_persistence.json. Strict uninterrupted '
      'cadence also failed for ESP32-02; actual intervals and the repeat are retained, not hidden.')

    page(5, 'Historical graph and freshness corrections')
    p('Confirmed empty-chart cause: P3 had 22 receipt events within roughly 10 milliseconds at 15:13:02 UTC. '
      'A minute grid selected no past observation at 15:13:00; at 15:14:00 the events exceeded the 30-second tolerance. '
      'Every value became NaN. A line-only chart could also hide an isolated valid point.')
    p('Individual history now uses exact receipt timestamps, ordered by receipt and observation ID. Known readings use '
      'lines plus markers. UNKNOWN readings and explicit NaN separators after long gaps prevent unsupported connections. '
      'History-only rows are excluded from the accepted-current state trend. No jitter, interpolation, future fill or fabricated occupancy is added.')
    p('All-slot total occupancy still uses the original conservative minute reconstruction and requires twelve known states. '
      'Individual-slot history has no all-twelve requirement. The selected time window includes current partial-minute receipts.')
    p('Current cards preserve backend stale flags and additionally reject old or future-dated measurement timestamps when present. '
      'Missing measurement time is explicitly labelled; receipt-based availability is not presented as verified device-clock accuracy. '
      'MQTT diagnostics show last-delivery age separately from connected/subscribed transport status.')
    h = e['actual_p3_history']
    p(f"Actual API/AppTest: {h['loaded']} P3 observations loaded, {h['known_points']} known-state chart points and "
      f"{h['line_breaks']} explicit missing/gap rows. Twelve cards rendered; manual refresh and the P3 filter/history action ran without exceptions.")
    p(f"Tests: {tests['dashboard_regressions']} dashboard and {tests['backend_regressions']} backend tests passed. "
      'Coverage includes the original 22-event failure, sparse markers, gaps, filter bounds, timezone rejection, stale measurements, '
      'counts, API errors and refresh registration. Browser visual inspection and wall-clock browser refresh were not performed.')

    page(6, 'ML contract, preservation and honest limits')
    p('Persistence remains the selected Phase 4 model, chosen by validation MAE. Linear Regression and Random Forest '
      'remain in the same frozen bundle. No model was trained or retrained in Phase 6. The existing local in-process and '
      'approved-interpreter subprocess adapters passed the dashboard regression suite.')
    table(['Model', 'Synthetic test MAE', 'RMSE', 'R-squared'], [[name,
        f"{results['test'][key]['clipped']['mae']:.6f}", f"{results['test'][key]['clipped']['rmse']:.6f}",
        f"{results['test'][key]['clipped']['r2']:.6f}"] for key, name in
        [('persistence', 'Persistence'), ('linear_regression', 'Linear Regression'), ('random_forest', 'Random Forest')]], [165, 115, 115, 115])
    p('The frozen interface requires 37 features including the seven-day lag, with strictly causal rolling windows and '
      'a target exactly 15 minutes ahead. Sequential captures do not provide 10,081 complete minute snapshots. '
      'Live forecasting therefore remains unavailable; synthetic retrospective review remains clearly separate. Predictions are clipped to 0-12.')
    p('Model SHA-256: ' + e['model_sha256'], 'small')
    p(f"Preservation checks: {e['preservation']['protected_tracked_files_checked']} protected tracked files unchanged; "
      'Phase 1-5 PDFs, Phase 3/4 datasets, models and notebooks retained. All original message IDs 1-38 and observation IDs '
      '1-152 remain present. New real simulation observations were appended by the existing backend.')
    p('Captured states were VACANT. Real OCCUPIED/UNKNOWN transitions, sensor physical accuracy, clock accuracy and '
      'controlled Wi-Fi/broker outage recovery were not established by these tests. No simultaneous or 24/7 monitoring claim is made.')

    page(7, 'Zero-cost hosting readiness: deferred')
    p('No cloud resources were provisioned. The latest instruction prohibits credential/token use, installations and '
      'payment details. Accordingly, authenticated provisioning, Linux dependency installation and GitHub authentication were not performed.')
    table(['Candidate free service', 'Limits and changes still required'], [
        ['Streamlit Community Cloud', 'Existing frontend; configurable API_BASE_URL, in-process adapter. Sleeps after 12 hours idle; shared resources. Linux bundle reload unverified.'],
        ['Render Free FastAPI', 'Sleeps after 15 minutes without inbound traffic; cold starts; 750 workspace hours/month. Ephemeral SQLite is unsuitable. No card/payment method.'],
        ['Neon Free PostgreSQL', '1 GB/project, 100 CU-hours/month/project, 5 GB egress; scales to zero after five idle minutes. Existing sqlite3 backend needs an approved storage adapter.'],
        ['EMQX Serverless', 'Spend limit 0; 1 million session-minutes and 1 GB traffic/month. Exhaustion stops service. MQTT TLS 8883/authentication required; existing plain-TCP clients need adaptation.'],
        ['Cloudflare Quick Tunnel fallback', 'Temporary HTTPS URL, no uptime guarantee, 200 in-flight requests. Laptop must remain online; needs approved software and API authentication.']], [150, 360])
    p('These are demonstration candidates, not deployment claims. Account eligibility, remaining quotas and card-free signup '
      'must be verified before any future use. Never upgrade, attach a payment method or enable paid overages. No paid VPS, domain, backup service or subscription is required by the proposal.')
    p('Future order: approved API authentication and PostgreSQL/TLS adapters; isolated regression checks; permitted Linux '
      'model reload; explicit free-account verification; short supervised deployment test. Keep local SQLite intact. '
      'Broker traffic does not guarantee Render stays awake; laptop-hosted simulations stop when the laptop is off.')
    p('Sources checked in the Phase 6 audit: docs.streamlit.io/deploy/streamlit-community-cloud; render.com/docs/free; '
      'neon.com/pricing; docs.emqx.com/en/cloud/latest/deployments/spend_limit.html; developers.cloudflare.com/tunnel/get-started/quick-tunnels/.', 'small')

    page(8, 'Acceptance and continuation runbook')
    table(['Requirement', 'Status / evidence'], [
        ['Three boards, twelve assigned slots', 'PASS sequentially: 8 + 16 + 16 messages, 160 corresponding observations.'],
        ['Periodic production MQTT and SQLite mapping', 'PASS with recorded ESP32-02 repeat/timing limitation; exact payload matches archived.'],
        ['Historical slot graph and honest gaps', 'PASS regression and actual API/AppTest; receipt events preserved.'],
        ['Cards, counts, filters, errors, refresh controls', 'PASS automated tests; browser rendering/wall-clock refresh unverified.'],
        ['History and frozen artifacts preserved', 'PASS read-only SQLite verification and protected tracked-file checks.'],
        ['No installs, secrets, policies or paid services', 'PASS for this completion sequence.'],
        ['Simultaneous sessions / continuous Serial logs', 'NOT VERIFIED / NOT ESTABLISHED. Not required for the accepted sequential test.'],
        ['Real live 15-minute forecast', 'UNAVAILABLE: incomplete genuine feature history.'],
        ['Linux/cloud deployment', 'DEFERRED under no-install/no-credentials conditions.'],
        ['Git delivery', 'One meaningful file per commit; authenticated push requires credentials and remains constrained.']], [215, 295])
    p('Reproduce one board at a time, leaving FastAPI and Mosquitto running. Stop only the completed additional simulator, '
      'load the next dedicated workspace there, confirm its identity, and start Wokwi. Never replace the main Codex workspace.')
    p('Capture command (choose a new output):<br/><font face="Body">python -B esp32/tools/verify_mqtt_runtime.py --duration 90 '
      '--label sequential --output reports/evidence/NEW_mqtt.json</font>', 'small')
    p('Persistence command:<br/>python -B esp32/tools/verify_sequential_capture.py --capture reports/evidence/NEW_mqtt.json '
      '--device esp32_02 --minimum-duration 90 --output reports/evidence/NEW_persistence.json', 'small')
    p('Final local verification:<br/>python -B reports/verify_phase6.py --output reports/evidence/NEW_acceptance.json', 'small')
    p('All evidence writers refuse to overwrite existing outputs. Database verification is read-only. '
      'Old board readings becoming stale during another board test is expected; preserve the records and label the limitation.')

    def footer(canvas, doc):
        canvas.setStrokeColor(teal)
        canvas.line(42, 38, 553, 38)
        canvas.setFont('Body', 8)
        canvas.drawString(42, 25, 'Phase 6 | Evidence-led local demonstration | Recurring service spend: INR 0')
        canvas.drawRightString(553, 25, str(doc.page))
    SimpleDocTemplate(str(OUTPUT), pagesize=(595, 842), leftMargin=42, rightMargin=42,
        topMargin=38, bottomMargin=52, title='Smart Parking Phase 6: Sequential Integration and Deployment Readiness',
        author='Smart Parking Project').build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == '__main__':
    main()
