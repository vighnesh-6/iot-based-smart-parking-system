"""Actual local broker -> worker -> SQLite -> HTTP test with SYNTHETIC fixtures.

Run from repository root: python -m backend.tools.verify_integration --output PATH
Never publishes production topics, touches live databases, or changes Mosquitto.
"""

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
import time
import uuid

import paho.mqtt.client as mqtt

from backend.db import now_utc
from backend.tests.support import fixture, http_server, request, test_settings, wait_until


def run(host="127.0.0.1", port=1883):
    run_id=uuid.uuid4().hex[:10]
    prefix=f"smartparking/validation/phase2/{run_id}"
    topics={f"{prefix}/esp32_{i:02d}/telemetry":f"esp32_{i:02d}" for i in range(1,4)}
    record={"source":"local_broker_backend_http_integration_with_synthetic_fixtures",
            "started_at_utc":now_utc(),"namespace":prefix,"checks":{},
            "production_topics_published":False,"esp32_runtime_verified":False}
    checks=record["checks"]
    publisher=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id=f"phase2-probe-{run_id}")
    publisher.connect_timeout=3
    publisher.connect(host,port,30); publisher.loop_start()

    def publish(board, data, retain=False):
        raw=data if isinstance(data,bytes) else json.dumps(data).encode()
        info=publisher.publish(f"{prefix}/esp32_{board:02d}/telemetry",raw,qos=1,retain=retain)
        info.wait_for_publish(timeout=5)
        if not info.is_published(): raise AssertionError("Probe publication not acknowledged")

    try:
        with test_settings() as initial:
            settings=replace(initial,mqtt_enabled=True,mqtt_host=host,mqtt_port=port,
                             mqtt_client_id=f"phase2-backend-{run_id}")
            data={i:fixture(i) for i in range(1,4)}
            with http_server(settings,topics) as (app,base):
                wait_until(lambda:request(base,"/health")[0]==200)
                checks["broker_connection_and_three_qos1_subscriptions"]=True
                for board in range(1,4): publish(board,data[board])
                wait_until(lambda:request(base,"/history")[1]["total"]==12)
                rows=request(base,"/slots")[1]
                assert {s["slot_id"] for s in rows}=={f"P{i}" for i in range(1,13)}
                assert request(base,"/stats")[1]["vacant"]==12
                checks["three_devices_twelve_slots_persisted_and_served"]=True
                publish(1,data[1])
                wait_until(lambda:app.state.ingestor.snapshot()["duplicates"]>=1)
                assert request(base,"/history")[1]["total"]==12
                checks["duplicate_no_extra_history"]=True
                publish(1,b'{"invalid":true}')
                wait_until(lambda:app.state.ingestor.snapshot()["rejected"]>=1)
                assert request(base,"/history")[1]["total"]==12
                checks["invalid_json_contract_rejected"]=True
                previous=app.state.ingestor.snapshot()["reconnects"]
                app.state.ingestor.reconnect_event.set()  # Only this test backend, never broker service.
                wait_until(lambda:app.state.ingestor.snapshot()["reconnects"]>previous and request(base,"/health")[0]==200)
                changed=fixture(1,sequence=2,uptime=10000)
                changed["slots"][0].update(distance_cm=10.0,occupancy_status="OCCUPIED")
                publish(1,changed)
                wait_until(lambda:request(base,"/history")[1]["total"]==16)
                assert request(base,"/slots/P1")[1]["occupancy_status"]=="OCCUPIED"
                checks["actual_backend_transport_reconnect_and_resume"]=True
                checks["synthetic_occupancy_transition_visible"]=True
                record["before_restart_status"]=app.state.ingestor.snapshot()
            with http_server(settings,topics) as (app,base):
                wait_until(lambda:request(base,"/health")[0]==200)
                publish(1,changed)
                wait_until(lambda:app.state.ingestor.snapshot()["duplicates"]>=1)
                assert request(base,"/history")[1]["total"]==16
                checks["backend_restart_preserves_history_and_deduplication"]=True
                record["after_restart_stats"]=request(base,"/stats")[1]
                record["after_restart_status"]=app.state.ingestor.snapshot()
            # Explicit test-only unsubscribe prevents abandoned persistent sessions.
            cleanup=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id=settings.mqtt_client_id,clean_session=True)
            cleanup.connect(host,port,30); cleanup.loop_start()
            wait_until(cleanup.is_connected)
            cleanup.disconnect(); cleanup.loop_stop()
    finally:
        publisher.disconnect(); publisher.loop_stop()
    record["ended_at_utc"]=now_utc()
    record["passed"]=all(checks.values()) and len(checks)==7
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=1883)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): parser.error("Choose a new evidence filename; existing evidence is never overwritten")
    try:
        result=run(args.host,args.port)
    except Exception as error:
        result={"source":"local_broker_backend_http_integration_with_synthetic_fixtures",
                "passed":False,"error_type":type(error).__name__,"recorded_at_utc":now_utc(),
                "production_topics_published":False,"esp32_runtime_verified":False}
        print(f"Integration failed: {type(error).__name__}",file=sys.stderr)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf-8") as stream:
        json.dump(result,stream,indent=2); stream.write("\n")
    print(json.dumps(result,indent=2))
    return 0 if result["passed"] else 1


if __name__=="__main__":
    raise SystemExit(main())
