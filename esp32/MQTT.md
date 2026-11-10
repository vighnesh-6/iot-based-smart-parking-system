# Phase 1: local MQTT telemetry

## Connection and configuration

All three firmware targets connect to `Wokwi-GUEST` (empty password, channel 6)
and the same Mosquitto broker at **host.wokwi.internal:1883**. The three existing
`simulations/esp32-0N/wokwi.toml` files and dedicated VS Code workspaces remain
unchanged. Their firmware paths were checked before implementation.

Wokwi for VS Code [includes its private IoT gateway](https://docs.wokwi.com/vscode/project-config#iot-gateway-esp32-wifi).
No extra `net.forward` setting is needed for an outbound MQTT connection.
`host.wokwi.internal` reaches the PC through that gateway; `localhost` or
`127.0.0.1` inside ESP32 firmware would refer to the simulated device itself.
The [free browser public gateway cannot reach a local broker](https://docs.wokwi.com/guides/esp32-wifi).
Gateway/license access and live routing still require an actual simulation run.

Public defaults live in `include/mqtt_config.h`. To override local credentials,
copy `include/config.example.h` to `include/config.h` (already gitignored).
Do not put passwords into build flags, tracked headers, logs or documentation.
Credentials are not logged. The existing Windows Mosquitto service and its
configuration have not been changed; the repository's broker placeholder
`config/mosquitto.conf` is also unchanged. Local Python clients use
`127.0.0.1:1883`, because they run on the PC, outside the simulation.

## Device identity and topics

| Build | MQTT client ID | Topic | Slot IDs |
| --- | --- | --- | --- |
| esp32_01 | smartparking-esp32_01 | smartparking/esp32_01/telemetry | P1-P4 |
| esp32_02 | smartparking-esp32_02 | smartparking/esp32_02/telemetry | P5-P8 |
| esp32_03 | smartparking-esp32_03 | smartparking/esp32_03/telemetry | P9-P12 |

One message contains a snapshot of the four assigned slots. Do not run two
copies of the same board target concurrently: identical MQTT client IDs cause
the broker to disconnect the older session. The three different board targets
can connect concurrently to the same broker.

## Payload and timestamps

This is an illustrative unsynchronized snapshot, not captured ESP32 telemetry:

```json
{
  "schema_version": 1,
  "device_id": "esp32_01",
  "sequence": 0,
  "timestamp": null,
  "clock_synced": false,
  "uptime_ms": 1000,
  "slots": [
    {"slot_id":"P1","distance_cm":10.0,"occupancy_status":"OCCUPIED","timestamp":null},
    {"slot_id":"P2","distance_cm":100.0,"occupancy_status":"VACANT","timestamp":null},
    {"slot_id":"P3","distance_cm":null,"occupancy_status":"UNKNOWN","timestamp":null},
    {"slot_id":"P4","distance_cm":100.0,"occupancy_status":"VACANT","timestamp":null}
  ]
}
```

After Wi-Fi connects, asynchronous SNTP requests UTC from `pool.ntp.org` and
`time.google.com`. Once wall time is valid, timestamps use ISO 8601 UTC strings
such as `2026-11-10T12:00:00Z`. The root timestamp is publication time; each
slot timestamp is its measurement time. The first snapshot can contain null
timestamps, or a mix if synchronization occurs during the scan. This is explicit
missing wall time, not an invented date. `uptime_ms` is diagnostic monotonic
device time and wraps at the Arduino millis limit; it is not Unix time.

Invalid measurements retain their existing UNKNOWN classification and emit
`distance_cm: null`. The threshold still defaults to 20 cm, inclusive for
OCCUPIED. All GPIO mappings and voltage dividers are unchanged. `sequence`
counts acknowledged publications and restarts on boot; it is diagnostic, not a
globally unique database/deduplication key. QoS 1 can deliver duplicates.

## Timing and recovery

- Sample all four local slots approximately once a second, with the original
  10 us triggers, 30 ms echo timeout and 60 ms inter-sensor quiet intervals.
- Service MQTT/Wi-Fi between sensors and in 10 ms sleep slices. Network outages
  do not introduce infinite wait-until-connected loops. TCP connection and MQTT
  acknowledgement timeouts are set to 1 second; DNS/network stack delays can
  still stretch a scan, so this is not a hard real-time latency guarantee.
- Publish the latest completed scan every 5 seconds when connected, QoS 1,
  non-retained. `PARKING_MQTT_PUBLISH_INTERVAL_MS` is configurable (1 s-1 h).
- Retry Wi-Fi and MQTT with bounded backoff, capped at 30 seconds. After
  reconnect, publish a newly completed scan without waiting another 5 seconds.
- A failed publish is rate-limited too. Old disconnected scans are not queued
  for replay, and lossless historical delivery is not promised in Phase 1.
- Bound JSON to a 1,536-byte buffer; reject truncation rather than publishing
  malformed JSON. The fixed slot/device IDs and numeric/UTC fields do not
  include user-provided strings or credentials.

## Build and checks

The firmware uses the pinned `256dpi/MQTT@2.5.3` library. Build all three targets
with the existing PlatformIO command in `README.md`. No Python dependencies
have been changed. Host test fakes are excluded from actual ESP32 builds.

From the repository root:

```powershell
.\.venv\Scripts\python.exe esp32/tests/test_circuits.py
.\.venv\Scripts\python.exe esp32/tools/run_host_tests.py
.\.venv\Scripts\python.exe esp32/tools/check_mqtt.py --smoke --timeout 10
```

The smoke command connects three **Python** publishers simultaneously and a
subscriber. Its synthetic fixtures are explicitly labelled and use a unique
`smartparking/validation/phase1/<run-id>/...` namespace, never the production
telemetry topics. It checks local broker acceptance, QoS 1 pub/sub and the
four-slot JSON contract; it does not run ESP32 firmware or exercise the gateway.
If broker authentication is required, configure an appropriate local test
client securely instead of changing the service or publishing credentials.

To observe actual firmware later, launch each board's existing workspace and
simulation, then run this read-only subscriber:

```powershell
.\.venv\Scripts\python.exe esp32/tools/check_mqtt.py --telemetry --timeout 30
```

This requires fresh non-retained valid messages for all three assigned topics.
Change a sensor distance and inspect actual received values. Test Wi-Fi/broker
recovery only in a controlled session; do not stop or reconfigure the Windows
service as part of an unattended check. Seeing Serial readings alone does not
prove MQTT success. A subscribed-topic timeout means runtime verification is
still incomplete, even if builds and the Python smoke test pass.

## Current validation limits

All three ESP32 firmware targets compile successfully. An initial ESP32-01 host
run passed sensor boundary/UNKNOWN checks, JSON UTC/null encoding, payload buffer
bounds, QoS/retain flags, publish pacing and reconnect tests. All three final
host programs compiled after adding explicit identity assertions. Windows
Application Control blocked ESP32-02 in the initial run and also blocked the
final ESP32-01 rerun (WinError 4551); a complete final host-suite pass is not
claimed. Compiled ESP32 ELF tables/strings independently confirm each board's
four GPIO mappings, unique MQTT topic/client ID and private gateway hostname.
Security policy was not changed.

The running local Mosquitto broker passed the isolated three-Python-publisher
smoke test. An 8-second read-only subscription observed no fresh messages on
any of the three production telemetry topics. Actual Wokwi ESP32-to-broker publishing and gateway reachability
remain unverified; simulation runtime testing was left pending by user choice.
No FastAPI, SQLite, ML or dashboard functionality is added by this phase.
