"""Generate the Phase 1 reference PDF from recorded evidence and source files.

Run with a Python environment containing reportlab. Evidence never becomes a
runtime pass merely because firmware compiled or an operator reported success.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape
import hashlib
import json
import subprocess

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
OUTPUT = REPORTS / "phase1_mqtt_integration.pdf"
IST = timezone(timedelta(hours=5, minutes=30))
NAVY, TEAL = colors.HexColor("#15364B"), colors.HexColor("#007F86")
INK, PALE = colors.HexColor("#263C49"), colors.HexColor("#EDF5F7")


def load_evidence():
    records = []
    for path in sorted((REPORTS / "evidence").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        records.append((path, data))
    return records


def main():
    records = load_evidence()
    captures = [(p, d) for p, d in records if d.get("source") == "read_only_production_mqtt_subscription"]
    totals = {f"esp32_{i:02d}": sum(d["devices"][f"esp32_{i:02d}"]["valid_unique_messages"] for _, d in captures) for i in range(1, 4)}
    env = next((d for p, d in records if p.name == "phase1_environment.json"), {})
    system = next((d for p, d in records if p.name == "phase1_broker_system.json"), {})
    operator = next((d for p, d in records if p.name == "phase1_operator_observation.json"), {})
    diagnostic = next((d for p, d in records if p.name == "phase1_diagnostic_build.json"), {})
    status = "DELIVERY OPERATOR-OBSERVED; DETAILED TESTS OPEN" if operator else "RUNTIME NOT VERIFIED"
    source_commit = env.get("source_commit", subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip())
    for name, filename in [("BodyFont", "arial.ttf"), ("BoldFont", "arialbd.ttf"), ("MonoFont", "consola.ttf")]:
        pdfmetrics.registerFont(TTFont(name, "C:/Windows/Fonts/" + filename))
    pdfmetrics.registerFontFamily("BodyFont", normal="BodyFont", bold="BoldFont", italic="BodyFont", boldItalic="BoldFont")
    styles = {
        "body": ParagraphStyle("body", fontName="BodyFont", fontSize=9.5, leading=13.2, textColor=INK, spaceAfter=7),
        "title": ParagraphStyle("title", fontName="BoldFont", fontSize=24, leading=29, textColor=NAVY, spaceAfter=17),
        "heading": ParagraphStyle("heading", fontName="BoldFont", fontSize=18, leading=23, textColor=NAVY, spaceAfter=12),
        "sub": ParagraphStyle("sub", fontName="BoldFont", fontSize=11, leading=15, textColor=TEAL, spaceBefore=8, spaceAfter=5),
        "small": ParagraphStyle("small", fontName="BodyFont", fontSize=8, leading=10.6, textColor=INK, spaceAfter=5),
        "cell": ParagraphStyle("cell", fontName="BodyFont", fontSize=8.5, leading=11.2, textColor=INK),
        "header": ParagraphStyle("header", fontName="BoldFont", fontSize=8.5, leading=11.2, textColor=colors.white),
        "code": ParagraphStyle("code", fontName="MonoFont", fontSize=7.5, leading=9.5, textColor=INK, spaceAfter=9),
    }
    story = []

    def p(text, style="body"):
        story.append(Paragraph(text, styles[style]))

    def sub(text): p(text, "sub")
    def code(text): story.append(Preformatted(text, styles["code"]))

    def page(number, title):
        if story: story.append(PageBreak())
        p(f"PHASE 1 MQTT / REFERENCE &amp; VALIDATION / {number:02d}", "small")
        p(title, "heading")

    def table(headers, rows, widths):
        cells = [[Paragraph(escape(str(value)), styles["header"]) for value in headers]]
        cells += [[Paragraph(str(value), styles["cell"]) for value in row] for row in rows]
        item = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
        item.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PALE, colors.white]),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.append(item)
        story.append(Spacer(1, 8))

    def note(text):
        item = Table([[Paragraph(text, styles["body"])]], colWidths=[499])
        item.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE),
                                 ("BOX", (0, 0), (-1, -1), 0.6, TEAL),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 11),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 11),
                                 ("TOPPADDING", (0, 0), (-1, -1), 9)]))
        story.append(item)

    page(1, "Phase 1 MQTT integration")
    story.append(Spacer(1, 20))
    p("Smart Parking System<br/>Runtime Audit &amp; Continuation Report", "title")
    p("Three ESP32 boards | Twelve HC-SR04 slots | Local Mosquitto", "sub")
    p("Prepared 10 November 2026. Times are explicitly labelled UTC or IST (Asia/Calcutta). This report records measured results, operator statements and implementation details separately.")
    note(f"<b>{status}.</b> All three firmware builds and local Python broker checks passed. The operator observed all three simulations delivering telemetry to their production topics with assigned slots P1-P12. No original screenshot or payload archive is available. Detailed cadence, timestamps, state transitions and recovery remain unverified; no complete acceptance-suite pass is claimed.")
    story.append(Spacer(1, 16))
    table(["Item", "Recorded basis"], [
        ("Initial source baseline", source_commit),
        ("Production captures", f"{len(captures)} separate observation windows; " + ", ".join(f"{key}: {value} valid messages" for key, value in totals.items())),
        ("Operator statements", "Later operator report confirms simultaneous simulations and subscriber delivery on all three production topics with P1-P12. Recorded as operator-observed only; original subscriber output and exact per-board payloads are unavailable."),
        ("CLI access", "Wokwi CLI installed; token not available in process, user or machine environment at initial inspection. Operator selected the VS Code launch route."),
        ("Scope", "ESP32 MQTT runtime audit, diagnostic tools and documentation only. No FastAPI, SQLite, ML or dashboard implementation."),
    ], [136, 363])
    p("The original four-slot code remains preserved at tag backup/4-slot-serial-baseline. The 12-slot source and board workspaces are preserved in Git. A documentation commit does not change the acceptance status of the runtime tests.", "small")

    page(2, "Architecture and boundaries")
    class Architecture(Flowable):
        def __init__(self): super().__init__(); self.width = 499; self.height = 250
        def draw(self):
            canvas = self.canv
            def box(x, y, width, title, text):
                canvas.setFillColor(PALE); canvas.setStrokeColor(TEAL)
                canvas.roundRect(x, y, width, 48, 5, fill=1, stroke=1)
                canvas.setFillColor(NAVY); canvas.setFont("BoldFont", 9)
                canvas.drawCentredString(x+width/2, y+29, title)
                canvas.setFont("BodyFont", 8); canvas.drawCentredString(x+width/2, y+13, text)
            def arrow(x, y, xx, yy):
                import math
                canvas.setStrokeColor(TEAL); canvas.line(x,y,xx,yy)
                angle=math.atan2(yy-y,xx-x)
                for delta in (-0.45,0.45): canvas.line(xx,yy,xx-6*math.cos(angle+delta),yy-6*math.sin(angle+delta))
            for i in range(3):
                box(i*173, 195, 153, f"ESP32-0{i+1}", f"HC-SR04 slots P{4*i+1}-P{4*i+4}")
                arrow(i*173+76,195,110,164)
            box(0,116,220,"VS Code Wokwi private gateway","host.wokwi.internal")
            box(279,116,220,"Local Mosquitto","MQTT TCP port 1883")
            arrow(220,140,279,140)
            box(279,28,220,"Read-only runtime observer","Three production topics / JSON evidence")
            arrow(389,116,389,76)
            canvas.setFillColor(INK); canvas.setFont("BodyFont",8)
            canvas.drawString(0,12,"Three separate Wokwi simulations; the combined diagram is an overview.")
    story.append(Architecture())
    sub("End-to-end path to prove")
    p("For each board: sensor measurement -> unchanged occupancy classification -> a completed four-slot snapshot -> MQTT JSON publish -> broker forwarding -> a fresh message on the matching production subscription. A Serial connection statement alone does not prove the final delivery step.")
    p("Wokwi does not support multiple microcontrollers executing in one project. Each board therefore has its own simulation folder and VS Code workspace. The combined esp32/diagram.json is a wiring overview, not a three-controller runtime configuration. [1]")
    sub("Included and excluded components")
    p("Included: Wi-Fi, private-gateway routing, board identities, MQTT reconnect logic, JSON snapshots, Serial diagnostics and evidence capture. Excluded: database ingestion, occupancy aggregation across devices, REST APIs, prediction, dashboard wiring and deployment. The local broker is shared; firmware handles only each board's four assigned sensors.")

    page(3, "Circuit mapping and detection behavior")
    table(["Board", "Slot", "TRIG GPIO", "ECHO GPIO after divider"], [
        (f"ESP32-{board:02d}", f"P{4*(board-1)+local+1}", trig, echo)
        for board in range(1,4) for local,(trig,echo) in enumerate([(13,34),(14,35),(25,32),(26,33)])
    ], [112, 62, 105, 220])
    p("Every sensor VCC connects to its assigned board's 5V, and GND connects to that board's GND.1. Every ECHO has its own 1,000-ohm series resistor and 1,800-ohm shunt resistor to ground; the ESP32 input is at the divider midpoint. No signal node is shared between slots or boards.")
    code("Sensor ECHO -- 1 kOhm --+-- assigned ESP32 ECHO GPIO\n                       |\n                    1.8 kOhm\n                       |\n                  assigned board GND")
    p("Calculated midpoint for a 5 V ECHO high: 5 x 1800 / (1000 + 1800) = 3.214 V. This is a calculation, not a voltage measured in Wokwi. The simulator's analog support is limited; physical hardware still requires appropriate components, supply checks and measured logic levels. [4]")
    p("Detection remains: 10 us trigger; pulseIn HIGH with 30 ms timeout; distance_cm = echo_us / 58; valid range 2-400 cm; OCCUPIED at or below the configurable 20 cm threshold; VACANT above it; UNKNOWN on timeout or out-of-range. Invalid distance is null in MQTT. Measurements are sequential, with a 60 ms quiet interval. [5]")

    page(4, "Firmware implementation and recovery design")
    sub("Board-specific compilation")
    p("platformio.ini defines esp32_01, esp32_02 and esp32_03 with PARKING_BOARD_ID=1, 2 and 3. A missing or invalid ID fails compilation. The selected branch contains exactly four slot entries. MQTT uses the pinned 256dpi/MQTT@2.5.3 library; the Espressif platform remains pinned at 8.0.0. No Python environment dependencies were changed for firmware integration.")
    sub("Publish call path")
    p("setup initializes Serial, TRIG outputs and ECHO inputs, starts station-mode Wi-Fi and configures the MQTT transport. Each loop services the network, measures and prints the four local slots, services the network during quiet intervals, then calls publishTelemetry(samples). That call happens after every completed scan. A call is not necessarily a publish: disconnected or not-yet-due conditions return early.")
    p("An eligible publication builds one bounded JSON snapshot and calls gMqtt.publish(topic, payload, false, 1). The false argument disables retention; 1 requests QoS 1. A true result triggers the success log and sequence increment. False is logged as failure and does not prove broker delivery. PARKING_MQTT_LOG_PAYLOAD defaults to 1. Serial prints the connected/due gate each scan, the production topic before an attempt, and the exact JSON only after publish returns true. last_error and return_code diagnose failure without printing credentials. Set the flag to 0 after diagnostics if desired.")
    sub("Timing and disconnection behavior")
    p("Scans target one second and publications target five seconds. Network service runs between sensors and in short sleep slices. There is no infinite wait-until-connected loop. TCP and MQTT acknowledgement timeouts are configured at about one second, while DNS or stack delays can still extend a scan. Retry delays are capped at 30 seconds; a successful reconnect resets publication gating so a new scan can be sent.")
    p("No disconnected history is queued. A failed publication is rate-limited, and the next eligible attempt uses a fresh scan. QoS 1 can duplicate messages. Sequence counts acknowledged sends and resets on reboot; it is not a globally unique ingestion key. A future backend will need explicit restart/session identity and duplicate/freshness policy.")
    note("<b>Inspection versus execution:</b> the source contains the post-scan publish call. The call path is source-verified. Subscriber delivery is operator-observed. No exact Serial log is archived, and which binary produced that observation is not independently established.")

    page(5, "MQTT configuration and workspaces")
    table(["Build / device", "Client ID", "Production topic"], [
        (f"esp32_0{i}",f"smartparking-esp32_0{i}",f"smartparking/esp32_0{i}/telemetry") for i in range(1,4)
    ], [94, 160, 245])
    table(["Setting", "Value / interpretation"], [
        ("ESP32 broker", "host.wokwi.internal:1883 through the private gateway; not localhost."),
        ("PC observer broker", "127.0.0.1:1883. The observer runs on the PC, outside the simulated ESP32."),
        ("Wi-Fi", "Wokwi-GUEST, empty password, channel 6."),
        ("Payload cadence", "Five seconds when connected; exactly four local slots per snapshot."),
        ("Delivery", "MQTT 3.1.1, QoS 1, retain=false. Distinct client IDs prevent one board replacing another."),
        ("Private overrides", "Optional gitignored esp32/include/config.h; public defaults in mqtt_config.h. Credentials are never printed or included in evidence."),
    ], [125,374])
    p("VS Code Wokwi includes a private gateway; no inbound port-forward rule is needed for outbound MQTT. A free browser public gateway cannot reach the PC's local broker. The expected hostname and compiled paths were checked, and delivery through the simulation path was subsequently operator-observed; no independently archived runtime trace is available. [2,3]")
    p("Open smart-parking-esp32-01.code-workspace, -02 or -03 in separate VS Code windows. Each puts its local simulations/esp32-0N folder first, then the source repository. Its wokwi.toml uses ../../.pio/build/esp32_0N/firmware.bin and the matching ELF. Use Wokwi: Start Simulator or Play on the local one-board diagram, never on the three-board overview.")
    p("The existing Windows Mosquitto service configuration was not changed. Read-only observation identified Mosquitto 2.1.2. The service config hash is retained in the evidence metadata for comparison. A broker-side subscriber receiving synthetic test traffic does not establish private-gateway reachability.")

    page(6, "Telemetry schema and example")
    table(["Field", "Meaning"], [
        ("schema_version / device_id", "Version 1; esp32_01, esp32_02 or esp32_03."),
        ("sequence / uptime_ms", "Acknowledged-send counter and device millis at payload creation; both can restart/wrap."),
        ("timestamp / clock_synced", "Root publication time in UTC and valid-clock indicator. Null/false before wall time is usable."),
        ("slots[]", "Exactly four uniquely assigned slot objects, containing slot_id, distance_cm, occupancy_status and measurement timestamp."),
        ("distance_cm / occupancy_status", "Finite valid range value with OCCUPIED/VACANT, or null with UNKNOWN."),
    ], [148,351])
    p("<b>Illustrative only: no production payload was captured in the initial observation windows.</b>")
    code('{\n  "schema_version": 1,\n  "device_id": "esp32_01",\n  "sequence": 0,\n  "timestamp": null,\n  "clock_synced": false,\n  "uptime_ms": 1000,\n  "slots": [\n    {"slot_id":"P1","distance_cm":10.0,\n     "occupancy_status":"OCCUPIED","timestamp":null},\n    {"slot_id":"P2","distance_cm":100.0,\n     "occupancy_status":"VACANT","timestamp":null},\n    {"slot_id":"P3","distance_cm":null,\n     "occupancy_status":"UNKNOWN","timestamp":null},\n    {"slot_id":"P4","distance_cm":100.0,\n     "occupancy_status":"VACANT","timestamp":null}\n  ]\n}')
    p("After asynchronous SNTP establishes usable wall time, timestamps use ISO 8601 UTC, for example 2026-11-10T12:00:00Z. The initial snapshot can have null or mixed slot timestamps if synchronization occurs during a scan. Do not treat uptime as Unix time, or claim NTP success merely because the field exists.")

    page(7, "Executed testing procedure and commands")
    p("The operator selected the VS Code route because no CLI token was configured. The agent did not control the browser or IDE. The operator reported three running simulations and later supplied short Wi-Fi/MQTT connection statements; exact per-board publication output was subsequently requested. The operator later explicitly reported subscriber delivery on all three topics with P1-P12. That statement is archived separately; no Serial lines or production payloads have been invented.")
    sub("Read-only production captures")
    code('.\\.venv\\Scripts\\python.exe esp32/tools/verify_mqtt_runtime.py `\n  --duration 90 --label baseline `\n  --output reports/evidence/phase1_mqtt_baseline.json\n\n.\\.venv\\Scripts\\python.exe esp32/tools/verify_mqtt_runtime.py `\n  --duration 60 --label operator_confirmed_running `\n  --output reports/evidence/phase1_mqtt_running.json\n\n.\\.venv\\Scripts\\python.exe esp32/tools/verify_mqtt_runtime.py `\n  --duration 45 --label operator_reported_mqtt_connected `\n  --output reports/evidence/phase1_mqtt_connected.json')
    p("The first two captures also supplied explicit expected VACANT states for P1-P12, matching the configured 100 cm starting distances. The observer subscribes to exactly the three production topics at QoS 1, ignores retained packets and exact duplicate identities, validates the documented JSON fields, and saves only whitelisted telemetry fields. It never publishes to production topics or overwrites an evidence file.")
    sub("Broker isolation and health checks")
    code('.\\.venv\\Scripts\\python.exe esp32/tools/check_mqtt.py --smoke --timeout 5')
    p("This passed using three Python publishers and one subscriber on a unique smartparking/validation/phase1/... namespace. Fixtures were explicitly labelled local_python_probe_not_esp32. A separate read-only $SYS subscription checked broker version, uptime and connected-client count while the production observer was open. No service restart or configuration edit was made.")
    p("Diagnostic firmware builds: esp32_01, esp32_02 and esp32_03 all SUCCESS; each uses 48,636 bytes RAM and 997,633 bytes flash. All three diagnostic host test programs compiled with --compile-only; they were not executed because of prior Windows Application Control blocks. Earlier circuit/config checks and an initial ESP32-01 host run passed. These results do not substitute for simulation execution. The interrupted later diagnostic-restart capture produced no saved record and supplies no test result.")

    page(8, "Actual production-topic observations")
    capture_rows=[]
    for path, data in captures:
        stamp=datetime.fromisoformat(data['started_at_utc'].replace('Z','+00:00')).astimezone(IST).strftime('%H:%M:%S IST')
        capture_rows.append((path.stem.replace('phase1_mqtt_',''), stamp,
                             str(data['requested_duration_seconds'])+' s',
                             ' / '.join(str(data['devices'][f'esp32_{i:02d}']['valid_unique_messages']) for i in range(1,4))))
    table(["Capture label", "Start (10 Nov)", "Requested window", "Messages: 01 / 02 / 03"], capture_rows, [157,112,104,126])
    p("These are separate windows, not one continuous run. Every capture records its actual elapsed wall time and UTC start/end times in the JSON evidence. A zero count means no fresh valid production payload was observed in that window; it does not establish the precise cause.")
    table(["Check", "Result", "Interpretation"], [
        ("Observer -> broker CONNACK", "PASSED", "Successful connection acknowledgements were recorded."),
        ("Three production SUBACKs", "PASSED", "Broker granted QoS 1 subscriptions for all three topics."),
        ("Python broker pub/sub", "PASSED", "Three synthetic publishers worked in an isolated validation namespace."),
        ("Three-topic delivery / P1-P12", "OPERATOR<br/>OBSERVED", "Operator saw all three production topics while simulations ran simultaneously; no original payload archive."),
        ("Archived production payloads", "NOT CAPTURED", ", ".join(f"{k}: {v}" for k,v in totals.items())),
        ("Periodic firmware delivery", "UNVERIFIED", "No production intervals can be computed without messages."),
        ("Actual timestamps / NTP", "UNVERIFIED", "No production timestamps captured in the initial windows."),
        ("Occupancy transitions", "UNVERIFIED", "No received state changes correlated with operator distance changes."),
        ("MQTT reconnect / recovery", "NOT RUN", "No controlled outage and recovery evidence was supplied."),
    ], [162,104,233])
    note("<b>Acceptance remains open.</b> Delivery is operator-observed, while the saved earlier windows contain no messages. Neither source proves the remaining detailed tests passed. These evidence classes are intentionally preserved separately.")

    page(9, "Broker diagnostics and later observation")
    values=system.get('values',{})
    table(["System topic", "Observed value", "Context"], [
        (key, entry['value'], "Read-only broker diagnostic; retained flag: "+str(entry['retained'])) for key,entry in values.items()
    ], [205,150,144])
    p("The broker reported two connected clients while two diagnostic observers were open. That count is consistent with the diagnostic subscribers alone; it does not support three additional connected ESP32 clients at that observed moment. Broker statistics update periodically, so this is supporting evidence rather than an exact per-client trace.")
    sub("What can and cannot be concluded")
    p("Confirmed: the local broker responds, accepts the expected subscriptions and forwards isolated test messages. The later operator observation establishes reported subscriber delivery, but not an independently archived broker route, loaded binary identity, exact JSON fields or the reason earlier observation windows were empty.")
    p("Possible causes include a stale simulation image, a topic or broker mismatch, a gateway route problem, or a connected client that is not reaching its publish path. The later operator observation does not retrospectively diagnose the earlier empty windows. These are hypotheses. No circuit rewrite, broker reconfiguration or invented payload is justified by a zero-message observation alone.")
    sub("Serial evidence required next")
    p("For every board, capture the startup banner, assigned slot lines, Wi-Fi status, exact MQTT-connected topic, publish-check gate, publish-attempt result and acknowledged JSON payload. An unedited copied log is preferred. Board names and slot IDs should agree with the selected workspace and build target. Credentials must not be included.")

    page(10, "Timestamp, state and reconnect acceptance")
    sub("Steady-state telemetry")
    p("Run all three independent simulations and observe for at least 60-90 seconds after connection. Require at least three fresh unique messages per device, exactly P1-P4 / P5-P8 / P9-P12, valid JSON, correct UNKNOWN/null rules and no foreign slots. Compare wall-clock arrival intervals with device uptime increments. Approximately five seconds is the target, but simulator speed can stretch wall time; report both measurements.")
    sub("UTC and sensor states")
    p("Permit explicit null timestamps during startup. Then require multiple fully timestamped messages, UTC Z formatting, sensible ordering of measurement and publication times, and comparison with receiver UTC time. A non-null field alone is not proof that NTP or clock accuracy passed. Change P1, P5 and P9 individually from 100 cm to 10 cm and back, preserving the other slots. Correlate received transitions with operator changes. Test timeout/UNKNOWN only in a disposable fault-injection copy, not by damaging the verified circuit.")
    sub("Controlled MQTT recovery, after baseline")
    p("One non-service method is a brief test-client connection using a selected ESP32's exact client ID. MQTT replacement disconnects that single ESP32 session; immediately disconnect the probe and observe the ESP32 reconnect and resume fresh production messages. Record the induced event time, Serial logs, sequence/uptime behavior, delivery gap and recovery time. Do not keep the duplicate client connected or cause a reconnect contest. This test has not been performed or operator-confirmed in this audit.")
    p("A simulator-side Wi-Fi interruption is a separate test and remains unverified. Do not treat a broker-client reconnect as proof of Wi-Fi recovery. Restarting the shared Windows Mosquitto service may affect other clients and is not necessary for the first targeted recovery test. Keep service settings unchanged unless a diagnosed routing/authentication need is explained and authorized.")
    note("<b>Backend gate:</b> Three-board delivery has operator confirmation; timestamp/state behavior and controlled recovery remain open acceptance items. This report does not authorize starting FastAPI or SQLite.")

    page(11, "Troubleshooting and continuation commands")
    table(["Observation", "Next check"], [
        ("No Wi-Fi connected line", "Confirm latest image, Wokwi-GUEST, channel 6, simulator network and licensed private-gateway availability."),
        ("Wi-Fi connected; MQTT fails", "Check host.wokwi.internal:1883 in the effective firmware, broker availability and authentication. Do not replace it with ESP32 localhost."),
        ("MQTT connected; no publish attempt", "Look at publish-check connected/due gates and whether all four measurements complete."),
        ("Publish attempt fails", "Capture library transport/return codes and broker-side symptoms. Do not label the attempted JSON delivered."),
        ("Acknowledged payload; observer sees none", "Compare exact topic and broker endpoint, selected workspace, loaded firmware image and duplicate client IDs."),
        ("All slots UNKNOWN at 100 cm", "Inspect ECHO pin paths and limited resistor simulation before claiming occupancy detection passed."),
        ("Clock remains unsynchronized", "Check gateway DNS/UDP internet access to SNTP servers; retain null timestamps instead of fabricating dates."),
    ], [192,307])
    sub("Rebuild only if firmware/configuration changed")
    code("$env:PLATFORMIO_CORE_DIR = Join-Path (Get-Location).Path 'tmp\\platformio-core'\n.\\tmp\\platformio-venv\\Scripts\\python.exe -m platformio run --project-dir esp32")
    sub("Capture a new window without replacing earlier results")
    code('.\\.venv\\Scripts\\python.exe esp32/tools/verify_mqtt_runtime.py `\n  --duration 90 --label after_serial_diagnosis `\n  --output reports/evidence/phase1_mqtt_after_diagnosis.json')
    p("Use a new evidence filename for every test window. Keep the failed/empty captures: they explain why a later fix was needed and prevent retrospective replacement of earlier results with successful fixtures. The observer is read-only; no test tool should spoof ESP32 traffic on production topics to manufacture a pass.")

    page(12, "Evidence manifest and project references")
    table(["Evidence file", "Purpose"], [(p.name, d.get('label', d.get('source', 'environment / operator / artifact record'))) for p,d in records], [254,245])
    sub("Firmware artifact record")
    for artifact in diagnostic.get('artifacts',[]):
        p(f"<b>{artifact['board']}</b>: {artifact['bytes']:,} bytes; SHA-256:<br/>{artifact['sha256']}", "small")
    p("Hashes identify the recorded binary files; they do not prove that a running simulator loaded those files. These are the diagnostic build hashes; the initial baseline hashes remain in phase1_environment.json. The operator observation was not tied to a verified binary hash. Do not embed API keys, passwords, personal IDE state or unrelated logs in committed reports.", "small")
    sub("Primary external references")
    refs=[
        ("1", "Wokwi FAQ: multiple microcontrollers", "https://docs.wokwi.com/faq"),
        ("2", "Wokwi VS Code project configuration", "https://docs.wokwi.com/vscode/project-config"),
        ("3", "ESP32 Wi-Fi and gateways", "https://docs.wokwi.com/guides/esp32-wifi"),
        ("4", "Wokwi resistor simulation limits", "https://docs.wokwi.com/parts/wokwi-resistor"),
        ("5", "HC-SR04 simulation and controls", "https://docs.wokwi.com/parts/wokwi-hc-sr04"),
        ("6", "Arduino MQTT library", "https://github.com/256dpi/arduino-mqtt"),
        ("7", "Wokwi CLI usage and token prerequisite", "https://docs.wokwi.com/wokwi-ci/cli-usage"),
    ]
    for number,title,url in refs:
        p(f'[{number}] {title}: <link href="{url}" color="#007F86">{url}</link>', "small")
    p("Repository continuation files: esp32/MQTT.md, esp32/README.md, the three board workspaces, esp32/tools/verify_mqtt_runtime.py and reports/evidence/. This PDF is generated by reports/generate_phase1_report.py using ReportLab, without modifying the project's Python dependency snapshot.", "small")

    def furniture(canvas, doc):
        width,height=doc.pagesize
        canvas.setStrokeColor(TEAL);canvas.setLineWidth(1.6);canvas.line(48,height-39,width-48,height-39)
        canvas.setFont("BoldFont",8);canvas.setFillColor(NAVY);canvas.drawString(48,height-28,"SMART PARKING / PHASE 1 MQTT")
        canvas.setStrokeColor(colors.HexColor("#D9E4EA"));canvas.setLineWidth(.5);canvas.line(48,39,width-48,39)
        canvas.setFont("BodyFont",7.5);canvas.setFillColor(INK);canvas.drawString(48,25,"10 Nov 2026 | Evidence-led runtime audit | No backend integration")
        canvas.drawRightString(width-48,25,str(doc.page))
    doc=SimpleDocTemplate(str(OUTPUT),pagesize=(595.28,841.89),leftMargin=48,rightMargin=48,topMargin=59,bottomMargin=54,
                          title="Phase 1 MQTT Integration - Smart Parking Runtime Audit",author="Smart Parking Project")
    doc.build(story,onFirstPage=furniture,onLaterPages=furniture)
    print(OUTPUT)


if __name__ == "__main__":
    main()
