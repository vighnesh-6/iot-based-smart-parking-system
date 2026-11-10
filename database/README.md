# Runtime database location

This directory documents storage policy; it must not hold the live database.

Use `%LOCALAPPDATA%\SmartParking\parking.db` on Windows, outside the
OneDrive-synchronized project. The `.env.example` template uses
`${LOCALAPPDATA}/SmartParking/parking.db` for python-dotenv expansion during
the future backend setup. The future backend must resolve an absolute path.

Phase 2 initializes the schema on backend startup, not during module import.
It creates only a new database file. An existing database must have the known
application ID, schema version, twelve-slot registry and expected journal mode;
otherwise startup fails and preserves it unchanged. There are no destructive
migrations or automatic resets. Choose a new filename when an unrelated or
incomplete database is encountered; retain the original for review.

The schema is owned by `backend/db.py`:

| Table | Contents |
| --- | --- |
| slots | Fixed P1-P12 identities and device assignment |
| telemetry_messages | Canonical fingerprint, sequence, uptime, publish/receive times, inferred session and current-application flag |
| occupancy_observations | Four historical slot observations per accepted message |
| slot_current | Pointer to each slot's latest accepted observation |

Each message commits atomically. Durable fingerprints suppress duplicate history
and do not refresh freshness. Late snapshots may be stored as history-only.
Foreign keys, range/state constraints, indexes, full synchronous writes and a
bounded connection lock timeout are enabled. Connections are short-lived and
never shared between request and ingestion threads.

Rollback journaling (`DELETE`) is intentional: the preserved Python installation
contains SQLite 3.49.1, within the versions affected by SQLite's documented
[WAL-reset concurrency bug](https://sqlite.org/wal.html#the_wal_reset_bug).
The backend does not automatically change an existing database's journal mode.
Use a single Uvicorn worker. Continuous history is retained; no automatic pruning
or database deletion is implemented. Monitor disk space and archive deliberately.

Back up a running SQLite database with a consistent backup method, or stop it
cleanly before exporting; do not synchronize an open database and its journals.
Use SQLite's backup API to a new destination outside OneDrive. Never replace an
existing backup or database without a separate deliberate decision. Ordinary
ingestion appends history and updates current pointers in a recognized database.

Live database files and journals are ignored by Git. Synthetic ML history
belongs in `ml/data/`, with explicit source metadata, not in live readings.
