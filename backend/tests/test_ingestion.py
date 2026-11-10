import json
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import paho.mqtt.client as mqtt

from backend.mqtt_ingest import Ingestor
from backend.tests.support import fixture, test_settings, wait_until


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.context=test_settings(queue_size=1); self.settings=self.context.__enter__()
        self.database=Mock(); self.database.persist.return_value="stored"
        self.client=Mock(); self.client.ack.return_value=mqtt.MQTT_ERR_SUCCESS
        self.client.subscribe.return_value=(mqtt.MQTT_ERR_SUCCESS,1)
        self.ingestor=Ingestor(self.settings,self.database,client=self.client)
        self.ingestor.update(connected=True)

    def tearDown(self):
        self.ingestor.stop(); self.context.__exit__(None,None,None)

    def message(self,payload=None,**kwargs):
        values=dict(topic="smartparking/esp32_01/telemetry",payload=payload if payload is not None else json.dumps(fixture()).encode(),
                    mid=12,qos=1,retain=False)
        values.update(kwargs)
        return SimpleNamespace(**values)

    def process_one(self):
        self.ingestor.on_message(self.client,None,self.message())
        self.ingestor.process(self.ingestor.queue.get_nowait())

    def test_commit_before_ack(self):
        events=[]
        self.database.persist.side_effect=lambda *_: events.append("commit") or "stored"
        self.client.ack.side_effect=lambda *_: events.append("ack") or 0
        self.process_one(); self.assertEqual(events,["commit","ack"])

    def test_duplicate_acknowledged(self):
        self.database.persist.return_value="duplicate"; self.process_one()
        self.assertEqual(self.ingestor.snapshot()["duplicates"],1)
        self.client.ack.assert_called_once()

    def test_invalid_ack_without_database_write(self):
        self.ingestor.on_message(self.client,None,self.message(b"{"))
        self.ingestor.process(self.ingestor.queue.get_nowait())
        self.database.persist.assert_not_called(); self.client.ack.assert_called_once()
        self.assertEqual(self.ingestor.snapshot()["rejected"],1)

    def test_retained_oversized_unknown_topic_qos_rejected(self):
        for message in [self.message(retain=True),self.message(b"x"*4097),
                        self.message(topic="foreign"),self.message(qos=0)]:
            self.ingestor.on_message(self.client,None,message)
        self.assertEqual(self.ingestor.queue.qsize(),0)
        self.database.persist.assert_not_called()

    def test_overflow_unacknowledged_and_reconnect_requested(self):
        self.ingestor.on_message(self.client,None,self.message())
        self.ingestor.on_message(self.client,None,self.message(mid=13))
        self.client.ack.assert_not_called()
        self.assertTrue(self.ingestor.reconnect_event.is_set())
        self.assertEqual(self.ingestor.snapshot()["queue_overflows"],1)

    def test_database_error_retried_before_ack(self):
        self.database.persist.side_effect=[sqlite3.OperationalError("locked"),"stored"]
        self.process_one()
        self.assertEqual(self.database.persist.call_count,2)
        self.client.ack.assert_called_once()
        self.assertEqual(self.ingestor.snapshot()["database_errors"],1)
        self.assertFalse(self.ingestor.snapshot()["database_error_active"])

    def test_shutdown_failure_no_ack(self):
        self.database.persist.side_effect=sqlite3.OperationalError("disk full")
        self.ingestor.stop_event.set(); self.process_one()
        self.client.ack.assert_not_called()
        self.assertTrue(self.ingestor.snapshot()["database_error_active"])

    def test_old_connection_generation_no_ack(self):
        self.ingestor.generation=2
        self.ingestor.acknowledge(12,1,1)
        self.client.ack.assert_not_called()

    def test_connection_and_subscription_callbacks(self):
        reason=SimpleNamespace(is_failure=False)
        self.ingestor.on_connect(self.client,None,None,reason,None)
        self.assertEqual(len(self.client.subscribe.call_args.args[0]),3)
        self.ingestor.on_subscribe(self.client,None,1,[SimpleNamespace(is_failure=False,value=1)]*3,None)
        self.assertTrue(self.ingestor.snapshot()["subscribed"])
        self.ingestor.on_disconnect(self.client,None,None,None,None)
        self.assertFalse(self.ingestor.snapshot()["connected"])
        self.ingestor.on_connect(self.client,None,None,reason,None)
        self.assertEqual(self.ingestor.snapshot()["reconnects"],1)

    def test_rejected_connection_subscription_and_ack(self):
        self.ingestor.on_connect(self.client,None,None,SimpleNamespace(is_failure=True),None)
        self.assertFalse(self.ingestor.snapshot()["connected"])
        self.ingestor.on_subscribe(self.client,None,1,[SimpleNamespace(is_failure=True,value=128)],None)
        self.assertTrue(self.ingestor.reconnect_event.is_set())
        self.ingestor.reconnect_event.clear(); self.ingestor.update(connected=True)
        self.client.ack.return_value=mqtt.MQTT_ERR_NO_CONN
        self.ingestor.acknowledge(1,1,0)
        self.assertEqual(self.ingestor.snapshot()["last_error"],"ack_failed")

    def test_worker_runs_and_stops_independently(self):
        self.ingestor.start()
        self.ingestor.on_message(self.client,None,self.message())
        wait_until(lambda:self.ingestor.snapshot()["stored"]==1)
        self.ingestor.stop()
        self.assertFalse(self.ingestor.worker.is_alive())
