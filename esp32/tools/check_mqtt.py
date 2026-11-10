"""Local broker smoke test or read-only observation of actual ESP32 telemetry.

Smoke messages use a unique validation namespace, never production topics.
Requires the project's existing paho-mqtt dependency. No service settings change.
"""

import argparse
import json
import math
import threading
import time
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

TOPICS = {f"smartparking/esp32_{n:02d}/telemetry": f"esp32_{n:02d}"
          for n in range(1, 4)}


def validate_payload(payload, device):
    data = json.loads(payload)
    assert data["schema_version"] == 1 and data["device_id"] == device
    assert isinstance(data["clock_synced"], bool)
    assert type(data["sequence"]) is int and data["sequence"] >= 0
    assert type(data["uptime_ms"]) is int and data["uptime_ms"] >= 0

    def timestamp(value):
        if value is not None:
            assert isinstance(value, str) and value.endswith("Z")
            datetime.fromisoformat(value.replace("Z", "+00:00"))

    timestamp(data["timestamp"])
    assert data["clock_synced"] == (data["timestamp"] is not None)
    number = int(device[-2:])
    assert len(data["slots"]) == 4
    assert {s["slot_id"] for s in data["slots"]} == {
        f"P{n}" for n in range(4 * (number - 1) + 1, 4 * number + 1)}
    for slot in data["slots"]:
        timestamp(slot["timestamp"])
        assert slot["occupancy_status"] in {"OCCUPIED", "VACANT", "UNKNOWN"}
        distance = slot["distance_cm"]
        if slot["occupancy_status"] == "UNKNOWN":
            assert distance is None
        else:
            assert type(distance) in (int, float) and math.isfinite(distance)
            assert 2 <= distance <= 400
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke", action="store_true")
    mode.add_argument("--telemetry", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    run_id = uuid.uuid4().hex[:10]
    prefix = f"smartparking/validation/phase1/{run_id}"
    topics = ({f"{prefix}/esp32_{n:02d}": f"esp32_{n:02d}" for n in range(1, 4)}
              if args.smoke else TOPICS)
    received, errors, clients = {}, [], []
    subscribed = threading.Event()

    def connect(name):
        event, reasons = threading.Event(), []
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                             client_id=f"parking-probe-{run_id}-{name}")
        clients.append(client)
        client.connect_timeout = min(args.timeout, 5)

        def connected(_client, _userdata, _flags, reason, _properties):
            reasons.append(reason)
            event.set()

        client.on_connect = connected
        client.connect(args.host, args.port, keepalive=30)
        client.loop_start()
        if not event.wait(args.timeout) or reasons[0].is_failure:
            raise RuntimeError(f"Broker did not accept {name}; check listener/authentication")
        return client

    try:
        subscriber = connect("subscriber")

        def on_message(_client, _userdata, message):
            # Retained packets do not prove a board is currently publishing.
            if message.retain or message.topic not in topics:
                return
            try:
                assert len(message.payload) <= 4096
                received[topics[message.topic]] = validate_payload(
                    message.payload, topics[message.topic])
            except (AssertionError, KeyError, ValueError, TypeError) as error:
                errors.append(f"{message.topic}: invalid telemetry ({type(error).__name__})")

        def on_subscribe(_client, _userdata, _mid, reason_codes, _properties):
            if any(reason.is_failure for reason in reason_codes):
                errors.append("Broker rejected subscription")
            subscribed.set()

        subscriber.on_message = on_message
        subscriber.on_subscribe = on_subscribe
        subscriber.subscribe([(topic, 1) for topic in topics])
        if not subscribed.wait(args.timeout):
            raise RuntimeError("No subscription acknowledgement")
        if args.smoke:
            # Three concurrently connected synthetic publishers; not ESP32 clients.
            publishers = [connect(f"publisher-{n}") for n in range(1, 4)]
            stamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
            for number, publisher in enumerate(publishers, 1):
                device = f"esp32_{number:02d}"
                data = {"schema_version": 1, "device_id": device, "sequence": 0,
                        "timestamp": stamp, "clock_synced": True, "uptime_ms": 0,
                        "validation_source": "local_python_probe_not_esp32",
                        "slots": [{"slot_id": f"P{slot}", "distance_cm": 100.0,
                                   "occupancy_status": "VACANT", "timestamp": stamp}
                                  for slot in range(4 * (number - 1) + 1, 4 * number + 1)]}
                info = publisher.publish(f"{prefix}/{device}", json.dumps(data), qos=1, retain=False)
                info.wait_for_publish(timeout=args.timeout)
                if not info.is_published():
                    raise RuntimeError("Publish acknowledgement timed out")
        deadline = time.monotonic() + args.timeout
        while len(received) < 3 and not errors and time.monotonic() < deadline:
            time.sleep(0.05)
        if errors:
            raise RuntimeError("; ".join(errors))
        if len(received) != 3:
            missing = sorted(set(topics.values()) - set(received))
            raise RuntimeError(f"No fresh validated messages for {', '.join(missing)}")
        print("PASS local broker pub/sub with three Python publishers; NOT ESP32 runtime verification."
              if args.smoke else "PASS observed fresh validated telemetry on all three ESP32 topics.")
        print("Devices:", ", ".join(sorted(received)))
        if args.smoke:
            print("Validation namespace:", prefix)
        else:
            print(json.dumps(received, indent=2))
    finally:
        for client in clients:
            client.disconnect()
            client.loop_stop()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError) as error:
        raise SystemExit(f"CHECK FAILED: {error}") from error
