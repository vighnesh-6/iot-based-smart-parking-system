"""Real PostgreSQL tests on a disposable localhost CI database only."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from urllib.parse import urlsplit

from backend.db import Database
from backend.postgres import PostgresDatabase
from backend.tools.import_sqlite_history import copy_history
from support import validated, fixture


@unittest.skipUnless(os.environ.get('PHASE7_TEST_DATABASE_URL'), 'Disposable PostgreSQL CI database not configured; not a runtime pass')
class PostgresIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = os.environ['PHASE7_TEST_DATABASE_URL']
        parsed = urlsplit(url)
        if parsed.hostname not in ('127.0.0.1','localhost') or parsed.path != '/parking_test':
            raise ValueError('Refusing to touch a non-disposable database')
        cls.database = PostgresDatabase(url, local_test=True)
        cls.database.initialize()

    def setUp(self):
        with self.database.raw_connection() as connection:
            connection.execute('TRUNCATE slot_current,occupancy_observations,telemetry_messages RESTART IDENTITY CASCADE')

    def test_all_twelve_slots_history_duplicates_and_sequence(self):
        for board in range(1,4):
            payload = validated(fixture(board=board,sequence=0xFFFFFFFF,uptime=0xFFFFFFFF))
            self.assertEqual(self.database.persist(payload),'stored')
            self.assertEqual(self.database.persist(payload),'duplicate')
        self.assertTrue(self.database.healthy())
        self.assertEqual(len(self.database.current()),12)
        self.assertTrue(all(row['observed'] for row in self.database.current()))
        history = self.database.history(limit=12)
        self.assertEqual(history['total'],12)
        self.assertEqual({row['slot_id'] for row in history['items']},{f'P{i}' for i in range(1,13)})
        self.assertEqual(self.database.history(slot_id='P1')['total'],1)

    def test_two_writers_duplicate_detection_is_atomic(self):
        payload = validated()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(self.database.persist,[payload,payload]))
        self.assertCountEqual(outcomes,['stored','duplicate'])
        self.assertEqual(self.database.history()['total'],4)

    def test_reordered_and_reset_sequences_match_sqlite(self):
        for data, expected in [(fixture(sequence=10,uptime=100000),'stored'),
                               (fixture(sequence=9,uptime=90000),'history_only'),
                               (fixture(sequence=1,uptime=5000),'stored')]:
            self.assertEqual(self.database.persist(validated(data)),expected)
        self.assertEqual(self.database.current()[0]['sequence'],1)
        self.assertEqual(self.database.history()['total'],12)

    def test_import_preserves_exact_history_and_refuses_nonempty_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'source.db'
            local = Database(source);local.initialize()
            for board in range(1,4): local.persist(validated(fixture(board=board)))
            result = copy_history(source,self.database)
            self.assertTrue(result['source_unchanged'])
            self.assertEqual(result['copied_rows']['occupancy_observations'],12)
            self.assertEqual(local.current(),self.database.current())
            with self.assertRaises(ValueError):copy_history(source,self.database)
            self.assertEqual(self.database.history()['total'],12)


if __name__ == '__main__':unittest.main(verbosity=2)
