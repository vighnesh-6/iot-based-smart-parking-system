"""One-time copy into an EMPTY dedicated cloud database; source always read-only.

Run only from an approved runtime containing psycopg, before cloud MQTT starts.
Credentials are read from DATABASE_URL, never command arguments or output.
"""
import argparse
from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3

from backend.config import Settings
from backend.db import APPLICATION_ID, SCHEMA_VERSION
from backend.postgres import PostgresDatabase


def export_sql(source):
    """Driver-free export for the Neon SQL editor; never installs a laptop package."""
    source = Path(source).resolve(strict=True)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    lines = ["BEGIN;", "SET standard_conforming_strings=on;", "SET search_path TO smartparking,public;",
        "SELECT pg_advisory_xact_lock(1397771058);",
        "DO $guard$ BEGIN IF (SELECT COUNT(*) FROM cloud_metadata WHERE version=1)<>1 OR EXISTS(SELECT 1 FROM telemetry_messages) OR EXISTS(SELECT 1 FROM occupancy_observations) OR EXISTS(SELECT 1 FROM slot_current) THEN RAISE EXCEPTION 'Destination must be recognized and empty'; END IF; END $guard$;"]
    counts = {}
    def literal(value):
        if value is None: return 'NULL'
        if isinstance(value,str): return "'" + value.replace("'", "''") + "'"
        if isinstance(value,(int,float)): return repr(value)
        raise ValueError('Unsupported source value')
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as connection:
        connection.execute('BEGIN')
        if connection.execute('PRAGMA application_id').fetchone()[0]!=APPLICATION_ID or connection.execute('PRAGMA user_version').fetchone()[0]!=SCHEMA_VERSION:
            raise ValueError('Unrecognized source database')
        for table in ('telemetry_messages','occupancy_observations','slot_current'):
            rows = connection.execute(f'SELECT * FROM {table} ORDER BY 1')
            columns = ','.join(c[0] for c in rows.description)
            counts[table] = 0
            for row in rows:
                lines.append(f'INSERT INTO {table} ({columns}) VALUES ('+','.join(literal(v) for v in row)+');')
                counts[table] += 1
        for table in ('telemetry_messages','occupancy_observations'):
            lines.append(f"SELECT setval(pg_get_serial_sequence('smartparking.{table}','id'),COALESCE(MAX(id),1),COUNT(*)>0) FROM {table};")
        for table,count in counts.items():
            lines.append(f"DO $guard$ BEGIN IF (SELECT COUNT(*) FROM {table})<>{count} THEN RAISE EXCEPTION 'Copied count mismatch'; END IF; END $guard$;")
    if hashlib.sha256(source.read_bytes()).hexdigest()!=before:
        raise ValueError('Source changed during export; no export accepted')
    lines.append('COMMIT;')
    return '\n'.join(lines)+'\n', {'source_sha256':before,'source_unchanged':True,'copied_rows':counts}


def copy_history(source, destination):
    source = Path(source).resolve(strict=True)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    tables = ('telemetry_messages', 'occupancy_observations', 'slot_current')
    counts = {}
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as local:
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
    parser.add_argument('--export-sql', help='Write a new ignored SQL file for the Neon SQL editor; no driver or network required')
    arguments = parser.parse_args()
    import json
    if arguments.export_sql:
        script, result = export_sql(arguments.source)
        with Path(arguments.export_sql).open('x',encoding='utf-8') as output:
            output.write(script)
        print(json.dumps(result))
        return
    settings = Settings.from_env()
    if not settings.database_url:
        raise SystemExit('DATABASE_URL required; no destination created')
    result = copy_history(arguments.source, PostgresDatabase(settings.database_url, settings.database_timeout))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
