# Phase 2: FastAPI and SQLite

The backend subscribes to the three existing `smartparking/esp32_0N/telemetry`
topics at QoS 1. `esp32_01` owns P1-P4, `esp32_02` owns P5-P8, and `esp32_03`
owns P9-P12. Firmware and broker configuration are unchanged.

## Start

From the repository root, use the existing environment:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Defaults work with the PC's broker at `127.0.0.1:1883`. ESP32 firmware continues
to use `host.wokwi.internal`; these addresses apply to different network contexts.
Optionally create a private `.env` from `.env.example`. Environment variables
override that file. Do not put credentials into tracked files or command lines.
Use a unique backend client ID and only one backend instance per database/client.
Do not use multiple workers or reload mode for the ingestion process.

Database default: `%LOCALAPPDATA%\SmartParking\parking.db`. The absolute path
must be outside the checkout and OneDrive. Startup creates only a new file or
opens a recognized Phase 2 schema. It refuses unrelated/incomplete databases
without resetting them. No default live database was needed for automated tests.
See [storage policy](../database/README.md).

Configuration: `MQTT_HOST`, `MQTT_PORT`, `MQTT_CLIENT_ID`, `MQTT_USERNAME`,
`MQTT_PASSWORD`, `MQTT_ENABLED` (`true`/`false`), `INGEST_QUEUE_SIZE` (default 256),
`STALE_SECONDS` (default 30), and `DATABASE_PATH`. Topics are fixed production
constants. `MQTT_ENABLED=false` allows database/API-only operation; health reports
that ingestion is disabled. Model/dashboard settings remain unused in Phase 2.

## Endpoints

| GET endpoint | Description |
| --- | --- |
| `/slots` | P1-P12 in numeric order, including never-observed slots |
| `/slots/P1` | Slot status; nonexistent IDs return 404 |
| `/history` | History ordered newest ingestion ID first |
| `/stats` | Fresh occupied/vacant counts, effective unknown, stale, unseen |
| `/health` | HTTP 200 ready or 503 degraded; database and MQTT/worker status |
| `/docs`, `/openapi.json` | Generated API contract |

History filters: `slot_id`, `device_id`, `state`, `since`, `until`, `limit`
(1-1000; default 100), `offset` (>=0). Time filters apply to **backend reception**
time and require timezone-aware ISO timestamps. Bounds are inclusive. Invalid
filters return 422. SQLite failures return a generic 503 without file paths.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/slots
Invoke-RestMethod 'http://127.0.0.1:8000/history?slot_id=P1&limit=20'
Invoke-RestMethod http://127.0.0.1:8000/stats
Invoke-RestMethod http://127.0.0.1:8000/health
```

`occupancy_status` is the last accepted device state. `observed=false` marks no
reading, and `stale=true` marks an old or absent reading. Stale records retain
their last state for diagnosis, but statistics count them as UNKNOWN, never
available. `unknown` includes fresh sensor UNKNOWN plus stale/unseen slots;
stale and unseen are overlapping diagnostic counts. The occupancy percentage
denominator is always 12, not just reporting slots. Backend freshness uses receipt
time, not a claim of synchronized sensor wall time.

## Ingestion and guarantees

Paho's network thread queues bounded messages. A separate worker parses strict
firmware-v1 JSON and writes one atomic four-slot snapshot. Synchronous API routes
run in FastAPI's thread pool, with their own short-lived SQLite connections.
The API event loop does not perform synchronous SQLite work.

Validation rejects unknown fields, duplicate JSON keys, nonfinite values,
boolean/string numeric substitutions, invalid identities, foreign/duplicate slots,
invalid dates, inconsistent clock flags, and inconsistent distance/state pairs.
Startup null timestamps and mixed null slot times during SNTP acquisition are
accepted. Device OCCUPIED/VACANT classification is preserved, because thresholds
can differ by firmware build. Format validation does not prove NTP accuracy.

The subscriber uses MQTT 3.1.1, a persistent broker session, manual acknowledgements
and reconnect backoff from 1 to 30 seconds. It resubscribes after connection and
requires QoS 1 subscription grants. ACK follows commit or durable duplicate
detection. Malformed/retained/unsupported packets are counted and acknowledged
without storing them. A full queue requests reconnect without ACK; database
errors hold ACK and retry until shutdown. Shutdown leaves unsuccessful writes
unacknowledged. Health exposes errors, queue depth and thread availability;
credentials and raw malformed payloads are not logged.

Duplicate identity is a SHA-256 fingerprint of canonical validated content,
including sequence, uptime, timestamps and sorted slots. This is not a universal
boot identity. Sequence and uptime can reset/wrap, and unsynchronized reboots can
produce identical content. Session inference uses counters and available device
timestamps; it can mistake delayed low-counter packets for a reboot or withhold
current updates after an unobserved reboot. Older non-boot counters and older
known publication timestamps remain history-only. Equal-counter conflicting
snapshots are retained as history-only. No firmware change is made to eliminate
this inherent ambiguity. Inspect history when diagnosing it.

Persistent MQTT delivery depends on broker/session retention, QoS, available
storage and broker persistence configuration. Paho session state is not a durable
application queue across process crashes. There is no end-to-end exactly-once or
lossless outage guarantee. Unsynchronized delayed traffic cannot always be
distinguished from fresh traffic. Local API/broker access is for the trusted
development PC; authentication/TLS and public deployment are outside Phase 2.

## Tests and evidence

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
.\.venv\Scripts\python.exe -m backend.tools.verify_integration `
  --output reports/evidence/phase2_broker_followup.json
.\.venv\Scripts\python.exe esp32/tests/test_circuits.py
```

Use a new evidence filename. Integration fixtures use only a unique
`smartparking/validation/phase2/...` namespace and private disposable databases
outside OneDrive. They prove the broker/backend/API path with Python fixtures,
not ESP32 sensor runtime. The integration test disconnects only its own backend
transport to test reconnect; it never restarts or reconfigures Mosquitto.
Tests use `unittest`, real Uvicorn/loopback HTTP and standard-library HTTP clients;
no packages were added to the existing environment.

See [Phase 2 PDF](../reports/phase2_fastapi_sqlite.pdf) and
[evidence index](../reports/README.md) for actual results and remaining limits.

## Troubleshooting

- Startup rejects an existing database: keep it intact and choose a new external
  filename. Review ownership/schema; do not delete or reset it automatically.
- Health 503 with MQTT disconnected: check PC broker address, credentials,
  unique backend ID and network availability. Firmware still uses the gateway.
- Health 200 but slots unseen: subscriptions are ready, but no valid telemetry
  has arrived. Check device simulations, rejection counters and production topics.
- Increasing database errors: inspect permissions, disk space and lock contention;
  stop duplicate backend processes. Writes retry without early ACK.
- Stale slots: check last receipt and assigned device. Never infer vacancy from
  silence. After outages, inspect queued/history-only messages before declaring
  current state trustworthy.
- Rejected messages: compare the actual payload with `schemas.py`; capture exact
  Serial/production output without credentials. Do not inject fixtures into live topics.

ML, dashboard and prediction serving are not implemented here.
