"""Read-only timed capture of production ESP32 MQTT telemetry and test evidence.

Does not start simulations or publish messages. Output excludes unknown payload
fields and credentials. It never overwrites an existing evidence file.
"""

import argparse
import json
import statistics
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
from check_mqtt import TOPICS, validate_payload


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--duration", type=float, default=90)
    parser.add_argument("--min-messages", type=int, default=3)
    parser.add_argument("--label", default="baseline")
    parser.add_argument("--expect", action="append", default=[], metavar="P1=VACANT")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.duration <= 0 or args.min_messages < 2:
        parser.error("positive duration and at least two messages are required")
    if args.output.exists():
        parser.error("evidence file exists; choose a new output path")
    expectations = {}
    for item in args.expect:
        slot, separator, status = item.partition("=")
        if not separator or slot not in {f"P{i}" for i in range(1, 13)} or status not in {"OCCUPIED", "VACANT", "UNKNOWN"}:
            parser.error(f"invalid expectation: {item}")
        expectations[slot] = status

    report = {"label": args.label, "source": "read_only_production_mqtt_subscription",
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "started_at_utc": utc_now(), "requested_duration_seconds": args.duration,
              "broker": {"host": args.host, "port": args.port}, "expected_states": expectations,
              "connack": None, "suback": None, "observer_disconnects": [],
              "messages": [], "errors": [], "retained_ignored": 0, "duplicates_ignored": 0}
    connected, subscribed = threading.Event(), threading.Event()
    start = time.monotonic()
    seen = set()

    def on_connect(client, _userdata, _flags, reason, _properties):
        report["connack"] = str(reason)
        connected.set()
        if not reason.is_failure:
            client.subscribe([(topic, 1) for topic in TOPICS])

    def on_subscribe(_client, _userdata, _mid, reasons, _properties):
        report["suback"] = [str(reason) for reason in reasons]
        if any(reason.is_failure for reason in reasons):
            report["errors"].append("production topic subscription rejected")
        subscribed.set()

    def on_disconnect(_client, _userdata, _flags, reason, _properties):
        report["observer_disconnects"].append({"at_utc": utc_now(), "reason": str(reason)})

    def on_message(_client, _userdata, message):
        if message.topic not in TOPICS:
            return
        if message.retain:
            report["retained_ignored"] += 1
            return
        try:
            if len(message.payload) > 4096:
                raise ValueError("payload exceeds observer limit")
            data = validate_payload(message.payload, TOPICS[message.topic])
            key = (message.topic, data["sequence"], data["uptime_ms"])
            if key in seen:
                report["duplicates_ignored"] += 1
                return
            seen.add(key)
            # Whitelist the documented telemetry fields; never persist arbitrary input.
            payload = {field: data[field] for field in ["schema_version", "device_id", "sequence", "timestamp", "clock_synced", "uptime_ms"]}
            payload["slots"] = [{field: slot[field] for field in ["slot_id", "distance_cm", "occupancy_status", "timestamp"]} for slot in data["slots"]]
            entry = {"received_at_utc": utc_now(), "elapsed_seconds": round(time.monotonic()-start, 3),
                     "topic": message.topic, "qos": message.qos, "payload": payload}
            report["messages"].append(entry)
            states = ", ".join(f"{s['slot_id']}={s['occupancy_status']}" for s in payload["slots"])
            print(f"RECEIVED {data['device_id']} sequence={data['sequence']} synced={data['clock_synced']} {states}", flush=True)
        except (AssertionError, KeyError, ValueError, TypeError) as error:
            report["errors"].append({"at_utc": utc_now(), "topic": message.topic,
                                     "error": f"invalid documented payload ({type(error).__name__})"})

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"parking-runtime-observer-{uuid.uuid4().hex[:10]}")
    client.connect_timeout = 5
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    looping = False
    try:
        client.connect(args.host, args.port, keepalive=30)
        client.loop_start()
        looping = True
        if not connected.wait(8):
            raise RuntimeError("broker CONNACK timeout")
        if not subscribed.wait(8):
            raise RuntimeError("production SUBACK timeout or connection rejected")
        print(f"Capturing {len(TOPICS)} production topics for {args.duration:g} seconds; no messages are published by this tool.", flush=True)
        deadline = time.monotonic() + args.duration
        while time.monotonic() < deadline:
            time.sleep(min(0.2, max(0, deadline-time.monotonic())))
    except (OSError, RuntimeError, KeyboardInterrupt) as error:
        report["errors"].append(f"capture interrupted: {type(error).__name__}: {error}")
    finally:
        if looping:
            client.on_disconnect = None # observer cleanup is not a broker outage
            client.disconnect()
            client.loop_stop()
        report["ended_at_utc"] = utc_now()
        report["elapsed_seconds"] = round(time.monotonic()-start, 3)

    summaries = {}
    for device in TOPICS.values():
        messages = [m for m in report["messages"] if m["payload"]["device_id"] == device]
        wall = [round(b["elapsed_seconds"]-a["elapsed_seconds"], 3) for a,b in zip(messages, messages[1:])]
        uptime = [(b["payload"]["uptime_ms"]-a["payload"]["uptime_ms"]) & 0xffffffff for a,b in zip(messages, messages[1:])]
        synced = sum(m["payload"]["clock_synced"] and all(s["timestamp"] is not None for s in m["payload"]["slots"]) for m in messages)
        matched = sum(all(expectations.get(s["slot_id"], s["occupancy_status"]) == s["occupancy_status"] for s in m["payload"]["slots"]) for m in messages)
        summaries[device] = {"valid_unique_messages": len(messages), "fully_timestamped_messages": synced,
                             "wall_intervals_seconds": wall, "device_intervals_ms": uptime,
                             "median_wall_interval_seconds": statistics.median(wall) if wall else None,
                             "expected_state_matching_messages": matched,
                             "minimum_messages_passed": len(messages) >= args.min_messages,
                             "periodic_device_cadence_passed": bool(uptime) and all(5000 <= value <= 10000 for value in uptime),
                             "timestamp_observation_passed": synced >= args.min_messages,
                             "expected_states_observed": matched >= args.min_messages}
    report["devices"] = summaries
    report["capture_checks_passed"] = not report["errors"] and all(
        all(info[key] for key in ["minimum_messages_passed", "periodic_device_cadence_passed",
                                 "timestamp_observation_passed", "expected_states_observed"])
        for info in summaries.values())
    report["provenance_limit"] = "Topic/payload observation alone is not simulator process/Serial provenance. Reconnection requires separate controlled evidence."
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"capture_checks_passed": report["capture_checks_passed"], "devices": summaries}, indent=2))
    print("Evidence saved:", args.output)
    return 0 if report["capture_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
