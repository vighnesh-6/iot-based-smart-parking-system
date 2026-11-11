"""Validate API snapshots and build causal receipt-time minute views."""
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from backend.db import statistics
from backend.schemas import SlotStatus
from ml.features import FEATURE_COLUMNS, WARMUP, engineer_features
from ml.generate_data import SLOTS, TIMEZONE


def slot_snapshot(payload, stale_seconds, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(payload, list) or len(payload) != 12:
        raise ValueError('API must return exactly twelve slots')
    slots = [SlotStatus.model_validate(value).model_dump() for value in payload]
    if {s['slot_id'] for s in slots} != set(SLOTS):
        raise ValueError('API slot identities must be P1-P12 without duplicates')
    for slot in slots:
        expected = f"esp32_{(int(slot['slot_id'][1:]) - 1) // 4 + 1:02d}"
        if slot['device_id'] != expected:
            raise ValueError('API slot/device assignment mismatch')
        distance = slot['distance_cm']
        if slot['occupancy_status'] != 'UNKNOWN' and (distance is None or not np.isfinite(distance) or not 2 <= distance <= 400):
            raise ValueError('Known states require a valid distance')
        if slot['occupancy_status'] == 'UNKNOWN' and distance is not None:
            raise ValueError('UNKNOWN requires an absent distance')
        age = None
        if slot['received_at']:
            received = datetime.fromisoformat(slot['received_at'].replace('Z', '+00:00'))
            if received.utcoffset() is None:
                raise ValueError('Receipt timestamps must include a timezone')
            age = (now - received).total_seconds()
        measured_age = None
        if slot['measured_at']:
            measured = datetime.fromisoformat(slot['measured_at'].replace('Z', '+00:00'))
            if measured.utcoffset() is None:
                raise ValueError('Measurement timestamps must include a timezone')
            measured_age = (now - measured).total_seconds()
        measurement_invalid = measured_age is not None and (measured_age > stale_seconds or measured_age < -2)
        slot['stale'] = slot['stale'] or not slot['observed'] or age is None or age > stale_seconds or age < -2 or measurement_invalid
        slot['reason'] = ('Never observed' if not slot['observed'] else
                          'Receipt clock is ahead' if age is not None and age < -2 else
                          'Measurement is old or its clock is ahead' if measurement_invalid else
                          'Stale reading' if slot['stale'] else
                          'Sensor returned UNKNOWN' if slot['occupancy_status'] == 'UNKNOWN' else
                          'Fresh receipt; measurement time unavailable' if measured_age is None else 'Fresh API telemetry')
        slot['display_status'] = 'UNKNOWN' if slot['stale'] else slot['occupancy_status']
        slot['age_seconds'] = age
        slot['measurement_age_seconds'] = measured_age
    slots.sort(key=lambda s: int(s['slot_id'][1:]))
    return slots, statistics(slots)


def minute_history(items, start, end, stale_seconds):
    """As-of join: each minute uses only accepted observations received by then.

    No interpolation; receipt-age tolerance applies separately to each slot.
    Input is bounded by API pagination. A missing slot remains NaN.
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if start.tz is None or end.tz is None or start > end:
        raise ValueError('Ordered timezone-aware history bounds required')
    grid = pd.date_range(start.ceil('min'), end.floor('min'), freq='min').tz_convert('UTC')
    result = pd.DataFrame({'timestamp': grid})
    if items:
        observations = pd.DataFrame(items)
        required = {'id', 'slot_id', 'received_at', 'occupancy_status', 'applied_current'}
        if not required.issubset(observations.columns):
            raise ValueError('History is missing required fields')
        if not observations.slot_id.isin(SLOTS).all() or not observations.occupancy_status.isin(['OCCUPIED', 'VACANT', 'UNKNOWN']).all():
            raise ValueError('History contains invalid slot/state values')
        if not observations.applied_current.isin([0, 1]).all() or not observations.id.is_unique:
            raise ValueError('Invalid acceptance flags or duplicate history IDs')
        observations['received_at'] = pd.to_datetime(observations.received_at, utc=True, errors='raise')
        if observations.received_at.isna().any():
            raise ValueError('History receipt timestamps cannot be missing')
        observations = observations.loc[observations.applied_current.eq(1)].sort_values(['received_at', 'id'])
    else:
        observations = pd.DataFrame()
    for slot in SLOTS:
        rows = observations.loc[observations.slot_id.eq(slot)] if len(observations) else observations
        if not len(rows):
            result[slot] = np.nan
            continue
        right = rows[['received_at', 'occupancy_status']].copy()
        right[slot] = right.occupancy_status.map({'OCCUPIED': 1.0, 'VACANT': 0.0})
        joined = pd.merge_asof(result[['timestamp']], right[['received_at', slot]],
            left_on='timestamp', right_on='received_at', direction='backward',
            tolerance=pd.Timedelta(seconds=stale_seconds))
        result[slot] = joined[slot].to_numpy()
    result['known_slots'] = result[list(SLOTS)].notna().sum(axis=1)
    result['total_occupied'] = result[list(SLOTS)].sum(axis=1, min_count=12)
    result['timestamp'] = result.timestamp.dt.tz_convert(TIMEZONE)
    result['data_source'] = 'api_telemetry'
    return result


def live_feature_record(history):
    if len(history) < WARMUP + 1:
        raise ValueError('At least seven days plus the current minute of valid history are required')
    if not history.timestamp.diff().iloc[1:].eq(pd.Timedelta(minutes=1)).all():
        raise ValueError('Minute history is not continuous')
    if not history[list(SLOTS)].isin([0, 1]).all().all():
        raise ValueError('History contains missing, stale or UNKNOWN slot observations')
    if not history.data_source.eq('api_telemetry').all():
        raise ValueError('Live prediction accepts API telemetry history only')
    if not history.total_occupied.eq(history[list(SLOTS)].sum(axis=1)).all():
        raise ValueError('History totals do not equal the sum of individual slots')
    raw = history[['timestamp', 'data_source', *SLOTS, 'total_occupied']].copy()
    changes = raw[list(SLOTS)].diff()
    raw['arrivals'] = changes.eq(1).sum(axis=1)
    raw['departures'] = changes.eq(-1).sum(axis=1)
    engineered = engineer_features(raw)
    latest = engineered.loc[:, list(FEATURE_COLUMNS)].iloc[-1]
    if not np.isfinite(latest.to_numpy(dtype='float64')).all():
        raise ValueError('Causal feature window is incomplete')
    return {name: float(latest[name]) for name in FEATURE_COLUMNS}


def slot_history(items, slot_id, start, end, stale_seconds):
    """Plot actual receipt events; explicit NaNs break UNKNOWN and expired gaps.

    Historical known readings do not expire merely because the viewer opens the
    chart later. Freshness limits how far a line can connect between events.
    Gap rows are chart separators, never synthetic observations or ML inputs.
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if slot_id not in SLOTS or start.tz is None or end.tz is None or start > end or stale_seconds <= 0:
        raise ValueError('Valid slot, timezone-aware ordered bounds and positive freshness required')
    points = []
    seen = set()
    for item in items:
        identity = item['id']
        if identity in seen:
            raise ValueError('Duplicate history ID')
        seen.add(identity)
        if item['slot_id'] not in SLOTS or item['occupancy_status'] not in ('OCCUPIED', 'VACANT', 'UNKNOWN') or item['applied_current'] not in (0, 1):
            raise ValueError('Invalid history identity, state or acceptance flag')
        stamp = pd.Timestamp(item['received_at'])
        if pd.isna(stamp) or stamp.tz is None:
            raise ValueError('Receipt timestamps must be present and timezone-aware')
        if item['slot_id'] == slot_id and item['applied_current'] == 1 and start <= stamp <= end:
            points.append((stamp.tz_convert('UTC'), identity, item['occupancy_status']))
    points.sort(key=lambda row: (row[0], row[1]))
    rows = []
    previous = None
    for stamp, identity, state in points:
        if previous is not None and stamp - previous > pd.Timedelta(seconds=stale_seconds):
            rows.append((previous + pd.Timedelta(seconds=stale_seconds), np.nan, None))
        rows.append((stamp, {'OCCUPIED': 1.0, 'VACANT': 0.0}.get(state, np.nan), identity))
        previous = stamp
    result = pd.DataFrame(rows, columns=['timestamp', slot_id, 'observation_id'])
    result['timestamp'] = pd.to_datetime(result.timestamp, utc=True).dt.tz_convert(TIMEZONE)
    return result
