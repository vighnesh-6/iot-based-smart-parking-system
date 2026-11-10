import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import socket
import unittest
from unittest.mock import patch

from backend.config import ROOT, Settings
from backend.tests.support import fixture, http_server, request, test_settings, validated, wait_until


class ConfigurationTests(unittest.TestCase):
    def test_project_and_onedrive_paths_rejected(self):
        for path in [ROOT/"parking.db",ROOT.parent/"OneDrive-copy"/"parking.db","relative.db"]:
            with self.assertRaises(ValueError): Settings(database_path=path)

    def test_invalid_limits_and_identity(self):
        with test_settings() as settings:
            for kwargs in [dict(mqtt_port=0),dict(queue_size=0),dict(stale_seconds=0),
                           dict(mqtt_client_id="smartparking-esp32_01")]:
                with self.assertRaises(ValueError): Settings(database_path=settings.database_path,**kwargs)

    def test_password_not_in_repr(self):
        with test_settings() as settings:
            self.assertNotIn("sentinel-secret",repr(Settings(database_path=settings.database_path,mqtt_password="sentinel-secret")))

    def test_api_remains_available_without_broker(self):
        with socket.socket() as blocked_port, test_settings() as settings:
            blocked_port.bind(("127.0.0.1",0))  # Bound but not listening: no broker.
            configured=replace(settings,mqtt_enabled=True,mqtt_port=blocked_port.getsockname()[1])
            with http_server(configured) as (app,base):
                wait_until(lambda:app.state.ingestor.snapshot()["last_error"]=="mqtt_transport_unavailable")
                self.assertEqual(request(base,"/health")[0],503)
                self.assertEqual(len(request(base,"/slots")[1]),12)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context=test_settings(); cls.settings=cls.context.__enter__()
        cls.server=http_server(cls.settings); cls.app,cls.base=cls.server.__enter__()
        for board in range(1,4): cls.app.state.database.persist(validated(fixture(board)))

    @classmethod
    def tearDownClass(cls):
        cls.server.__exit__(None,None,None); cls.context.__exit__(None,None,None)

    def test_all_slots_and_individual(self):
        status,rows=request(self.base,"/slots")
        self.assertEqual((status,len(rows)),(200,12))
        self.assertEqual(request(self.base,"/slots/P12")[1]["device_id"],"esp32_03")
        self.assertEqual(request(self.base,"/slots/P13")[0],404)

    def test_stats(self):
        status,data=request(self.base,"/stats")
        self.assertEqual(status,200); self.assertEqual(data["vacant"],12)
        self.assertEqual(data["occupied"]+data["vacant"]+data["unknown"],12)

    def test_history_filters(self):
        status,data=request(self.base,"/history?slot_id=P1&state=VACANT&limit=1")
        self.assertEqual((status,data["total"],len(data["items"])),(200,1,1))
        self.assertEqual(request(self.base,"/history?device_id=esp32_03")[1]["total"],4)
        self.assertEqual(request(self.base,"/history?limit=2&offset=11")[1]["total"],12)

    def test_invalid_history_queries(self):
        for query in ["limit=0","limit=1001","offset=-1","slot_id=P99","device_id=bad",
                      "state=FREE","since=bad","since=2026-01-01T00:00:00",
                      "since=2026-12-01T00:00:00Z&until=2026-01-01T00:00:00Z"]:
            with self.subTest(query=query): self.assertEqual(request(self.base,"/history?"+query)[0],422)

    def test_health_and_openapi(self):
        status,data=request(self.base,"/health")
        self.assertEqual(status,200); self.assertTrue(data["database_ok"])
        self.assertFalse(data["mqtt"]["enabled"])
        self.assertIn("/slots",request(self.base,"/openapi.json")[1]["paths"])

    def test_database_failure_503_no_leak(self):
        with patch.object(self.app.state.database,"current",side_effect=sqlite3.OperationalError("secret-path")):
            status,data=request(self.base,"/slots")
            self.assertEqual(status,503); self.assertNotIn("secret",str(data))
        with patch.object(self.app.state.database,"healthy",side_effect=sqlite3.OperationalError()):
            self.assertEqual(request(self.base,"/health")[0],503)

    def test_mqtt_unavailable_degraded(self):
        state=self.app.state.ingestor.snapshot()
        with patch.object(self.app.state.ingestor,"snapshot",return_value={**state,"enabled":True,"connected":False}):
            self.assertEqual(request(self.base,"/health")[0],503)

    def test_parallel_reads_during_reserved_writer_lock(self):
        with self.app.state.database.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            with ThreadPoolExecutor(max_workers=4) as pool:
                results=list(pool.map(lambda _:request(self.base,"/slots")[0],range(12)))
            connection.rollback()
        self.assertEqual(results,[200]*12)
