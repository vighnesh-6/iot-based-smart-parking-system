"""Atomic snapshots, durable duplicate detection, and short-lived SQLite connections."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import sqlite3

from backend.config import DEVICES, safe_database_path

APPLICATION_ID = 0x53504B32
SCHEMA_VERSION = 1


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


SCHEMA = """
CREATE TABLE slots (
 slot_id TEXT PRIMARY KEY, device_id TEXT NOT NULL,
 UNIQUE(slot_id, device_id)
);
CREATE TABLE telemetry_messages (
 id INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL UNIQUE,
 device_id TEXT NOT NULL, sequence INTEGER NOT NULL CHECK(sequence BETWEEN 0 AND 4294967295),
 uptime_ms INTEGER NOT NULL CHECK(uptime_ms BETWEEN 0 AND 4294967295),
 published_at TEXT, clock_synced INTEGER NOT NULL CHECK(clock_synced IN (0,1)),
 received_at TEXT NOT NULL, inferred_session INTEGER NOT NULL,
 applied_current INTEGER NOT NULL CHECK(applied_current IN (0,1))
);
CREATE TABLE occupancy_observations (
 id INTEGER PRIMARY KEY, message_id INTEGER NOT NULL REFERENCES telemetry_messages(id),
 slot_id TEXT NOT NULL REFERENCES slots(slot_id), distance_cm REAL,
 occupancy_status TEXT NOT NULL CHECK(occupancy_status IN ('OCCUPIED','VACANT','UNKNOWN')),
 measured_at TEXT, UNIQUE(message_id, slot_id),
 CHECK((occupancy_status='UNKNOWN' AND distance_cm IS NULL) OR
       (occupancy_status IN ('OCCUPIED','VACANT') AND distance_cm BETWEEN 2 AND 400 AND distance_cm IS NOT NULL))
);
CREATE TABLE slot_current (
 slot_id TEXT PRIMARY KEY REFERENCES slots(slot_id),
 observation_id INTEGER NOT NULL UNIQUE REFERENCES occupancy_observations(id)
);
CREATE INDEX history_slot_id ON occupancy_observations(slot_id, id);
CREATE INDEX message_device_id ON telemetry_messages(device_id, id);
CREATE INDEX message_received_at ON telemetry_messages(received_at);
"""


class Database:
    def __init__(self, path, timeout=2.0):
        self.path = safe_database_path(path)
        self.timeout = timeout

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True,
                                     timeout=self.timeout, isolation_level=None)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA synchronous=FULL")
            yield connection
        finally:
            connection.close()

    def initialize(self):
        """Create only a new file. Refuse unknown existing databases without writes."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.path.open("xb"):
                pass
        except FileExistsError:
            connection = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)
            try:
                app_id = connection.execute("PRAGMA application_id").fetchone()[0]
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if app_id != APPLICATION_ID or version != SCHEMA_VERSION:
                    raise ValueError("Existing database is unrecognized; preserved unchanged. Choose a new DATABASE_PATH.")
                required = {"slots", "telemetry_messages", "occupancy_observations", "slot_current"}
                actual = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if not required.issubset(actual):
                    raise ValueError("Existing schema is incomplete; preserved unchanged")
                registry = set(connection.execute("SELECT slot_id,device_id FROM slots").fetchall())
                if registry != {(s, d) for d, slots in DEVICES.items() for s in slots}:
                    raise ValueError("Existing slot registry does not match the twelve-slot architecture")
                if connection.execute("PRAGMA journal_mode").fetchone()[0].lower() != "delete":
                    raise ValueError("Existing journal mode requires explicit review; database preserved")
            finally:
                connection.close()
            return
        with self.connection() as connection:
            # No migrations or destructive reinitialization of an existing file.
            connection.executescript("BEGIN IMMEDIATE;\n" + SCHEMA)
            try:
                connection.executemany("INSERT INTO slots VALUES (?,?)",
                                       [(s, d) for d, slots in DEVICES.items() for s in slots])
                connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
                connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def persist(self, telemetry, received_at=None):
        received_at = received_at or now_utc()
        canonical = telemetry.model_dump()
        canonical["slots"] = sorted(canonical["slots"], key=lambda s: s["slot_id"])
        fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                                               allow_nan=False).encode()).hexdigest()
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                if connection.execute("SELECT 1 FROM telemetry_messages WHERE fingerprint=?", (fingerprint,)).fetchone():
                    connection.rollback()
                    return "duplicate"
                last = connection.execute(
                    "SELECT * FROM telemetry_messages WHERE device_id=? AND applied_current=1 ORDER BY id DESC LIMIT 1",
                    (telemetry.device_id,)).fetchone()
                session, apply = (last["inferred_session"] if last else 0), True
                if last:
                    # Device timestamps can be absent; never claim definitive boot identity.
                    if telemetry.timestamp and last["published_at"] and telemetry.timestamp < last["published_at"]:
                        apply = False
                    elif telemetry.sequence > last["sequence"]:
                        apply = True
                    elif telemetry.sequence < last["sequence"] and telemetry.uptime_ms < last["uptime_ms"]:
                        # A near-boot low sequence suggests reset; older non-boot data stays history-only.
                        if telemetry.sequence <= 2:
                            session += 1
                        else:
                            apply = False
                    elif telemetry.sequence < last["sequence"] and last["sequence"] > 0xF0000000 and telemetry.sequence < 0x0FFFFFFF:
                        session += 1
                    else:
                        apply = False
                cursor = connection.execute(
                    "INSERT INTO telemetry_messages(fingerprint,device_id,sequence,uptime_ms,published_at,clock_synced,received_at,inferred_session,applied_current) VALUES (?,?,?,?,?,?,?,?,?)",
                    (fingerprint, telemetry.device_id, telemetry.sequence, telemetry.uptime_ms,
                     telemetry.timestamp, int(telemetry.clock_synced), received_at, session, int(apply)))
                message_id = cursor.lastrowid
                for slot in telemetry.slots:
                    observation = connection.execute(
                        "INSERT INTO occupancy_observations(message_id,slot_id,distance_cm,occupancy_status,measured_at) VALUES (?,?,?,?,?)",
                        (message_id, slot.slot_id, slot.distance_cm, slot.occupancy_status, slot.timestamp))
                    if apply:
                        connection.execute("INSERT INTO slot_current VALUES (?,?) ON CONFLICT(slot_id) DO UPDATE SET observation_id=excluded.observation_id",
                                           (slot.slot_id, observation.lastrowid))
                connection.commit()
                return "stored" if apply else "history_only"
            except Exception:
                connection.rollback()
                raise

    def current(self, stale_seconds=30):
        with self.connection() as connection:
            rows = connection.execute("""SELECT s.slot_id,s.device_id,o.occupancy_status,o.distance_cm,
                o.measured_at,m.received_at,m.sequence FROM slots s
                LEFT JOIN slot_current c ON c.slot_id=s.slot_id
                LEFT JOIN occupancy_observations o ON o.id=c.observation_id
                LEFT JOIN telemetry_messages m ON m.id=o.message_id
                ORDER BY CAST(SUBSTR(s.slot_id,2) AS INTEGER)""").fetchall()
        result = []
        now = datetime.now(timezone.utc)
        for row in rows:
            item = dict(row)
            item["observed"] = item["received_at"] is not None
            item["stale"] = not item["observed"] or (now-datetime.fromisoformat(item["received_at"].replace("Z", "+00:00"))).total_seconds() > stale_seconds
            item["occupancy_status"] = item["occupancy_status"] or "UNKNOWN"
            result.append(item)
        return result

    def history(self, *, slot_id=None, device_id=None, state=None, since=None, until=None, limit=100, offset=0):
        clauses, values = [], []
        for column, value, operator in [("o.slot_id",slot_id,"="),("m.device_id",device_id,"="),
                                         ("o.occupancy_status",state,"="),("m.received_at",since,">="),
                                         ("m.received_at",until,"<=")]:
            if value is not None:
                clauses.append(f"{column} {operator} ?")
                values.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        base = " FROM occupancy_observations o JOIN telemetry_messages m ON m.id=o.message_id"
        with self.connection() as connection:
            connection.execute("BEGIN")
            total = connection.execute("SELECT COUNT(*)"+base+where, values).fetchone()[0]
            rows = connection.execute("SELECT o.*,m.device_id,m.sequence,m.uptime_ms,m.published_at,m.received_at,m.inferred_session,m.applied_current"+base+where+" ORDER BY o.id DESC LIMIT ? OFFSET ?", values+[limit,offset]).fetchall()
            return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}

    def healthy(self):
        with self.connection() as connection:
            return connection.execute("SELECT COUNT(*) FROM slots").fetchone()[0] == 12


def statistics(slots):
    fresh = [s for s in slots if not s["stale"]]
    occupied = sum(s["occupancy_status"] == "OCCUPIED" for s in fresh)
    vacant = sum(s["occupancy_status"] == "VACANT" for s in fresh)
    return {"total_slots": 12, "occupied": occupied, "vacant": vacant,
            "unknown": 12-occupied-vacant, "stale": sum(s["stale"] for s in slots),
            "unseen": sum(not s["observed"] for s in slots),
            "occupancy_percent_of_total": round(100*occupied/12, 2)}
