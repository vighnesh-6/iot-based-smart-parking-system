"""Strict firmware-v1 telemetry validation and documented HTTP response models."""

from datetime import datetime
import json
import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.config import DEVICES

State = Literal["OCCUPIED", "VACANT", "UNKNOWN"]


def utc_timestamp(value):
    if value is None:
        return value
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise ValueError("Expected firmware UTC timestamp YYYY-MM-DDTHH:MM:SSZ or null")
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)


class SlotReading(StrictModel):
    slot_id: str
    distance_cm: float | None
    occupancy_status: State
    timestamp: str | None

    _timestamp = field_validator("timestamp")(utc_timestamp)

    @field_validator("distance_cm", mode="before")
    @classmethod
    def numeric_distance(cls, value):
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
            raise ValueError("Distance must be finite numeric or null")
        return value

    @model_validator(mode="after")
    def valid_state(self):
        if self.occupancy_status == "UNKNOWN":
            if self.distance_cm is not None:
                raise ValueError("UNKNOWN requires null distance")
        elif self.distance_cm is None or not 2 <= self.distance_cm <= 400:
            raise ValueError("Known state requires distance between 2 and 400 cm")
        return self


class Telemetry(StrictModel):
    schema_version: int = Field(ge=1, le=1)
    device_id: str
    sequence: int = Field(ge=0, le=4294967295)
    timestamp: str | None
    clock_synced: bool
    uptime_ms: int = Field(ge=0, le=4294967295)
    slots: list[SlotReading] = Field(min_length=4, max_length=4)

    _timestamp = field_validator("timestamp")(utc_timestamp)

    @model_validator(mode="after")
    def identity_and_clock(self):
        if self.device_id not in DEVICES:
            raise ValueError("Unknown device")
        if {s.slot_id for s in self.slots} != set(DEVICES[self.device_id]):
            raise ValueError("Four distinct slots must match the assigned device")
        if self.clock_synced != (self.timestamp is not None):
            raise ValueError("clock_synced must agree with publication timestamp")
        return self


def parse_telemetry(payload: bytes, expected_device: str) -> Telemetry:
    if not payload or len(payload) > 4096:
        raise ValueError("Payload must contain 1-4096 bytes")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result

    def nonfinite(_value):
        raise ValueError("Nonfinite JSON constant")

    data = json.loads(payload.decode("utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)
    telemetry = Telemetry.model_validate(data)
    if telemetry.device_id != expected_device:
        raise ValueError("MQTT topic and device_id disagree")
    return telemetry


class SlotStatus(BaseModel):
    slot_id: str
    device_id: str
    occupancy_status: State
    distance_cm: float | None
    measured_at: str | None
    received_at: str | None
    sequence: int | None
    stale: bool
    observed: bool


class HistoryPage(BaseModel):
    items: list[dict]
    limit: int
    offset: int
    total: int


class Statistics(BaseModel):
    total_slots: int
    occupied: int
    vacant: int
    unknown: int
    stale: int
    unseen: int
    occupancy_percent_of_total: float
