# Phase 5 acceptance: verified local implementation, cloud deployment pending

Evidence: [actual verification](evidence/phase5_dashboard_verification.json),
[final PDF/preservation checks](evidence/phase5_final_checks.json),
[comprehensive PDF](phase5_streamlit_dashboard.pdf),
[local and deployment instructions](../dashboard/README.md).

| Requirement | Result | Evidence / qualification |
| --- | --- | --- |
| All 12 slots, board assignment and numeric ordering | PASS | Snapshot tests and actual AppTest: 12 slot cards |
| Occupied/vacant/unknown counts | PASS | Existing statistics helper; same snapshot as cards; fresh/stale/unseen tests |
| Stale, missing, sensor UNKNOWN and future receipt handling | PASS | Effective unknown states and diagnostics; no silent vacancy |
| API_BASE_URL-only backend access | PASS | GET-only client tests; no direct frontend SQLite/MQTT access |
| API errors, timeouts and loading states | PASS | Client tests, AppTest outage behavior, spinner branches and explicit errors |
| Automatic/manual refresh controls | PASS LOCALLY | AppTest verifies interval registration, disabling and manual reruns; actual browser wall-clock timing is unverified |
| Historical trends, coverage and slot filters | PASS | As-of/gap tests, Plotly rendering, filter invalidation and actual API history extraction |
| Bounded pagination and explicit truncation | PASS | Fixed reception upper bound, row/time caps and invalid-page tests |
| Causal feature reuse | PASS | Frozen engineer_features reused; complete-history fixture agrees exactly; gaps rejected |
| Selected saved model and bounded prediction interface | PASS | Frozen bundle checksum/reload; Persistence, 15-minute horizon and 0-12 contract |
| Windows subprocess adapter | PASS | Actual approved-interpreter prediction and synthetic UI interaction |
| In-process adapter | PASS ON LOCAL WINDOWS | Actual execution in approved ML runtime; matches subprocess result; Linux/cloud compatibility remains unverified |
| Complete-history live forecast code path | PASS WITH FIXTURE | Explicit in-memory fixture and actual saved model; this is not production telemetry evidence |
| Production live 15-minute forecast | UNAVAILABLE / NOT PASSED | 12 effective unknown slots and insufficient valid history; no forecast fabricated |
| Synthetic retrospective review | PASS | Existing frozen validation row, actual adapter execution, explicit synthetic labels |
| Three-model MAE/RMSE/R2 comparison | PASS | Six frozen validation/test score sets displayed; no new selection or fitting |
| Dashboard tests | PASS | 32 tests, no failures/errors/skips |
| Existing backend regression tests | PASS | 43 tests; private temporary databases only |
| Existing ML regression tests | PASS | 42 tests in approved native runtime; small test fixtures do not overwrite frozen model |
| Actual local HTTP server | PASS | / and /_stcore/health return 200 on 127.0.0.1:8501 |
| Phase 1-4 source, data, models, notebooks and PDFs | PASS | All 119 protected tracked file hashes unchanged |
| Existing environments and security settings | PASS | No Phase 5 installs/removals/policy changes; frozen pins preserved; isolated ML inventory unchanged |
| Older root requirements vs current project freeze | DIFFERENCE DOCUMENTED | Existing Jupyter additions predate Phase 5; exact match remains false, not concealed or reset |
| Comprehensive Phase 5 PDF | PASS | 11 pages, rendered with Poppler; every page visually inspected; pages 7/8/11 also inspected individually |
| Separate deployment instructions | PASS | Frontend, FastAPI, persistent SQLite, MQTT and ML each documented |
| Actual cloud deployment | PENDING PHASE 6 | No hosting, cloud install, public exposure, network reconfiguration or database migration performed |
| Real browser layout and timed auto-refresh | UNVERIFIED | Browser/Computer Use remained off; AppTest and local HTTP are the archived UI evidence |
| One meaningful file per commit and one push | VERIFIED AT DELIVERY | Check commit scopes, remote HEAD and clean Git status after all local checks |

Local software acceptance passes within these explicit limits. Production
telemetry completeness, production live prediction, browser timing and cloud
operation are not marked passed. Initial sandbox-test and strict historical
freeze-check failures remain archived; no test output or live reading is invented.
