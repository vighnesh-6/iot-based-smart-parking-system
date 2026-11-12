"""PostgreSQL transport for the unchanged transactional SQLite persistence rules.

Only this module requires psycopg. Local SQLite execution does not import it.
Database methods are inherited, preserving fingerprints, ordering and freshness.
"""
from contextlib import contextmanager
import math
import sqlite3

from backend.config import DEVICES
from backend.db import Database, SCHEMA

POSTGRES_SCHEMA = (SCHEMA.replace('INTEGER PRIMARY KEY', 'BIGSERIAL PRIMARY KEY')
    .replace('sequence INTEGER', 'sequence BIGINT').replace('uptime_ms INTEGER', 'uptime_ms BIGINT')
    .replace('message_id INTEGER', 'message_id BIGINT').replace('observation_id INTEGER', 'observation_id BIGINT'))


class Row(dict):
    def __getitem__(self, key):
        return tuple(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


class Cursor:
    def __init__(self, cursor, lastrowid=None):
        self.cursor, self.lastrowid = cursor, lastrowid

    def fetchone(self):
        row = self.cursor.fetchone()
        return Row(row) if row is not None else None

    def fetchall(self):
        return [Row(row) for row in self.cursor.fetchall()]


class Connection:
    """Translate the small fixed DB-API SQL subset used by backend.db, never user SQL."""
    def __init__(self, raw):
        self.raw = raw

    def execute(self, statement, values=()):
        if statement == 'BEGIN IMMEDIATE':
            return Cursor(self.raw.execute('SELECT pg_advisory_xact_lock(1397771058)'))
        if statement == 'BEGIN':
            statement = 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'
        returning = statement.startswith(('INSERT INTO telemetry_messages(', 'INSERT INTO occupancy_observations('))
        if returning:
            statement += ' RETURNING id'
        cursor = self.raw.execute(statement.replace('?', '%s'), values)
        return Cursor(cursor, cursor.fetchone()['id'] if returning else None)

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()


class PostgresDatabase(Database):
    def __init__(self, url, timeout=2.0, *, local_test=False):
        self.url, self.timeout, self.local_test = url, timeout, local_test

    @contextmanager
    def raw_connection(self):
        import psycopg
        from psycopg.rows import dict_row
        connection = None
        try:
            options = {'sslmode': 'disable'} if self.local_test else {'sslmode': 'verify-full', 'sslrootcert': 'system'}
            connection = psycopg.connect(self.url, autocommit=True, row_factory=dict_row,
                connect_timeout=max(1, math.ceil(self.timeout)), prepare_threshold=None, **options)
            yield connection
        except psycopg.Error:
            # Shared API/ingestion handlers already retry/sanitize sqlite3.Error.
            # Never put a DSN, SQL parameter or server diagnostic in UI/logs.
            raise sqlite3.OperationalError('PostgreSQL operation unavailable') from None
        finally:
            if connection is not None:
                connection.close()

    @contextmanager
    def connection(self):
        with self.raw_connection() as raw:
            raw.execute('BEGIN')
            try:
                self.configure_transaction(raw)
                yield Connection(raw)
            finally:
                # Read-only callers do not commit; release their pooled connection.
                # Persist already committed before returning/acknowledging MQTT.
                raw.rollback()

    @staticmethod
    def configure_transaction(connection):
        # Neon transaction pooling cannot preserve session-level SET statements.
        connection.execute('SET LOCAL search_path TO smartparking,public')
        connection.execute("SET LOCAL statement_timeout TO '10000ms'")

    def initialize(self):
        with self.raw_connection() as connection:
            with connection.transaction():
                self.configure_transaction(connection)
                connection.execute('SELECT pg_advisory_xact_lock(1397771058)')
                connection.execute('CREATE SCHEMA IF NOT EXISTS smartparking')
                tables = {r['table_name'] for r in connection.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='smartparking'")}
                expected = {'cloud_metadata', 'slots', 'telemetry_messages', 'occupancy_observations', 'slot_current'}
                if not tables:
                    connection.execute(POSTGRES_SCHEMA)
                    connection.execute('CREATE TABLE cloud_metadata (version INTEGER PRIMARY KEY CHECK(version=1))')
                    connection.execute('INSERT INTO cloud_metadata VALUES (1)')
                    with connection.cursor() as cursor:
                        cursor.executemany('INSERT INTO slots VALUES (%s,%s)',
                            [(slot, device) for device, slots in DEVICES.items() for slot in slots])
                elif tables != expected:
                    raise ValueError('Unrecognized cloud schema preserved; use a dedicated empty database')
                versions = list(connection.execute('SELECT version FROM cloud_metadata'))
                registry = {(r['slot_id'], r['device_id']) for r in connection.execute('SELECT * FROM slots')}
                if versions != [{'version': 1}] or registry != {(s,d) for d,ss in DEVICES.items() for s in ss}:
                    raise ValueError('Unrecognized cloud metadata/slot registry; preserved unchanged')
