"""Synthetic fixtures and real local HTTP test server; never ESP32 evidence."""

from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
from urllib.error import HTTPError
from urllib.request import urlopen

import uvicorn

from backend.config import Settings
from backend.db import now_utc
from backend.main import create_app
from backend.schemas import parse_telemetry


def fixture(board=1, sequence=1, uptime=5000, stamp=None):
    stamp = stamp or now_utc()[:19] + "Z"
    return {"schema_version": 1, "device_id": f"esp32_{board:02d}",
            "sequence": sequence, "uptime_ms": uptime, "timestamp": stamp,
            "clock_synced": True, "slots": [
                {"slot_id": f"P{i}", "distance_cm": 100.0, "occupancy_status": "VACANT", "timestamp": stamp}
                for i in range(4*board-3, 4*board+1)]}


def validated(data=None):
    data = deepcopy(data or fixture())
    return parse_telemetry(json.dumps(data).encode(), data["device_id"])


def wait_until(predicate, timeout=8):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.03)
    raise AssertionError("Timed out waiting for test condition")


def request(base, path):
    try:
        with urlopen(base+path, timeout=5) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


@contextmanager
def http_server(settings, topics=None):
    app = create_app(settings, topics=topics)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    base = f"http://127.0.0.1:{sock.getsockname()[1]}"
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        wait_until(lambda: server.started or not thread.is_alive())
        if not server.started:
            raise AssertionError("Test server startup failed")
        yield app, base
    finally:
        server.should_exit = True
        thread.join(8)
        sock.close()
        if thread.is_alive():
            raise AssertionError("Test server did not stop")


@contextmanager
def test_settings(**kwargs):
    with tempfile.TemporaryDirectory(prefix="smartparking-phase2-") as directory:
        yield Settings(database_path=Path(directory)/"test.db", mqtt_enabled=False, **kwargs)
