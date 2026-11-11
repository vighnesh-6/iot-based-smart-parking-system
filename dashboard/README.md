# Phase 5: Local-first, cloud-ready Streamlit dashboard

The same `dashboard/app.py` reads the existing FastAPI API locally or at a
configured HTTPS address. The frontend never opens SQLite, subscribes to MQTT,
changes firmware, or writes observations. Phase 1-4 source, datasets, notebooks,
models and PDFs remain frozen. No new notebook or duplicate dataset is needed.

## Local startup (existing environments, no installation)

Keep the existing backend running on port 8000. Its original startup command is
in `backend/README.md`; do not start a second instance using the same client/DB.
From the repository root, configure only the dashboard process:

```powershell
$env:API_BASE_URL = 'http://127.0.0.1:8000'
$env:PREDICTION_ADAPTER = 'subprocess'
$env:ML_PYTHON = "$env:LOCALAPPDATA/SmartParking/ml-runtime/Scripts/python.exe"
$env:PYTHONDONTWRITEBYTECODE = '1'
.\.venv\Scripts\python.exe -B -m streamlit run dashboard/app.py `
  --server.address 127.0.0.1 --server.port 8501 --server.headless true `
  --browser.gatherUsageStats false
```

Visit `http://127.0.0.1:8501` manually. No browser automation is required or used.
The interpreter path above is an operator-supplied Windows example, not a path
embedded in the app. The dashboard defaults to portable in-process prediction;
the subprocess setting handles this laptop's separate approved native runtime.
The original `.venv`, isolated ML runtime and frozen root requirements are unchanged.
If a package/native import is blocked, stop and obtain an approved compatible
environment; do not disable policy, create trust exceptions or relocate DLLs.

## Architecture and configuration

```text
ESP32 -> Mosquitto -> unchanged FastAPI + external SQLite
                              |
                            HTTP GET
                              v
Streamlit -> ApiClient -> API_BASE_URL
    |
    +-> receipt-time history -> frozen ml.features.engineer_features
    +-> predict(features, settings)
          +-> in_process -> frozen load_predictor(...).predict(...)
          +-> subprocess -> configured Python -> the same frozen interface
    +-> frozen model_results.json -> synthetic evaluation table
```

`Settings.from_env()` accepts environment variables and an optional TOML file
selected by `DASHBOARD_CONFIG`. Environment variables take precedence. See
`config.example.toml`. No `.env` file is silently loaded or modified.

| Setting | Default / purpose |
| --- | --- |
| `API_BASE_URL` | `http://127.0.0.1:8000`; all backend requests originate here |
| `API_BEARER_TOKEN` | Empty; optional Authorization header for a future secured API gateway |
| `PREDICTION_ADAPTER` | `in_process` or `subprocess` |
| `ML_PYTHON` | Required only for subprocess mode; approved interpreter executable |
| `API_TIMEOUT_SECONDS` | 3; maximum 30 per request |
| `REFRESH_SECONDS` | 10; supported options 5, 10, 15, 30, 60 |
| `DASHBOARD_STALE_SECONDS` | 30; conservative receipt-age ceiling, in addition to backend stale flags |
| `HISTORY_MAX_ROWS` | 20,000; configurable up to 2,000,000, subject to host memory and fetch-time cap |
| `MODEL_RESULTS_PATH` | Repository-relative `ml/artifacts/phase4/model_results.json` |
| `MODEL_BUNDLE_PATH` | Repository-relative `ml/artifacts/phase4/parking_models.joblib` |
| `DATASET_MANIFEST_PATH` | Repository-relative `ml/data/phase3_dataset_manifest.json` |

Paths are anchored to the code's repository location, not the working directory,
OneDrive or the developer's username. Deployment may override them with packaged
or mounted paths. The subprocess uses an argument list without a shell, a
30-second timeout, stdin JSON and the approved interpreter. The worker returns
bounded forecasts and model metadata. The UI does not reveal loader diagnostics
or credentials. Both adapters preserve the frozen selected Persistence model.

Only load this trusted joblib artifact. A checksum detects changes but does not
make an untrusted pickle safe. Model loading checks the recorded SHA256, and
the public frozen predictor validates the exact 37 named numeric features.

## Live data and forecast correctness

- Twelve slot cards are grouped into three boards. Known fresh readings alone
  count as Occupied/Vacant. Backend-stale, locally expired, unseen, missing or
  future-clock readings are effectively Unknown. Last-reported states remain
  diagnostic labels, never available spaces.
- Counts reuse `backend.db.statistics` on the same validated snapshot as the
  cards. `/stats` and `/health` appear as separate diagnostics; these independent
  GETs are not represented as one atomic snapshot. An API error removes fresh
  counts/forecasts and labels all cards unavailable.
- Auto refresh uses `st.fragment(run_every=...)` only while a session is active.
  It can be disabled, and manual refresh is available. History is loaded on
  demand and labelled with its frozen upper receipt-time bound.
- History uses timezone-aware `/history` reception filters, 1,000-row pages,
  a row cap and a 20-second paging budget (an in-flight request may add its
  configured timeout). Truncated history is explicit and cannot enable prediction.
- Minute reconstruction uses only accepted-current observations received at or
  before each minute origin. A backward as-of join has a per-slot age tolerance.
  UNKNOWN, absent and expired observations remain NaN. There is no interpolation
  or future/backward fill. Historical totals require all twelve known slots;
  a coverage trace shows missingness. Clock-synced device time is not assumed.
- The live forecast requires fresh current readings plus 10,081 complete minute
  snapshots (seven days and the origin). Slot sums are checked; signed minute
  transitions produce arrivals/departures. The existing feature function supplies
  all 37 predictors with Asia/Kolkata calendar semantics. It does not fit or write.
- The target time is the displayed minute origin plus exactly 15 minutes. The
  saved predictor clips output to 0-12 without rounding. Missing history yields
  unavailable, not fabricated features. Large high-frequency histories can hit
  the fetch cap; evaluate memory, row cap and backend query scalability before
  production. Raising a cap is not proof of completeness.
- The synthetic review uses one existing validation row and actual model
  execution. Its predicted and actual future totals are explicitly synthetic,
  separate from current telemetry. The frozen six validation/test score sets
  compare Persistence, Linear Regression and Random Forest. No retraining or
  test-based selection occurs; Persistence remains the validation-MAE winner.

## Test and verification commands

With the backend and local dashboard already running:

```powershell
$env:PHASE5_TEST_ML_PYTHON = $env:ML_PYTHON
.\.venv\Scripts\python.exe -B -m unittest discover -s dashboard/tests -v
.\.venv\Scripts\python.exe -B -m dashboard.tools.verify_local `
  --ml-python $env:ML_PYTHON --output tmp/phase5_followup.json
```

Use a new output path; evidence is never overwritten. The verifier runs dashboard
and existing backend suites, the ML suite in the approved interpreter, actual
GET-only API observations, AppTest interactions, dependency checks and optional
protected-file hash checks. Tests use explicit synthetic/in-memory fixtures and
private temporary databases; they do not publish to production MQTT or alter
the live database. Full-history forecast fixtures are not production evidence.

AppTest verifies rendered elements and interactions without browser control.
Local HTTP verifies the server page and health endpoint. Browser layout and
wall-clock refresh scheduling are not independently observed; refresh interval
registration, disabling and manual reruns are tested. See the Phase 5 evidence,
acceptance checklist and PDF for actual results and limits.

## Phase 6: separate deployment responsibilities (not deployed)

### Streamlit Community Cloud frontend

Select this repository, its intended branch and `dashboard/app.py` as entrypoint.
Use a compatible Python 3.12 environment and `dashboard/requirements.txt`, which
reuses the frozen ML pins. The entrypoint-adjacent dependency file avoids
modifying the frozen root snapshot. Native Linux wheel compatibility and the
saved bundle must be tested on the chosen host; Windows success is not a cloud pass.
Use `PREDICTION_ADAPTER="in_process"`, an HTTPS `API_BASE_URL`, and no `ML_PYTHON`.
Set root-level values through Community Cloud's private Secrets settings (not
Git). Streamlit exposes root-level secrets as environment variables. Keep any
gateway token private. Cloud `localhost` cannot address the Windows laptop.
The app's local filesystem is not a live-data persistence layer.

### Cloud-hosted FastAPI backend

Host the existing service separately with a reachable HTTPS address, suitable
timeouts and health monitoring. Preserve its one-worker MQTT/SQLite ownership
model. The current API is intended for trusted local access and has no built-in
public authentication/TLS. Configure a secured reverse proxy/API gateway before
public exposure; its bearer token can be passed by the existing frontend client.
Do not expose the unprotected development API. Any future backend changes need
their own approval; Phase 5 makes none. CORS is not needed for these server-side
Python HTTP calls, but public browser-based consumers would need separate review.

### Persistent database

Keep SQLite backend-owned on an absolute path on a durable volume, outside the
checkout and synchronized directories; configure `DATABASE_PATH` explicitly on
Linux. Preserve the recognized schema, delete-journal mode and single-writer
deployment assumptions. Configure backups, restore tests, disk monitoring and
retention. No SQLite file belongs in Community Cloud or Git. Switching database
engines or migrating schemas is outside this phase and requires approval.

### MQTT broker and ESP32 telemetry

Provision a reachable broker with access control, encrypted transport, firewall
rules, persistence/session policy and unique client IDs. Preserve topic names and
payload validation. `host.wokwi.internal` addresses the development PC through the
Wokwi private gateway; it is not a public broker name. Hosting changes must supply
the appropriate broker hostname and approved transport configuration separately.
Existing firmware/service configuration is untouched. Production delivery,
reconnection and all-device freshness must be tested independently on that network.

### Cloud-compatible model execution

Install compatible pinned dependencies into the hosted environment, verify model
and selection hashes, reload the trusted bundle and compare predictions against
the saved reference. Use the same in-process adapter, no retraining or feature
changes. Require sufficient valid API history; a synthetic demo is never a live
forecast. Plan memory/CPU and history retrieval costs. A future remote prediction
service is not implemented or required by the present two-adapter design.

## Troubleshooting and references

- API down/503: inspect URL, reachable HTTPS endpoint, backend health and network;
  the dashboard does not restart services or infer vacancy.
- Model unavailable locally: configure the approved interpreter for subprocess
  mode. Inspect worker diagnostics locally; do not weaken Application Control.
- No live forecast: inspect all twelve freshness states, history coverage and
  truncation. Do not replace missing observations with frozen synthetic rows.
- History is empty/gapped: reception-time filters differ from device measurement
  times; UNKNOWN/history-only/expired data do not form complete minute totals.
- Cloud import failure: deployment is unverified until supported native packages
  and bundle reload pass. Do not silently change frozen model versions.

Official references (reviewed 11 November 2026):

- [Streamlit fragments](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment)
- [Streamlit AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest)
- [Cloud file organization](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization)
- [Cloud dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)
- [Cloud secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)

The complete report is `reports/phase5_streamlit_dashboard.pdf`. Phase 6 hosting,
network/security configuration, durable infrastructure and cloud acceptance are pending.
