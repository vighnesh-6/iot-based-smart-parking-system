"""Seeded semi-Markov parking simulation; synthetic only, never live telemetry."""

import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

SLOTS = tuple(f"P{i}" for i in range(1, 13))
SEED = 42
START = "2026-09-14 00:00:00"
TIMEZONE = "Asia/Kolkata"
DAYS = 56
SOURCE = "synthetic"
RAW_COLUMNS = ("timestamp", "data_source", *SLOTS, "total_occupied", "arrivals", "departures")


def generate(seed=SEED, days=DAYS):
    if type(days) is not int or days < 1:
        raise ValueError("days must be a positive integer")
    rng = np.random.default_rng(seed)
    n = days*1440
    timestamps = pd.date_range(START, periods=n, freq="min", tz=TIMEZONE)
    states = np.zeros((n, 12), dtype=np.uint8)
    arrivals = np.zeros(n, dtype=np.uint8)
    departures = np.zeros(n, dtype=np.uint8)
    # Unequal slot preference; no deterministic reserved or missing slots.
    preference = np.linspace(1.15, 0.85, 12)
    daily_demand = rng.lognormal(mean=-0.5*0.18**2, sigma=0.18, size=days)
    departure_at = np.full(12, -1, dtype=np.int32)
    occupied = np.zeros(12, dtype=bool)
    for t in range(n):
        previous = occupied.copy()
        leaving = occupied & (departure_at <= t)
        occupied[leaving] = False
        departures[t] = leaving.sum()
        hour = (t % 1440)/60
        weekday = timestamps[t].day_of_week < 5
        if weekday:
            rate = (0.0015 + 0.055*np.exp(-0.5*((hour-8.8)/1.25)**2)
                    + 0.025*np.exp(-0.5*((hour-13)/1.8)**2)
                    + 0.015*np.exp(-0.5*((hour-17.5)/1.5)**2))
        else:
            rate = (0.001 + 0.025*np.exp(-0.5*((hour-12.8)/2.3)**2)
                    + 0.015*np.exp(-0.5*((hour-18)/1.5)**2))
        demand = int(rng.poisson(rate*daily_demand[t//1440]))
        # Exclude just-departed slots: every arrival/departure is visible at 1-minute resolution.
        available = np.flatnonzero(~previous & ~occupied)
        if demand and len(available):
            chosen = rng.choice(available, size=min(demand,len(available)), replace=False,
                                p=preference[available]/preference[available].sum())
            for slot in chosen:
                mean_duration = 300 if weekday and 6 <= hour < 11 else (110 if weekday else 100)
                duration = int(np.clip(round(rng.lognormal(np.log(mean_duration)-0.5*0.5**2,0.5)),10,720))
                departure_at[slot] = t+duration
                occupied[slot] = True
            arrivals[t] = len(chosen)
        states[t] = occupied
    frame = pd.DataFrame(states, columns=SLOTS, copy=False)
    frame.insert(0,"data_source",pd.Categorical([SOURCE]*n))
    frame.insert(0,"timestamp",timestamps)
    frame["total_occupied"] = states.sum(axis=1).astype("uint8")
    frame["arrivals"], frame["departures"] = arrivals, departures
    return frame


def read_raw(path):
    # Check before narrowing: uint8 parsing could silently wrap invalid values.
    numeric = {name:"float64" for name in (*SLOTS,"total_occupied","arrivals","departures")}
    frame = pd.read_csv(path,dtype={**numeric,"data_source":"category"})
    if tuple(frame.columns) != RAW_COLUMNS:
        raise ValueError("Unexpected raw schema")
    if frame.isna().any().any() or not all(frame[s].isin([0,1]).all() for s in SLOTS):
        raise ValueError("Missing values or nonbinary slot state")
    for name in numeric:
        if not frame[name].between(0,12).all() or not frame[name].mod(1).eq(0).all():
            raise ValueError("Invalid occupancy/count value")
        frame[name] = frame[name].astype("uint8")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"],utc=True).dt.tz_convert(TIMEZONE)
    return frame


def content_digest(frame):
    digest = hashlib.sha256()
    digest.update(frame["timestamp"].astype("int64").to_numpy().tobytes())
    digest.update(frame[list(SLOTS)+["total_occupied","arrivals","departures"]].to_numpy(dtype="uint8").tobytes())
    digest.update("|".join(frame["data_source"].astype(str).unique()).encode())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path("ml/data/synthetic_parking_8weeks_raw.csv"))
    args = parser.parse_args()
    if args.output.exists(): parser.error("Output exists; choose a new path, never overwrite observations")
    frame = generate()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",newline="",encoding="utf-8") as stream:
        frame.to_csv(stream,index=False,date_format="%Y-%m-%dT%H:%M:%S%z",lineterminator="\n")
    print(f"Synthetic rows={len(frame):,}; bytes={args.output.stat().st_size:,}; digest={content_digest(frame)}")


if __name__ == "__main__":
    main()
