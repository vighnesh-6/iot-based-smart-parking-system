"""Generate the Phase 2 PDF from saved actual test evidence (requires ReportLab)."""

from collections import Counter
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports/phase2_fastapi_sqlite.pdf"
NAVY, TEAL, PALE = (colors.HexColor(c) for c in ("#15364B", "#007F86", "#EDF5F7"))


def main():
    evidence = ROOT / "reports/evidence"
    def read(name):
        return json.loads((evidence / name).read_text(encoding="utf-8"))
    unit = read("phase2_unit_tests.json")
    broker = read("phase2_final_integration.json")
    production = read("phase2_production_observation.json")
    checks = read("phase2_repository_checks.json")
    failed = read("phase2_pre_fix_tests.json")
    for name, filename in [("Body", "arial.ttf"), ("Bold", "arialbd.ttf"), ("Mono", "consola.ttf")]:
        pdfmetrics.registerFont(TTFont(name, "C:/Windows/Fonts/" + filename))
    pdfmetrics.registerFontFamily("Body", normal="Body", bold="Bold", italic="Body", boldItalic="Bold")
    styles = {
        "body": ParagraphStyle("body", fontName="Body", fontSize=9.5, leading=13.4, spaceAfter=8, textColor=NAVY),
        "title": ParagraphStyle("title", fontName="Bold", fontSize=23, leading=28, spaceAfter=18, textColor=NAVY),
        "heading": ParagraphStyle("heading", fontName="Bold", fontSize=17, leading=22, spaceAfter=12, textColor=NAVY),
        "sub": ParagraphStyle("sub", fontName="Bold", fontSize=11, leading=15, spaceBefore=8, spaceAfter=6, textColor=TEAL),
        "small": ParagraphStyle("small", fontName="Body", fontSize=8, leading=11, spaceAfter=6, textColor=NAVY),
        "cell": ParagraphStyle("cell", fontName="Body", fontSize=8.3, leading=11, textColor=NAVY),
        "header": ParagraphStyle("header", fontName="Bold", fontSize=8.3, leading=11, textColor=colors.white),
        "code": ParagraphStyle("code", fontName="Mono", fontSize=7.7, leading=10, spaceAfter=10, textColor=NAVY),
    }
    story = []
    def p(text, style="body"):
        story.append(Paragraph(text, styles[style]))
    def sub(text): p(text, "sub")
    def code(text): story.append(Preformatted(text, styles["code"]))
    def page(number, title):
        if story: story.append(PageBreak())
        p(f"PHASE 2 / FASTAPI + SQLITE / {number:02d}", "small")
        p(title, "heading")
    def table(headers, rows, widths):
        data = [[Paragraph(escape(h), styles["header"]) for h in headers]]
        data += [[Paragraph(escape(str(v)), styles["cell"]) for v in row] for row in rows]
        item = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        item.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), NAVY), ("ROWBACKGROUNDS", (0,1), (-1,-1), [PALE,colors.white]),
            ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 8),
            ("RIGHTPADDING", (0,0), (-1,-1), 8), ("TOPPADDING", (0,0), (-1,-1), 7),
            ("BOTTOMPADDING", (0,0), (-1,-1), 7)]))
        story.append(item); story.append(Spacer(1,8))

    page(1, "Phase 2 implementation and verification")
    story.append(Spacer(1,15))
    p("Smart Parking System<br/>FastAPI + SQLite Integration", "title")
    p("Three ESP32 devices | Twelve slots | Independent MQTT ingestion", "sub")
    p("Prepared 10 November 2026. This report documents the completed local backend, actual automated test evidence, production observation limits and continuation commands. Times in evidence use UTC; local project timezone is Asia/Calcutta (IST).")
    table(["Verification class", "Actual result"], [
        ("Final automated suite", f"{unit['tests_run']} tests; successful={unit['successful']}; failures={unit['failures']}, errors={unit['errors']}, skipped={unit['skipped']}."),
        ("Real broker/backend/API integration", f"{len(broker['checks'])} synthetic-fixture checks; passed={broker['passed']}. These are Python publishers, not ESP32 runtime evidence."),
        ("Production observation", f"{production['duration_seconds']} seconds; HTTP health={production['health_http_status']}; historical observations={production['history_total']}. No new ESP32-to-API delivery pass."),
        ("Preservation", "Existing databases were not selected for tests or reset. ESP32, circuits, topics, broker configuration, requirements, ML and dashboard remain unchanged."),
    ], [163,336])
    p("Phase 1 delivery remains operator-observed, with no original subscriber screenshot or payload archive. The new backend tests do not retroactively establish timestamp accuracy, physical sensing or ESP32 reconnection. Detailed device runtime acceptance remains open.")
    p("No credentials, live SQLite files, virtual environment or build output are included in Git. Implementation was completed and tested before the per-file commits; all commits are intended for one final push.", "small")

    page(2, "Architecture and data flow")
    table(["Stage", "Responsibility / execution context"], [
        ("ESP32-01 / 02 / 03", "P1-P4 / P5-P8 / P9-P12; unchanged firmware publishes four-slot snapshots."),
        ("Wokwi private gateway", "Firmware broker host stays host.wokwi.internal:1883."),
        ("Local Mosquitto", "PC-side backend connects to 127.0.0.1:1883. Existing service is unchanged."),
        ("MQTT network thread", "Connect, subscribe, receive bounded packets, enqueue and service reconnects. No database writes here."),
        ("Bounded queue -> persistence worker", "Strict validation -> canonical duplicate check -> one SQLite transaction -> manual acknowledgement."),
        ("SQLite -> REST API", "Short-lived connections per operation. Synchronous endpoints execute in worker threads, independent of ingestion."),
    ], [157,342])
    sub("Lifecycle and ownership")
    p("FastAPI lifespan initializes a new or recognized schema off the event loop, then starts the persistence and MQTT threads. Shutdown signals both threads and joins them; queued or unsuccessfully stored messages remain unacknowledged. Importing backend.main does not create a database or connect to MQTT.")
    p("Run a single Uvicorn process and one backend client identity. Multiple workers/reload would create competing subscribers and unnecessary SQLite contention. API handlers do not share SQLite connections with ingestion or perform synchronous database work on the event loop. [1]")
    sub("Scope")
    p("Implemented: validation, history/current persistence, idempotent duplicate handling, reconnect/backpressure behavior, read APIs, health and evidence tooling. Not implemented: ML, predictions, Streamlit, public deployment, API authentication/TLS, lossless historical buffering or new sensor/firmware behavior.")

    page(3, "Topics, configuration and telemetry contract")
    table(["Topic", "Device", "Slots"], [(f"smartparking/esp32_0{i}/telemetry", f"esp32_0{i}", f"P{4*i-3}-P{4*i}") for i in range(1,4)], [282,100,117])
    table(["Root field", "Validation / interpretation"], [
        ("schema_version", "Strict integer 1; booleans and coercion rejected."),
        ("device_id / slots", "Topic must match known device; exactly four distinct assigned slots."),
        ("sequence / uptime_ms", "Strict unsigned 32-bit integers; reset/wrap is possible."),
        ("timestamp / clock_synced", "Valid UTC YYYY-MM-DDTHH:MM:SSZ or null; root flag agrees with nullability."),
        ("Slot fields", "slot_id, distance_cm, occupancy_status, timestamp; no extra fields."),
        ("Distance / state", "Finite numeric 2-400 cm for OCCUPIED/VACANT; null for UNKNOWN. Device classification preserved."),
    ], [154,345])
    p("Payloads are limited to 4,096 bytes. UTF-8, JSON syntax, duplicate object keys, unknown fields, nonfinite numbers, boolean/string numeric substitutions, invalid dates and slot/device mismatches are rejected. Startup null times and mixed null slot times during SNTP acquisition are accepted. Timestamp format validation is not NTP accuracy verification.")
    p("Public defaults: PC broker 127.0.0.1:1883; client smartparking-backend; queue 256; stale timeout 30 seconds; MQTT enabled. .env.example now reflects the fixed production topics. Private .env is optional; process environment overrides it. Passwords are excluded from settings repr and logs. No topic-prefix override is exposed in production configuration.")
    p("Installed environment: " + "; ".join(f"{name} {version}" for name,version in unit["python_dependencies"].items()) + ". No project packages were installed or removed.", "small")

    page(4, "SQLite schema and preservation policy")
    table(["Table", "Keys and stored information"], [
        ("slots", "Twelve fixed slot IDs; assigned device; unique slot/device pair."),
        ("telemetry_messages", "Integer PK; unique SHA-256 fingerprint; device, sequence, uptime, publish/receipt times, clock flag, inferred session and applied_current."),
        ("occupancy_observations", "Integer PK; message/slot foreign keys; unique message+slot; state, distance and measurement timestamp."),
        ("slot_current", "One row per observed slot, pointing to its latest accepted observation."),
    ], [152,347])
    p("Every new snapshot inserts a message and all four observations atomically, and updates current pointers only when eligible. Any failure rolls back the entire transaction. History indexes support slot/device/reception-time queries. Foreign keys, state/distance checks, full synchronous writes and bounded lock timeouts are enabled. Reads use independent connections; each connection closes after its operation.")
    sub("Existing data is never reset")
    p("Default live path: %LOCALAPPDATA%\\SmartParking\\parking.db. Paths must be absolute and outside the checkout and OneDrive. New files are reserved with exclusive creation. Existing files are inspected read-only for application ID 0x53504B32, schema version 1, required tables, exact slot registry and DELETE journal mode. Unrecognized or incomplete files are refused without schema replacement or deletion. There are no automatic migrations or pruning jobs.")
    p("The installed SQLite is " + unit["sqlite_version"] + ". Rollback journal mode is intentional: SQLite documents a WAL-reset concurrency bug affecting this version. The project environment was preserved instead of enabling WAL or upgrading Python. Existing journal modes are not silently changed. [3]")
    sub("Backups and test isolation")
    p("Use SQLite's backup API to a new external destination, or stop the backend cleanly before copying. Never copy an open database alone as a claimed consistent backup. Automated tests create only private unique Windows Temp databases and clean up their own fixtures. No default live database was opened by verification. An unrelated test-created database was rejected with an unchanged byte hash.")

    page(5, "MQTT reliability, ordering and freshness")
    sub("Commit-before-acknowledgement")
    p("The subscriber uses MQTT 3.1.1, QoS 1, a persistent broker session and manual ACK. The network thread queues bounded data; a separate worker validates and writes. A successful transaction or durable duplicate lookup precedes acknowledgement. This closes the normal callback-return-before-database-write gap. Paho explicitly supports post-processing acknowledgement. [2]")
    p("Invalid, retained, unsupported-topic or unsupported-QoS messages are counted and acknowledged without persistence. Database errors hold ACK and retry; health becomes degraded. Queue overflow leaves that packet unacknowledged and requests reconnect. Connection generations prevent a worker acknowledging an old packet ID after a newer connection reuses it. Unexpected worker/network failures are visible; threads do not silently manufacture a pass.")
    sub("Recovery")
    p("The network worker reconnects with 1-30 second backoff and resubscribes after CONNACK. Health requires connection, QoS 1 subscription grants and live threads. Shutdown leaves pending unsuccessful work unacknowledged. Broker session retention, broker persistence, disk availability and Paho process-state limits still apply; there is no end-to-end exactly-once or lossless-crash guarantee.")
    sub("Duplicate identity and ordering limits")
    p("Canonical content includes device, sequence, uptime, times and sorted slot values. Its persistent SHA-256 fingerprint suppresses equivalent duplicates across backend restarts. Duplicate receipt does not refresh current freshness. New observations with older known publication times or older non-boot counters can be history-only. Counter wrap and near-boot low counters infer a new session; equal-counter conflicts remain history-only.")
    p("Firmware has no boot ID. Delayed unsynchronized packets, unobserved reboots and identical early-boot snapshots cannot always be distinguished. Session inference is explicitly heuristic. A future boot/session identifier would improve this, but firmware compatibility is preserved in Phase 2.")
    p("Current status preserves the last device classification plus observed/stale flags. Stale and unseen slots count as effective UNKNOWN in statistics, never as free spaces. Freshness is based on backend reception time; it cannot prove original measurement age for unsynchronized delayed traffic.")

    page(6, "REST API contract and examples")
    table(["GET endpoint", "Behavior"], [
        ("/slots", "Twelve slots in numeric order; last state, distance, measured/received times, sequence, stale and observed."),
        ("/slots/{slot_id}", "One registered slot; 404 for unknown IDs."),
        ("/history", "Newest observation ID first; items, total, limit and offset. Filters: slot_id, device_id, state, since, until."),
        ("/stats", "Total 12; fresh occupied/vacant; effective unknown; stale and unseen; occupied/12 percentage."),
        ("/health", "200 ready or 503 degraded; database_ok plus MQTT connection, subscriptions, queue, counters, timestamps and thread status."),
        ("/docs / /openapi.json", "Generated interactive documentation / machine-readable API contract."),
    ], [150,349])
    p("History time bounds are inclusive and apply to backend reception time. Timezone-aware input is normalized to UTC. limit defaults to 100 and must be 1-1000; offset must be nonnegative. Invalid filters and reversed/naive time ranges return 422. SQLite request errors return a generic 503 without leaking paths. Pagination is consistent within each request, not a frozen multi-request export snapshot.")
    sub("Actual isolated-test aggregate after restart")
    code(json.dumps(broker["after_restart_stats"], indent=2))
    p("These values came from synthetic fixtures on validation topics: P1 was changed to OCCUPIED, the other eleven remained VACANT. They are not live sensor availability. Stale/unseen counts overlap with effective unknown; occupied + vacant + unknown always equals 12.")
    p("Health readiness and data freshness are separate: the production observation returned HTTP 200 with twelve unseen slots. MQTT_ENABLED=false explicitly disables ingestion and allows healthy database/API-only operation; health reports enabled=false.")

    page(7, "Startup and verification commands")
    sub("Run from repository root")
    code('.\\.venv\\Scripts\\python.exe -m uvicorn backend.main:app `\n  --host 127.0.0.1 --port 8000 --workers 1\n\nInvoke-RestMethod http://127.0.0.1:8000/slots\nInvoke-RestMethod http://127.0.0.1:8000/slots/P1\nInvoke-RestMethod "http://127.0.0.1:8000/history?slot_id=P1&limit=20"\nInvoke-RestMethod http://127.0.0.1:8000/stats\nInvoke-RestMethod http://127.0.0.1:8000/health')
    p("Use defaults or a private .env copied deliberately from .env.example. Check DATABASE_PATH before startup. Do not use multiple workers, reload mode or a second backend sharing the same MQTT ID. No service configuration change is required.")
    sub("Executed checks / repeatable commands")
    code('.\\.venv\\Scripts\\python.exe -m unittest discover -s backend/tests -v\n\n.\\.venv\\Scripts\\python.exe -m backend.tools.verify_integration `\n  --output reports/evidence/phase2_broker_followup.json\n\n.\\.venv\\Scripts\\python.exe esp32/tests/test_circuits.py')
    p("Choose a new evidence output name. Integration starts real local HTTP, a backend MQTT subscriber and a synthetic publisher on a unique smartparking/validation/phase2/... namespace. It uses a private temporary database, tests one backend transport reconnect, restarts the backend and checks durable deduplication. It never publishes production topics or restarts Mosquitto.")
    p("Tests use standard-library unittest and urllib, existing Uvicorn and existing Paho; pytest/httpx are not required. External temporary database creation and loopback networking required execution outside the restricted sandbox. This is a tooling permission condition, not an application test pass.")
    sub("Production observation procedure actually used")
    p("A temporary backend used the unchanged production topic map and a unique observer client ID. After all subscriptions were active, a read-only 30-second window collected health, slots, history total and statistics through HTTP. The observer was stopped and only its test session was cleared. No publisher or device simulation was started for that observation.")

    page(8, "Actual automated and broker test results")
    groups = Counter(name.split(".")[0] for name in unit["test_ids"])
    table(["Suite", "Tests", "Coverage"], [
        (name, count, {"test_api":"Real HTTP, OpenAPI, filters, errors, parallel reads, settings, unavailable broker",
                       "test_database":"Atomicity, locks, duplicates, persistence, history, ordering, existing-file preservation",
                       "test_ingestion":"ACK order, invalid/retained packets, queue pressure, retries, callbacks, shutdown",
                       "test_validation":"Three-device contract, slot identities, strict values, dates, malformed JSON"}.get(name,""))
        for name,count in sorted(groups.items())], [125,45,329])
    p(f"Final run: {unit['tests_run']} tests in {unit['duration_seconds']} seconds; successful={unit['successful']}; {unit['failures']} failures, {unit['errors']} errors, {unit['skipped']} skips. Full test IDs, runner output and source SHA-256 hashes are saved in phase2_unit_tests.json.")
    table(["Real local-broker check", "Result"], [(name.replace("_"," "), "PASSED" if passed else "FAILED") for name,passed in broker["checks"].items()], [399,100])
    p("Final integration namespace: " + broker["namespace"] + ". Backend reconnect counter reached " + str(broker["before_restart_status"]["reconnects"]) + "; stored snapshots=4, duplicate=1 and rejected=1 before restart. History remained 16 observations after restart and replay. This verifies backend reconnection using synthetic data, not ESP32 Wi-Fi recovery.")
    sub("Failures retained and corrected")
    p(f"Initial sandbox execution could not access Windows Temp. A fixture left a connection open during cleanup; that was fixed and 41 tests passed. The expanded pre-fix {failed['tests_run']}-test run had {failed['failures']} failure: unavailable broker exposed a reference to nonexistent paho.mqtt.client.MQTTException. The handler was corrected; the final complete run and real-broker integration were repeated successfully. The failed evidence remains archived.")

    page(9, "Production result, limits and troubleshooting")
    table(["Production observation", "Recorded result"], [
        ("UTC start / end", production["started_at_utc"] + " / " + production["ended_at_utc"]),
        ("MQTT readiness", "Connected and subscribed to all three production topics; HTTP health 200."),
        ("Received observations", production["history_total"]),
        ("Availability result", "0 occupied, 0 vacant, 12 UNKNOWN; 12 stale and unseen."),
        ("ESP32-to-API acceptance", "NOT OBSERVED in this window. Prior Phase 1 delivery remains operator-observed only."),
    ], [162,337])
    p("No production messages were available to archive or correlate with actual sensor changes. Therefore live production JSON compatibility, sensor timestamps, periodic arrival cadence and ESP32 recovery are not newly runtime-verified. Static contract checks and synthetic backend tests passed separately.")
    table(["Symptom", "Action"], [
        ("Existing database rejected", "Preserve it; choose a new external filename and review ownership/schema. Never delete or reset automatically."),
        ("MQTT disconnected / health 503", "Check PC broker address/port, credentials, unique backend client ID and service availability."),
        ("Health 200, slots UNKNOWN", "Check simulations and actual production traffic; distinguish no data from invalid-message rejection."),
        ("Database errors / queue grows", "Check disk, permissions, locks and duplicate processes. ACK remains withheld; broker retention limits apply."),
        ("Stale/history-only readings", "Inspect receipt time, device time, counters and restart ambiguity. Do not infer vacancy from silence."),
        ("Invalid payloads", "Capture exact Serial/subscriber output without secrets and compare with schemas.py; never spoof production topics."),
    ], [166,333])
    p("Operational limits: trusted local development only; no API authentication/TLS, retention/pruning automation, schema migration framework, globally reliable boot identity, multi-process ingestion or lossless-outage guarantee. History grows continuously. Plan storage monitoring and deliberate backups. ML/dashboard integration has not started.")

    page(10, "Evidence, source files and continuation")
    descriptions = {
        "phase2_unit_tests.json":"Final 43-test run, exact test IDs, output and source hashes",
        "phase2_pre_fix_tests.json":"Earlier failed expanded test run before exception-handler fix",
        "phase2_broker_integration.json":"Initial seven-check synthetic broker integration pass",
        "phase2_final_integration.json":"Final integration rerun after all backend fixes",
        "phase2_production_observation.json":"Read-only production observation; zero messages",
        "phase2_repository_checks.json":"Circuit regression, protected files, environment and broker hashes",
    }
    table(["Evidence under reports/evidence/", "Purpose"], descriptions.items(), [241,258])
    p("Repository checks: circuit tests exit " + str(checks["circuit_tests_returncode"]) + "; protected paths changed=" + str(checks["protected_paths_changed"]) + "; requirements match pip freeze=" + str(checks["requirements_matches_existing_freeze"]) + "; broker config hash matches Phase 1=" + str(checks["mosquitto_config_matches_phase1"]) + ". Hash comparison normalized hexadecimal case; the initial case-sensitive assertion was corrected without changing the measured bytes.")
    sub("Implementation map")
    p("backend/config.py: settings/path policy; schemas.py: strict telemetry and API models; db.py: storage; mqtt_ingest.py: threads/ACK/reconnect; main.py: lifespan/endpoints; tests/: fixtures and four test modules; tools/verify_integration.py: isolated real-broker verification. backend/__init__.py remains unchanged. Usage and schema instructions are in backend/README.md and database/README.md.")
    sub("Primary references")
    for label,url in [
        ("[1] FastAPI concurrency and synchronous handlers", "https://fastapi.tiangolo.com/async/"),
        ("[2] Paho MQTT client, manual ACK and persistent sessions", "https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html"),
        ("[3] SQLite WAL-reset bug and affected versions", "https://sqlite.org/wal.html#the_wal_reset_bug"),
    ]:
        p(f'{label}<br/><link href="{url}" color="#007F86">{url}</link>', "small")
    p("Continuation: run the single-worker backend with a reviewed external database path, start the three existing Wokwi simulations manually, and archive fresh production messages plus API results and sensor-change correlations. Test controlled device recovery separately. Keep operator observations and independently saved evidence distinct. No ML or dashboard work is authorized by this report.")
    p("Reproduce with reports/generate_phase2_report.py using ReportLab and Windows Arial/Consolas fonts. PDF tooling comes from the bundled environment; it does not modify the project's dependency snapshot. The PDF was rendered and visually checked before delivery.", "small")

    def furniture(canvas, doc):
        width,height=doc.pagesize
        canvas.setStrokeColor(TEAL); canvas.setLineWidth(1.5); canvas.line(48,height-39,width-48,height-39)
        canvas.setFont("Bold",8); canvas.setFillColor(NAVY)
        canvas.drawString(48,height-28,"SMART PARKING / PHASE 2 FASTAPI + SQLITE")
        canvas.setLineWidth(.5); canvas.line(48,39,width-48,39)
        canvas.setFont("Body",7.5)
        canvas.drawString(48,25,"10 Nov 2026 | Actual evidence and explicit runtime limits | No ML/dashboard")
        canvas.drawRightString(width-48,25,str(doc.page))
    doc=SimpleDocTemplate(str(OUTPUT),pagesize=(595.28,841.89),leftMargin=48,rightMargin=48,topMargin=59,bottomMargin=54,
                          title="Phase 2 FastAPI and SQLite - Smart Parking",author="Smart Parking Project")
    doc.build(story,onFirstPage=furniture,onLaterPages=furniture)
    print(OUTPUT)


if __name__ == "__main__":
    main()
