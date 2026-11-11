"""Match an archived single-board MQTT capture to existing SQLite rows, read-only."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.config import DEVICES, Settings, TOPICS
from backend.schemas import parse_telemetry


def verify(capture, device, minimum_duration, database_path):
    topic = next(topic for topic, assigned in TOPICS.items() if assigned == device)
    messages = [m for m in capture['messages'] if m['topic'] == topic]
    checks = []
    delays = []
    connection = sqlite3.connect(Path(database_path).resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        for message in messages:
            payload = message['payload']
            parsed = parse_telemetry(json.dumps(payload, allow_nan=False).encode(), device)
            candidates = connection.execute(
                'SELECT id,applied_current FROM telemetry_messages WHERE device_id=? AND sequence=? '
                'AND uptime_ms=? AND published_at IS ?',
                (device, parsed.sequence, parsed.uptime_ms, parsed.timestamp)).fetchall()
            expected = sorted([{'slot_id': s.slot_id, 'distance_cm': s.distance_cm,
                'occupancy_status': s.occupancy_status, 'measured_at': s.timestamp}
                for s in parsed.slots], key=lambda s: s['slot_id'])
            matches = []
            for candidate in candidates:
                rows = connection.execute('SELECT slot_id,distance_cm,occupancy_status,measured_at '
                    'FROM occupancy_observations WHERE message_id=? ORDER BY slot_id',
                    (candidate['id'],)).fetchall()
                if [dict(row) for row in rows] == expected:
                    matches.append(dict(candidate))
            checks.append({'sequence': parsed.sequence, 'uptime_ms': parsed.uptime_ms,
                           'sqlite_matches': matches})
            if parsed.timestamp:
                delays.append((datetime.fromisoformat(message['received_at_utc'].replace('Z', '+00:00'))
                    - datetime.fromisoformat(parsed.timestamp.replace('Z', '+00:00'))).total_seconds())
        integrity = connection.execute('PRAGMA quick_check').fetchone()[0]
        foreign_keys = len(connection.execute('PRAGMA foreign_key_check').fetchall())
        all_counts = {row['device_id']: row['n'] for row in connection.execute(
            'SELECT device_id,COUNT(*) n FROM telemetry_messages GROUP BY device_id')}
    finally:
        connection.close()
    sequences = [m['payload']['sequence'] for m in messages]
    applied_sequences = [x['sequence'] for x in checks if any(m['applied_current'] == 1
                         for m in x['sqlite_matches'])]
    device_intervals = capture['devices'][device]['device_intervals_ms']
    intervals = [(datetime.fromisoformat(b['received_at_utc'].replace('Z', '+00:00'))
        - datetime.fromisoformat(a['received_at_utc'].replace('Z', '+00:00'))).total_seconds()
        for a, b in zip(messages, messages[1:])]
    acceptance = {
        'capture_duration': capture['elapsed_seconds'] >= minimum_duration,
        'broker_and_subscription': capture['connack'] == 'Success' and len(capture['suback'] or []) == 3
            and all(v == 'Granted QoS 1' for v in capture['suback']),
        'no_invalid_payloads': not capture['errors'],
        'enough_messages': len(messages) >= int(minimum_duration / 10),
        # Firmware advances sequence only after PUBACK. An unacknowledged scan
        # can be observed, followed by a different scan with the same sequence.
        # SQLite retains both and applies only the first to current state.
        'sequence_progression': len(sequences) >= 2 and all(b >= a for a, b in zip(sequences, sequences[1:])),
        'applied_sequence_progression': len(applied_sequences) >= 2 and all(b > a
            for a, b in zip(applied_sequences, applied_sequences[1:])),
        'periodic_device_cadence': bool(device_intervals) and 4000 <= statistics.median(device_intervals) <= 10000,
        'receipt_cadence': bool(intervals) and 3 <= statistics.median(intervals) <= 10,
        'all_captured_messages_persisted': bool(checks) and all(x['sqlite_matches'] for x in checks),
        'sqlite_integrity': integrity == 'ok' and foreign_keys == 0,
    }
    return {'source': 'actual_sequential_mqtt_to_sqlite_verification', 'device_id': device,
        'topic': topic, 'slots': DEVICES[device], 'started_at_utc': capture['started_at_utc'],
        'ended_at_utc': capture['ended_at_utc'], 'duration_seconds': capture['elapsed_seconds'],
        'valid_messages': len(messages), 'sequences': sequences, 'receipt_intervals_seconds': intervals,
        'repeated_sequences': len(sequences) - len(set(sequences)),
        'history_only_messages': sum(bool(x['sqlite_matches']) and not any(m['applied_current'] == 1
            for m in x['sqlite_matches']) for x in checks),
        'strict_uninterrupted_cadence': capture['devices'][device]['periodic_device_cadence_passed'],
        'publication_age_seconds': {'min': min(delays), 'max': max(delays)} if delays else None,
        'message_database_matches': checks, 'database_device_counts_at_check': all_counts,
        'acceptance': acceptance, 'passed': all(acceptance.values()),
        'limitations': 'Sequential board test only; no simultaneous twelve-slot freshness, '
            'controlled reconnection, occupancy transitions or independent clock accuracy established.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--device', choices=DEVICES, required=True)
    parser.add_argument('--minimum-duration', type=int, choices=(60, 90), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(json.loads(args.capture.read_text(encoding='utf-8')), args.device,
                    args.minimum_duration, Settings.from_env().database_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'device_id': args.device, 'passed': result['passed'],
                      'messages': result['valid_messages'], 'acceptance': result['acceptance']}))
    raise SystemExit(0 if result['passed'] else 2)
