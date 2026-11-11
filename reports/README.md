# Smart Parking integration reports

## Phase 3: Historical Dataset Preparation

[Comprehensive Phase 3 PDF](phase3_historical_dataset_preparation.pdf) documents
synthetic generation, schema, calculations, causal features, target alignment,
chronological partitions, actual tests, storage and limitations.

- Raw: **80,640 one-minute rows**, 8 weeks, exactly P1-P12; all explicitly synthetic.
- Processed: **70,515 rows**, 37 predictors; train 49,360, validation 10,577,
  test 10,578, with 15-minute boundary purges and integer-rounded 70/15/15 allocation.
- **18 critical dataset checks and 21 software tests passed.**
- Dataset/model storage: **7,327,764 bytes (7.328 MB)**; no model trained.
- Processed format is deterministic gzip CSV: Windows Application Control blocks
  the existing PyArrow DLL. Parquet remains unverified; dependencies/security
  policy were preserved. Raw CSV and one compressed processed table are retained.
- Frozen Phase 1/2 implementation, reports/evidence, notebooks and live data remain unchanged.

See [ML instructions](../ml/README.md),
[acceptance checklist](phase3_acceptance_checklist.md),
[dataset validation](evidence/phase3_dataset_validation.json),
[actual test execution](evidence/phase3_tests.json), and
[final verification](evidence/phase3_final_checks.json).
These checks certify synthetic preparation, not real-world accuracy.

## Phase 2: FastAPI and SQLite

[Comprehensive Phase 2 PDF](phase2_fastapi_sqlite.pdf) documents architecture,
telemetry validation, atomic persistence, APIs, commands, actual tests and limits.
See [backend run instructions](../backend/README.md).

- Final automated suite: **43 tests passed**, no skips, failures or errors.
- Real local Mosquitto integration: **7 checks passed** using synthetic fixtures
  confined to unique validation topics and a private temporary database.
- Verified broker/backend transport reconnection, restart persistence,
  deduplication and a synthetic occupancy transition through actual HTTP.
- Production observation: subscriptions were active and health returned 200,
  but the 30-second window received **zero production observations**. Slots
  correctly remained unseen UNKNOWN. No new ESP32-to-API runtime pass is claimed.
- An expanded pre-fix test run caught a Paho exception-handler bug; failed
  evidence is preserved, and the corrected final run passed.
- Existing database files were never selected for automated tests or reset.
  A test-created unrelated database was rejected with unchanged content hash.
  ESP32, ML, dashboard, broker configuration and dependency snapshot stayed unchanged.

Evidence files:

| JSON | Meaning |
| --- | --- |
| phase2_unit_tests.json | Final 43-test run, test IDs, runner output and source hashes |
| phase2_pre_fix_tests.json | Earlier 43-test run with one failure before handler correction |
| phase2_broker_integration.json | Initial successful isolated broker/API test |
| phase2_final_integration.json | Successful seven-check integration rerun after final code correction |
| phase2_production_observation.json | Read-only 30-second production subscription observation |
| phase2_repository_checks.json | Circuit regression, protected paths, dependencies and broker config hash |

The JSON archives and PDF distinguish synthetic backend verification from actual
ESP32 telemetry. Broker session retention and firmware restart identity limits
remain documented; there is no exactly-once or lossless-outage claim.

Generate the Phase 2 PDF with the bundled tooling or another ReportLab-enabled
Python environment: `python reports/generate_phase2_report.py`.

## Phase 1 MQTT audit

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

At the Phase 1 milestone, Mosquitto configuration, circuits and unrelated modules
were unchanged, and FastAPI/SQLite had not started. Phase 2 is documented above;
detailed ESP32 acceptance tests remain open.
