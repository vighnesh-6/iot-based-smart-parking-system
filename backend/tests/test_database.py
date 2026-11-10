from datetime import datetime, timedelta, timezone
import hashlib
import sqlite3
import unittest

from backend.db import Database, statistics
from backend.tests.support import fixture, test_settings, validated


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.context = test_settings(); self.settings = self.context.__enter__()
        self.db = Database(self.settings.database_path, timeout=0.02); self.db.initialize()

    def tearDown(self): self.context.__exit__(None,None,None)

    def test_seed_and_statistics(self):
        rows=self.db.current()
        self.assertEqual([s["slot_id"] for s in rows],[f"P{i}" for i in range(1,13)])
        self.assertEqual(statistics(rows)["unknown"],12)
        self.assertEqual(statistics(rows)["vacant"],0)
        self.assertTrue(self.db.healthy())

    def test_all_boards_persist_and_reopen(self):
        for board in range(1,4): self.db.persist(validated(fixture(board)))
        reopened=Database(self.settings.database_path); reopened.initialize()
        self.assertEqual(reopened.history()["total"],12)
        self.assertEqual(statistics(reopened.current())["vacant"],12)

    def test_durable_duplicate_and_slot_order(self):
        data=fixture(); self.db.persist(validated(data)); data["slots"].reverse()
        self.assertEqual(Database(self.settings.database_path).persist(validated(data)),"duplicate")
        self.assertEqual(self.db.history()["total"],4)

    def test_late_message_history_only(self):
        self.db.persist(validated(fixture(sequence=10,uptime=50000)))
        self.assertEqual(self.db.persist(validated(fixture(sequence=9,uptime=45000))),"history_only")
        self.assertEqual(self.db.current()[0]["sequence"],10)
        self.assertEqual(self.db.history()["total"],8)

    def test_inferred_reboot_and_counter_wrap(self):
        self.db.persist(validated(fixture(sequence=10,uptime=50000)))
        self.assertEqual(self.db.persist(validated(fixture(sequence=0,uptime=1000))),"stored")
        self.assertEqual(self.db.history()["items"][0]["inferred_session"],1)
        self.db.persist(validated(fixture(sequence=4294967295,uptime=10000)))
        self.assertEqual(self.db.persist(validated(fixture(sequence=0,uptime=15000))),"stored")

    def test_older_device_time_does_not_replace(self):
        self.db.persist(validated(fixture(sequence=1,stamp="2026-11-10T12:00:00Z")))
        self.assertEqual(self.db.persist(validated(fixture(sequence=2,stamp="2026-11-10T11:00:00Z"))),"history_only")

    def test_stale_is_not_available_and_duplicate_does_not_refresh(self):
        old=(datetime.now(timezone.utc)-timedelta(minutes=2)).isoformat(timespec="milliseconds").replace("+00:00","Z")
        value=validated(); self.db.persist(value, old); self.db.persist(value)
        self.assertTrue(self.db.current()[0]["stale"])
        self.assertEqual(statistics(self.db.current())["vacant"],0)

    def test_snapshot_rollback_on_database_error(self):
        with self.db.connection() as c:
            c.execute("CREATE TRIGGER fail_slot BEFORE INSERT ON occupancy_observations WHEN NEW.slot_id='P2' BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(sqlite3.Error): self.db.persist(validated())
        self.assertEqual(self.db.history()["total"],0)
        with self.db.connection() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM telemetry_messages").fetchone()[0],0)

    def test_locked_database_recoverable(self):
        with self.db.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            with self.assertRaises(sqlite3.OperationalError): self.db.persist(validated())
            c.rollback()
        self.assertEqual(self.db.persist(validated()),"stored")

    def test_history_filters_and_pagination(self):
        for board in (1,2): self.db.persist(validated(fixture(board)))
        self.assertEqual(self.db.history(device_id="esp32_02")["total"],4)
        page=self.db.history(limit=2,offset=1)
        self.assertEqual((page["total"],len(page["items"])),(8,2))
        self.assertEqual(self.db.history(slot_id="P1",state="VACANT")["total"],1)
        self.assertEqual(self.db.history(since="2099-01-01T00:00:00.000Z")["total"],0)

    def test_unknown_existing_database_unchanged(self):
        other=self.settings.database_path.with_name("existing.db")
        with sqlite3.connect(other) as c:
            c.execute("CREATE TABLE important(data TEXT)"); c.execute("INSERT INTO important VALUES ('preserve')")
        c.close()
        before=hashlib.sha256(other.read_bytes()).hexdigest()
        with self.assertRaises(ValueError): Database(other).initialize()
        self.assertEqual(hashlib.sha256(other.read_bytes()).hexdigest(),before)

    def test_known_database_not_reinitialized(self):
        self.db.persist(validated()); before=self.settings.database_path.read_bytes()
        self.db.initialize()
        self.assertEqual(before,self.settings.database_path.read_bytes())
