"""Causal features and purged 70/15/15 chronological partitioning."""

import numpy as np
import pandas as pd

from ml.generate_data import SLOTS

HORIZON = 15
LAGS = (1,5,15,30,60,1440,10080)
MEAN_WINDOWS = (5,15,60,1440)
STD_WINDOWS = (15,60)
WARMUP = max(LAGS)
FEATURE_COLUMNS = (*SLOTS,"total_occupied","arrivals","departures","hour","minute","day_of_week",
                   "is_weekend","time_sin","time_cos","week_sin","week_cos",
                   *(f"occupied_lag_{lag}" for lag in LAGS),
                   *(f"occupied_mean_{window}" for window in MEAN_WINDOWS),
                   *(f"occupied_std_{window}" for window in STD_WINDOWS),"occupied_change_15")
METADATA_COLUMNS = ("timestamp","data_source","target_timestamp","occupied_15min_ahead","split")


def engineer_features(raw):
    """Features at t use only observations at or before t; no fitting/global statistics."""
    result = raw.copy(deep=False)
    times = raw["timestamp"].dt
    result["hour"] = times.hour.astype("uint8")
    result["minute"] = times.minute.astype("uint8")
    result["day_of_week"] = times.day_of_week.astype("uint8")
    result["is_weekend"] = (times.day_of_week >= 5).astype("uint8")
    minute_of_day = times.hour*60+times.minute
    result["time_sin"] = np.sin(2*np.pi*minute_of_day/1440).astype("float32")
    result["time_cos"] = np.cos(2*np.pi*minute_of_day/1440).astype("float32")
    result["week_sin"] = np.sin(2*np.pi*times.day_of_week/7).astype("float32")
    result["week_cos"] = np.cos(2*np.pi*times.day_of_week/7).astype("float32")
    total = raw["total_occupied"]
    for lag in LAGS:
        result[f"occupied_lag_{lag}"] = total.shift(lag).astype("float32")
    history = total.shift(1)  # Rolling windows end at t-1, never at a future minute.
    for window in MEAN_WINDOWS:
        result[f"occupied_mean_{window}"] = history.rolling(window,min_periods=window).mean().astype("float32")
    for window in STD_WINDOWS:
        result[f"occupied_std_{window}"] = history.rolling(window,min_periods=window).std(ddof=0).astype("float32")
    result["occupied_change_15"] = (total.astype("float32")-total.shift(15)).astype("float32")
    return result


def split_counts(eligible_count):
    # Reserve the two 15-minute boundary gaps first; then allocate final usable rows.
    usable = eligible_count-2*HORIZON
    if usable < 100:
        raise ValueError("Insufficient feature-complete observations")
    train = int(usable*0.70)
    validation = int(usable*0.15)
    return train, validation, usable-train-validation


def prepare(raw):
    timestamps = raw["timestamp"]
    if timestamps.isna().any() or not timestamps.is_unique or not timestamps.is_monotonic_increasing:
        raise ValueError("Timestamps must be unique, ordered and nonmissing")
    if not timestamps.diff().iloc[1:].eq(pd.Timedelta(minutes=1)).all():
        raise ValueError("Every adjacent observation must be exactly one minute apart")
    if set(raw["data_source"].astype(str)) != {"synthetic"}:
        raise ValueError("This preparation path accepts only explicitly synthetic history")
    features = engineer_features(raw)
    features["target_timestamp"] = timestamps.shift(-HORIZON)
    features["occupied_15min_ahead"] = raw["total_occupied"].shift(-HORIZON)
    n = len(raw)
    counts = split_counts(n-WARMUP-HORIZON)
    labels = np.full(n,"excluded",dtype=object)
    cursor = WARMUP
    boundaries = {}
    for name,count in zip(("train","validation","test"),counts):
        labels[cursor:cursor+count] = name
        boundaries[name] = {"start_raw_index":cursor,"end_raw_index_exclusive":cursor+count,"rows":count}
        cursor += count+(HORIZON if name != "test" else 0)
    if cursor != n-HORIZON:
        raise ValueError("Split arithmetic does not cover the eligible timeline")
    features["split"] = pd.Categorical(labels,categories=["train","validation","test","excluded"],ordered=True)
    output = features.loc[labels != "excluded",["timestamp","data_source",*FEATURE_COLUMNS,
                          "target_timestamp","occupied_15min_ahead","split"]].reset_index(drop=True)
    output["occupied_15min_ahead"] = output["occupied_15min_ahead"].astype("uint8")
    if output.isna().any().any():
        raise ValueError("Missing feature or target after warmup/purge removal")
    return output, boundaries
