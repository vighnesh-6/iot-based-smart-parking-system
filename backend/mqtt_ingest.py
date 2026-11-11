"""Independent MQTT network and persistence threads with commit-before-ACK."""

import logging
import queue
import sqlite3
import threading
import ssl

import paho.mqtt.client as mqtt

from backend.config import TOPICS
from backend.db import now_utc
from backend.schemas import parse_telemetry

LOGGER = logging.getLogger(__name__)


class Ingestor:
    def __init__(self, settings, database, topics=None, client=None):
        self.settings, self.database = settings, database
        self.topics = dict(TOPICS if topics is None else topics)
        self.queue = queue.Queue(maxsize=settings.queue_size)
        self.stop_event = threading.Event()
        self.reconnect_event = threading.Event()
        self.lock = threading.RLock()
        self.generation = 0
        self.state = dict(connected=False, subscribed=False, reconnects=0, received=0,
                          stored=0, history_only=0, duplicates=0, rejected=0,
                          retained_ignored=0, queue_overflows=0, database_errors=0,
                          database_error_active=False, worker_error_active=False, last_received_at=None,
                          last_stored_at=None, last_error=None)
        self.client = client or mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.mqtt_client_id, clean_session=False,
            protocol=mqtt.MQTTv311, manual_ack=True)
        if settings.mqtt_username:
            self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        if settings.mqtt_tls:
            context = ssl.create_default_context(cafile=settings.mqtt_ca_file or None)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            self.client.tls_set_context(context)
        self.client.connect_timeout = 3
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_subscribe = self.on_subscribe
        self.client.on_message = self.on_message
        self.worker = None
        self.network = None

    def update(self, **values):
        with self.lock:
            self.state.update(values)

    def increment(self, field):
        with self.lock:
            self.state[field] += 1

    def snapshot(self):
        with self.lock:
            result = dict(self.state)
        result.update(queue_depth=self.queue.qsize(),
                      worker_alive=bool(self.worker and self.worker.is_alive()),
                      network_alive=bool(self.network and self.network.is_alive()),
                      enabled=self.settings.mqtt_enabled)
        return result

    def on_connect(self, client, _userdata, _flags, reason, _properties):
        if reason.is_failure:
            self.update(connected=False, subscribed=False, last_error="broker_connection_rejected")
            return
        with self.lock:
            self.generation += 1
            self.state["connected"] = True
            self.state["subscribed"] = False
            if self.generation > 1:
                self.state["reconnects"] += 1
            self.state["last_error"] = None
        result, _mid = client.subscribe([(topic, 1) for topic in self.topics])
        if result != mqtt.MQTT_ERR_SUCCESS:
            self.update(last_error="subscription_request_failed")
            self.reconnect_event.set()

    def on_subscribe(self, _client, _userdata, _mid, reasons, _properties):
        ok = len(reasons) == len(self.topics) and all(not r.is_failure and r.value >= 1 for r in reasons)
        self.update(subscribed=ok, last_error=None if ok else "subscription_rejected_or_qos_downgraded")
        if not ok:
            self.reconnect_event.set()

    def on_disconnect(self, _client, _userdata, _flags, _reason, _properties):
        self.update(connected=False, subscribed=False)

    def acknowledge(self, mid, qos, generation):
        # MQTT packet ids can be reused after reconnect. Never ACK an old generation.
        with self.lock:
            if generation != self.generation or not self.state["connected"]:
                return
            result = self.client.ack(mid, qos)
            if result != mqtt.MQTT_ERR_SUCCESS:
                self.state["last_error"] = "ack_failed"
                self.reconnect_event.set()

    def on_message(self, _client, _userdata, message):
        with self.lock:
            generation = self.generation
        if message.retain:
            self.increment("retained_ignored")
            self.acknowledge(message.mid, message.qos, generation)
            return
        if message.topic not in self.topics or len(message.payload) > 4096 or message.qos != 1:
            self.increment("rejected")
            self.acknowledge(message.mid, message.qos, generation)
            return
        try:
            self.queue.put_nowait((message.topic, bytes(message.payload), now_utc(),
                                   message.mid, message.qos, generation))
            self.increment("received")
            self.update(last_received_at=now_utc())
        except queue.Full:
            self.increment("queue_overflows")
            self.update(last_error="ingest_queue_full")
            # No ACK: request reconnect so the persistent broker session can redeliver.
            self.reconnect_event.set()

    def process(self, item):
        topic, payload, received_at, mid, qos, generation = item
        try:
            telemetry = parse_telemetry(payload, self.topics[topic])
        except (ValueError, TypeError, KeyError, RecursionError):
            self.increment("rejected")
            self.update(last_error="invalid_payload")
            self.acknowledge(mid, qos, generation)
            return
        while True:
            try:
                result = self.database.persist(telemetry, received_at)
                self.increment({"stored": "stored", "duplicate": "duplicates", "history_only": "history_only"}[result])
                self.update(database_error_active=False, worker_error_active=False, last_stored_at=now_utc())
                self.acknowledge(mid, qos, generation)
                return
            except (sqlite3.Error, OSError):
                self.increment("database_errors")
                self.update(database_error_active=True, last_error="database_write_failed")
                LOGGER.warning("MQTT database write failed; holding acknowledgement and retrying")
                if self.stop_event.wait(0.25):
                    return

    def run_worker(self):
        # Leave queued packets unacknowledged on shutdown for broker redelivery.
        while not self.stop_event.is_set():
            try:
                item = self.queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self.process(item)
            except Exception:
                # Unexpected programming errors must be visible and never silently ACKed.
                LOGGER.exception("Unexpected ingestion failure (payload omitted)")
                self.update(last_error="ingestion_worker_failure", worker_error_active=True)
                self.reconnect_event.set()
            finally:
                self.queue.task_done()

    def run_network(self):
        delay = 1
        while not self.stop_event.is_set():
            self.reconnect_event.clear()
            try:
                self.client.connect(self.settings.mqtt_host, self.settings.mqtt_port, keepalive=30)
                while not self.stop_event.is_set() and not self.reconnect_event.is_set():
                    if self.client.loop(timeout=0.2) != mqtt.MQTT_ERR_SUCCESS:
                        break
                    if self.snapshot()["subscribed"]:
                        delay = 1
            except OSError:
                self.update(last_error="mqtt_transport_unavailable")
            except Exception as error:
                LOGGER.error("MQTT network failure (%s); retry scheduled", type(error).__name__)
                self.update(last_error="mqtt_network_failure")
            finally:
                self.client.disconnect()
                self.update(connected=False, subscribed=False)
            if self.stop_event.wait(delay):
                break
            delay = min(delay*2, 30)

    def start(self):
        self.worker = threading.Thread(target=self.run_worker, name="parking-writer", daemon=True)
        self.worker.start()
        if self.settings.mqtt_enabled:
            self.network = threading.Thread(target=self.run_network, name="parking-mqtt", daemon=True)
            self.network.start()

    def stop(self):
        self.stop_event.set()
        if self.network:
            self.network.join(timeout=5)
        if self.worker:
            self.worker.join(timeout=5)
