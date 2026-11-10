# Phase 1 MQTT audit

[Comprehensive PDF](phase1_mqtt_integration.pdf) covers the three-board, twelve-slot
architecture, configuration, telemetry contract, commands, results and continuation.

## Verification status

- **Build evidence:** all three diagnostic firmware targets compiled successfully.
- **Saved test evidence:** local broker connection/subscription checks and isolated
  Python publisher smoke test passed. Three saved production windows (90/60/45 s)
  received zero production messages; those results remain unchanged.
- **Operator-observed delivery:** the operator later confirmed all three Wokwi
  simulations running simultaneously and telemetry arriving on all three production
  topics, with P1-P4, P5-P8 and P9-P12 respectively. No original screenshot, raw
  production payload or Serial log remains available. This is not independently
  archived runtime evidence.
- **Still unverified:** exact production JSON validation, measured cadence,
  timestamp/NTP accuracy, occupancy transitions and controlled reconnection.
- **Host tests:** diagnostic programs compiled for all boards; execution was not
  attempted after earlier Windows Application Control blocks. A complete final
  host runtime pass is not claimed.

`evidence/phase1_operator_observation.json` records the operator statement only.
Other JSON files retain earlier capture results, broker diagnostics, environment
metadata and diagnostic build hashes. The interrupted diagnostic-restart capture
left no saved evidence and is not counted as a result. No fabricated Serial logs
or production payload fixtures are included.

## Reproduce

Run from the repository root with the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe esp32/tests/test_circuits.py
.\.venv\Scripts\python.exe esp32/tools/run_host_tests.py --compile-only
.\.venv\Scripts\python.exe esp32/tools/check_mqtt.py --smoke --timeout 5
.\.venv\Scripts\python.exe esp32/tools/verify_mqtt_runtime.py `
  --duration 90 --label followup `
  --output reports/evidence/phase1_mqtt_followup.json
```

The final command requires running simulations and a new output filename. It
only subscribes; smoke fixtures use an isolated validation namespace.
See [Serial capture guidance](../esp32/MQTT.md#serial-diagnostics-and-saved-capture).

Generate the PDF with a Python environment containing ReportLab:

```powershell
python reports/generate_phase1_report.py
```

The generator uses Windows Arial and Consolas fonts. Report generation reads the
evidence files; it does not run simulations or promote operator statements into
independent test passes. PDF dependencies were provided by the bundled tooling;
the project's dependency snapshot and virtual environment were preserved.

Mosquitto configuration, circuits and unrelated modules were unchanged. FastAPI
and SQLite integration have not started. Detailed acceptance tests remain open.
