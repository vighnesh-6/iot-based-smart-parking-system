# Phase 6 - Essential local integration acceptance

Authoritative evidence: [final acceptance](evidence/phase6_final_acceptance.json).
Report: [Phase 6 PDF](phase6_end_to_end_integration_and_deployment.pdf).

| Requirement | Result | Evidence / boundary |
| --- | --- | --- |
| ESP32-01, P1-P4 | PASS | 60.032s capture; 8 messages; 32 exact SQLite observations |
| ESP32-02, P5-P8 | PASS with timing limitation | 90.032s; 16 messages; 64 observations; one repeated sequence retained as history-only |
| ESP32-03, P9-P12 | PASS | 90.015s; 16 messages; 64 observations |
| Topic/device/JSON/slot assignments | PASS | Strict backend payload parser plus exact four-row database comparison |
| Nominal periodic delivery | PASS with limitation | Median receipt interval about 5s; ESP32-02 was not uninterrupted |
| Existing history | PASS | Original IDs 1-38 messages and 1-152 observations remain; integrity/foreign keys pass |
| Individual history graph | PASS | Exact receipt timestamps, visible markers, UNKNOWN/gap separators; actual P3 API/AppTest |
| Total occupancy | PASS conservative behavior | Requires all 12 known slots; sequential runs do not establish complete live snapshots |
| Freshness | PASS automated checks | Backend flags preserved; old/future measurement timestamps cannot appear fresh; missing clock labelled |
| Cards/counts/filter/errors/refresh controls | PASS automated checks | Dashboard tests plus actual API/AppTest; no browser verification claim |
| Phase 1-5 frozen research artifacts | PASS | Protected tracked files, PDFs, datasets/models/notebooks unchanged |
| All boards simultaneously | UNVERIFIED | Explicitly replaced by sequential testing for the 8 GB laptop |
| Persistent continuous Serial logs | NOT ESTABLISHED | Terminal output observed; raw MQTT payloads archived separately |
| Occupied/UNKNOWN physical transitions and controlled reconnect | UNVERIFIED | Captured states were VACANT; no controlled outage performed |
| Genuine live prediction | UNAVAILABLE | Frozen 37-feature interface requires complete seven-day minute history |
| Linux/cloud hosting | DEFERRED | No installations, credentials or provisioning; no 24/7 claim |
| Authenticated final push | CONSTRAINED | Latest user instruction prohibits using any credentials |

The unchanged legacy capture utility expects three concurrent boards. Its top-level
`capture_checks_passed=false` is expected for single-board captures. The separate
`phase6_sequential_esp32_0N_persistence.json` files contain per-board acceptance.
ESP32-02's strict uninterrupted cadence is also false and remains documented.

No synthetic observations were injected into production topics or SQLite. Test
fixtures are isolated. No firmware, circuits, topics, broker configuration,
backend code, database schema, models or research data were changed.

Use a new output filename on every verification run. Never reset the live database.
The final PDF includes the commands, architecture, observed failures and limitations.
