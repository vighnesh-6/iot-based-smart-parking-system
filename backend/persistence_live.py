"""Separate deployment adapter for the exact Persistence rule; no ML feature padding."""
from datetime import datetime, timedelta, timezone
import math

from pydantic import BaseModel, Field, model_validator

from backend.config import DEVICES
from backend.schemas import SlotStatus

SLOTS = tuple(slot for assigned in DEVICES.values() for slot in assigned)
FRESHNESS_CEILING_SECONDS = 30


class PersistenceLiveResult(BaseModel):
    available: bool
    inference_path: str = 'persistence_only_live'
    model: str = 'persistence'
    data_source: str = 'api_sqlite_telemetry'
    horizon_minutes: int = 15
    evaluated_at: datetime
    prediction_timestamp: datetime | None = None
    target_timestamp: datetime | None = None
    current_occupied: int | None = Field(default=None, ge=0, le=12)
    predicted_occupied: int | None = Field(default=None, ge=0, le=12)
    freshness_limit_seconds: int = Field(ge=1, le=30)
    blockers: list[dict[str, str]]
    snapshot: list[SlotStatus]

    @model_validator(mode='after')
    def contract(self):
        if (self.inference_path, self.model, self.data_source, self.horizon_minutes) != (
                'persistence_only_live', 'persistence', 'api_sqlite_telemetry', 15):
            raise ValueError('Unexpected Persistence-only inference contract')
        if self.evaluated_at.utcoffset() is None:
            raise ValueError('Evaluation timestamp requires a timezone')
        if self.available:
            if self.blockers or self.current_occupied is None or self.predicted_occupied != self.current_occupied:
                raise ValueError('Available Persistence forecast requires equal complete counts and no blockers')
            if self.prediction_timestamp != self.evaluated_at or self.target_timestamp != self.evaluated_at + timedelta(minutes=15):
                raise ValueError('Forecast must target exactly fifteen minutes after evaluation')
            if len(self.snapshot) != 12 or {s.slot_id for s in self.snapshot} != set(SLOTS):
                raise ValueError('Complete twelve-slot snapshot required')
        elif any(v is not None for v in (self.current_occupied, self.predicted_occupied,
                                        self.prediction_timestamp, self.target_timestamp)):
            raise ValueError('Unavailable result cannot contain a forecast')
        return self


def persistence_live(snapshot, stale_seconds=30, now=None):
    """Read an already fetched SQLite snapshot; never open/write DB or train models.

    This exact parameter-free baseline is y(t+15)=occupied(t). It is a separate
    interface, not ParkingPredictor.predict or a fabricated 37-feature record.
    Both receipt and measurement clocks must be available and fresh.
    """
    now = now or datetime.now(timezone.utc)
    limit = min(stale_seconds, FRESHNESS_CEILING_SECONDS)
    blockers = []
    slots = [SlotStatus.model_validate(row) for row in snapshot]
    indexed = {s.slot_id: s for s in slots}
    if len(slots) != len(indexed) or set(indexed) - set(SLOTS):
        blockers.append({'slot_id': 'snapshot', 'reason': 'Duplicate or unexpected slot identities'})
    for number, slot_id in enumerate(SLOTS):
        slot = indexed.get(slot_id)
        reason = None
        if slot is None:
            reason = 'Missing slot observation'
        elif slot.device_id != f'esp32_{number // 4 + 1:02d}':
            reason = 'Slot/device assignment mismatch'
        elif not slot.observed:
            reason = 'Never observed'
        elif slot.stale:
            reason = 'Backend marks observation stale'
        elif slot.occupancy_status == 'UNKNOWN':
            reason = 'Sensor state is UNKNOWN'
        elif slot.distance_cm is None or not math.isfinite(slot.distance_cm) or not 2 <= slot.distance_cm <= 400:
            reason = 'Invalid known-state distance'
        else:
            for label, stamp in [('Receipt', slot.received_at), ('Measurement', slot.measured_at)]:
                if not stamp:
                    reason = f'{label} timestamp unavailable; freshness cannot be established'
                    break
                try:
                    value = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
                except ValueError:
                    reason = f'{label} timestamp is invalid'
                    break
                if value.utcoffset() is None:
                    reason = f'{label} timestamp lacks a timezone'
                    break
                age = (now - value).total_seconds()
                if age < -2 or age > limit:
                    reason = f'{label} is stale or its clock is ahead (age {age:.1f}s; limit {limit}s)'
                    break
        if reason:
            blockers.append({'slot_id': slot_id, 'reason': reason})
    occupied = sum(s.occupancy_status == 'OCCUPIED' for s in slots) if not blockers else None
    return PersistenceLiveResult(available=not blockers, evaluated_at=now,
        prediction_timestamp=now if not blockers else None,
        target_timestamp=now + timedelta(minutes=15) if not blockers else None,
        current_occupied=occupied, predicted_occupied=occupied,
        freshness_limit_seconds=limit, blockers=blockers, snapshot=slots)
