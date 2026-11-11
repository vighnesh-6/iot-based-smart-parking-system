"""One-time copy into an EMPTY dedicated cloud database; source always read-only.

Run only from an approved runtime containing psycopg, before cloud MQTT starts.
Credentials are read from DATABASE_URL, never command arguments or output.
"""
import argparse
import hashlib
import os
from pathlib import Path
import sqlite3

from backend.config import Settings
from backend.db import APPLICATION_ID, SCHEMA_VERSION
from backend.postgres import PostgresDatabase


def copy_history(source, destination):
    source = Path(source).resolve(strict=True)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    tables = ('telemetry_messages', 'occupancy_observations', 'slot_current')
    counts = {}
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as local:
        local.row_factory = sqlite3.Row
        local.execute('BEGIN')
        if local.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID or local.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION:
            raise ValueError('Source is not the recognized parking database')
        registry = {tuple(row) for row in local.execute('SELECT slot_id,device_id FROM slots')}
        destination.initialize()
        with destination.raw_connection() as remote:
            with remote.transaction():
                remote.execute('SELECT pg_advisory_xact_lock(1397771058)')
                cloud_registry = {(r['slot_id'],r['device_id']) for r in remote.execute('SELECT slot_id,device_id FROM slots')}
                if cloud_registry != registry:
                    raise ValueError('Slot registries differ')
                if any(remote.execute(f'SELECT COUNT(*) AS n FROM {t}').fetchone()['n'] for t in tables):
                    raise ValueError('Cloud database is not empty; refusing to overwrite or merge history')
                for table in tables:
                    cursor = local.execute(f'SELECT * FROM {table} ORDER BY 1')
                    columns = [column[0] for column in cursor.description]
                    statement = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join(['%s']*len(columns))})"
                    counts[table] = 0
                    while batch := cursor.fetchmany(250):
                        with remote.cursor() as writer:
                            writer.executemany(statement, [tuple(row) for row in batch])
                        counts[table] += len(batch)
                    if remote.execute(f'SELECT COUNT(*) AS n FROM {table}').fetchone()['n'] != counts[table]:
                        raise ValueError('Copied row count mismatch')
                for table in tables[:2]:
                    remote.execute(f"SELECT setval(pg_get_serial_sequence('smartparking.{table}','id'), COALESCE(MAX(id),1), COUNT(*)>0) FROM {table}")
                # Compare canonical rows, not just counts, before committing.
                for table in tables:
                    old = local.execute(f'SELECT * FROM {table} ORDER BY 1')
                    new = iter(remote.execute(f'SELECT * FROM {table} ORDER BY 1'))
                    for row in old:
                        if dict(row) != next(new, None):
                            raise ValueError('Copied history content mismatch')
                    if next(new, None) is not None:
                        raise ValueError('Unexpected extra cloud history')
                if hashlib.sha256(source.read_bytes()).hexdigest() != before:
                    raise ValueError('Source changed during copy; cloud transaction rolled back')
    return {'source_sha256': before, 'source_unchanged': True, 'copied_rows': counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    arguments = parser.parse_args()
    settings = Settings.from_env()
    if not settings.database_url:
        raise SystemExit('DATABASE_URL required; no destination created')
    import json
    result = copy_history(arguments.source, PostgresDatabase(settings.database_url, settings.database_timeout))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
