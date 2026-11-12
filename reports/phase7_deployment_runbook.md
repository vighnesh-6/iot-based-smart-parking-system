# Phase 7 - zero-cost deployment runbook

Provisioning is gated by complete local and Linux readiness checks, authenticated
account access and a card-free Free-plan confirmation in each provider console.
This document is a runbook, not evidence that deployment has occurred. Actual
status belongs in the Phase 7 evidence and PDF. Never select a paid plan, enter a
payment method, enable overages or weaken certificate/freshness checks.

## Architecture and preserved local path

Wokwi ESP32 clients -> EMQX Serverless MQTT/TLS -> Render Free FastAPI -> Neon Free
PostgreSQL. Streamlit Community Cloud calls FastAPI over authenticated HTTPS.
The cloud frontend uses the existing in-process Phase 4 model adapter. All model
files, synthetic datasets, notebooks, research results and existing PDFs remain
unchanged. The separate Persistence-only endpoint retains its twelve-fresh-slot
gate. SQLite remains the default locally and its original file is never replaced.

## Prerequisites and verification

The standard GitHub-hosted Ubuntu24 runner is free for this public repository.
The workflow `.github/workflows/phase7-readiness.yml` installs dependencies only
on the disposable hosted runner. It runs real PostgreSQL tests, backend/dashboard/
ML regressions, static circuit tests, C++ host regressions, six firmware builds
and an actual unchanged-model reload/prediction on a labelled synthetic row.
Local Windows PostgreSQL skips are not runtime passes. First-run image/version
failures must remain recorded rather than being promoted to test successes.

## Account and cost gate

1. Sign in to each provider only on its official website. Never send credentials
   in chat. Stop if a card, authorization hold, paid upgrade or marketplace
   subscription is required. Existing GitHub Git authentication is not equivalent
   to Render, Neon, EMQX or Streamlit account authorization.
2. Use Neon **Free**, Render **Hobby + Free web service**, Streamlit **Community
   Cloud**, and EMQX **Serverless with Spend Limit exactly 0**. Do not enable paid
   add-ons or automatic upgrades. No custom domain is needed.
3. Verify the displayed plan, remaining quotas and billing configuration before
   creating a resource. Published free-plan terms do not prove account eligibility.

Official references (audited November 2026):

- https://render.com/docs/free
- https://neon.com/docs/introduction/plans
- https://docs.emqx.com/en/cloud/latest/deployments/spend_limit.html
- https://docs.emqx.com/en/cloud/latest/deployments/port_guide_serverless.html
- https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app

## Deployment sequence

1. Create one Neon Free project/database. Keep connection details private. The
   application uses a dedicated `smartparking` schema; unknown existing schemas
   are refused rather than reset. PostgreSQL TLS is forced to verify-full with
   the system trust store. Local SQLite is not the cloud database.
2. Create EMQX Serverless with spend limit 0. Configure authenticated MQTT clients
   and topic permissions: boards publish only the three existing telemetry topics;
   the cloud backend subscribes to those topics. Use the assigned broker hostname,
   port8883 and its documented public CA; do not disable hostname verification.
3. Create the Render Free service from `render.yaml`, with one worker. Start with
   no cloud ESP32 publishers while importing history. Configure secrets privately:

   | Setting | Value/source |
   |---|---|
   | `DEPLOYMENT_MODE` | `cloud` |
   | `DATABASE_URL` | Private Neon connection URL with verified TLS |
   | `DATABASE_EXPECTED_HOST` | Exact hostname confirmed inside only the separate `smart-parking` Neon project |
   | `MQTT_TLS`, `MQTT_PORT` | `true`, `8883` |
   | `MQTT_HOST` | Assigned EMQX hostname |
   | `MQTT_CLIENT_ID` | `smartparking-cloud-backend` |
   | `MQTT_USERNAME`, `MQTT_PASSWORD` | Private backend MQTT identity |
   | `API_BEARER_TOKEN` | Render generates a private random256-bit value from the Blueprint; later copy it only into Streamlit's private secrets |
   | `STALE_SECONDS` | `30` (unchanged) |

   `/livez` is public minimal process liveness; all other routes require the token
   when configured. `/health` provides authenticated database/MQTT diagnostics.
   Cloud startup rejects a connection URL whose hostname differs from
   `DATABASE_EXPECTED_HOST` before opening any database connection. Confirm the
   Neon project heading is `smart-parking` when copying both values; never open,
   connect to, or reuse credentials from the unrelated Sector Rotation project.
   A pooled hostname and its direct hostname are different: copy the exact host
   used by the chosen connection URL into the expected-host setting. If Neon adds
   `sslmode=require`, change that parameter privately to `sslmode=verify-full`.
4. Copy the recognized SQLite history without installing a driver locally:

   ```powershell
   .\.venv\Scripts\python.exe -B -m backend.tools.import_sqlite_history --source "$env:LOCALAPPDATA\SmartParking\parking.db" --export-sql tmp/phase7_history_import.sql
   ```

   The tool opens SQLite read-only, checks its identity/version and unchanged file
   hash, and refuses to overwrite the export file. Run the generated transaction
   in the authenticated Neon SQL editor after application schema initialization,
   before enabling cloud publishers. It refuses a nonempty destination. It copies
   existing IDs, receipt/measurement timestamps, sequences, fingerprints, history
   and current pointers, preserving gaps and stale states. Compare2252 source
   observations/563 messages against the current source snapshot, not a guessed
   future count. The export is private runtime data under ignored `tmp/`; never
   commit or upload it to a public repository. A driver-based exact row-comparison
   path also exists for an approved runtime already containing psycopg.
5. Deploy `dashboard/app.py` from the existing public GitHub repository to Streamlit
   Community Cloud using Python3.12 and `dashboard/requirements.txt`. Configure
   root-level Streamlit secrets privately: `API_BASE_URL` is the Render HTTPS URL,
   `API_BEARER_TOKEN` matches the backend, and `PREDICTION_ADAPTER="in_process"`.
   Do not set Windows `ML_PYTHON` or machine-specific artifact paths in the cloud.
6. Configure ignored `esp32/include/config.cloud.h` using the example. Keep local
   `config.h` unchanged. Build the corresponding `esp32_01_cloud`, `esp32_02_cloud`
   or `esp32_03_cloud` target. Never commit configured headers or credential-bearing
   firmware binaries. Sensor logic, GPIOs, topics, JSON schema and publishing
   cadence remain unchanged. Simulation setup must point to the cloud target's
   firmware and the byte-identical verified per-board diagram. After building,
   run `.venv/Scripts/python.exe -B esp32/tools/prepare_cloud_simulation.py --board 1`
   (use2 or3 for other boards). It creates an ignored folder under
   `tmp/phase7-cloud-simulations/`, refuses to overwrite existing folders and leaves
   local workspaces/circuits untouched. Open that folder in only one additional
   simulator window at a time. Cloud builds reuse each board's existing MQTT
   library cache; never install new tooling or dependencies on the laptop.
7. Verify real production-topic messages and exact PostgreSQL persistence for all
   boards. Mark sequential evidence as sequential. Test auth failures, reconnects,
   actual dashboard loading, history filters/gaps, refresh, cloud cold starts and
   missing/stale-data behavior. Record actual URLs and source commit. A successful
   synthetic model reload is not a successful live sensor forecast.

## Free-tier and scientific limits

- Wokwi telemetry stops when the laptop/simulation is off or paused. The cloud
  deployment does not make simulated hardware autonomous. Historical data remains
  historical; no fake readings, timestamp refresh or retained-message replay is
  used to pretend it is live.
- Render sleeps after15 minutes without inbound HTTP/WebSocket activity, taking
  its subscriber offline. MQTT traffic on an outbound broker connection is not an
  always-on service guarantee. Wake the API and allow reconnection before a demo.
  Do not add artificial keep-alive services. Free Render filesystem changes are
  ephemeral; PostgreSQL provides persistence. Broker queue redelivery is subject
  to provider/session limits and does not guarantee lossless continuous capture.
- Neon Free currently includes1GB storage,100CU-hours and5GB transfer per project;
  compute scales to zero after5 idle minutes. At0.25CU,100CU-hours is400 active
  hours, not a full month of continuous operation. Free restore history is limited.
- EMQX's free1GB includes inbound/outbound traffic. At five seconds per message,
  three boards plus one subscriber and a captured543-byte payload imply about
  1.69GB in30 continuous days before overhead. Use bounded demonstrations and
  monitor quotas. At spend limit0, exhaustion suspends service; do not upgrade.
- Streamlit sleeps after12 idle hours and has shared resource limits. Render,
  database and frontend cold starts can produce temporary unavailability. The UI
  explains wake-up failures and never substitutes synthetic live values.
- A Persistence-only live forecast requires all12 fresh, known, timestamped slots
  within the same30-second window. Sequential tests do not automatically meet
  that requirement. The unchanged full37-feature interface independently requires
  10081 complete minute rows. Cloud hosting removes neither scientific constraint.

## Closure evidence

Only mark deployment complete after the actual cloud checks pass and a working
public Streamlit URL is observed. Preserve original artifacts and SQLite hashes;
record blocked tests honestly. Generate and visually inspect the Phase7 PDF.
Keep one meaningful file per commit, and push through existing Git authentication.
