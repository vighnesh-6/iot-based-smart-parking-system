# Phase 3: historical dataset preparation

This is an explicitly **synthetic** offline dataset for a 15-minute-ahead
occupancy forecasting demonstration. It is not actual Wokwi telemetry and is
never written into the live SQLite database or MQTT topics. Phase 1/2 code,
reports and evidence remain frozen. No model or dashboard is implemented here;
`train.py` and the four title-only notebooks are unchanged.

## Reproduce and validate

From the repository root, using the existing environment:

```powershell
.\.venv\Scripts\python.exe -B -m ml.generate_data
.\.venv\Scripts\python.exe -B -m ml.prepare_data
.\.venv\Scripts\python.exe -B -m ml.validate_data
.\.venv\Scripts\python.exe -B -m unittest discover -s ml/tests -v
```

Outputs are exclusive-create: commands refuse to replace existing artifacts or
evidence. To reproduce beside the released dataset, choose new names:

```powershell
.\.venv\Scripts\python.exe -B -m ml.generate_data --output tmp/repro_raw.csv
.\.venv\Scripts\python.exe -B -m ml.prepare_data `
  --raw tmp/repro_raw.csv --output tmp/repro_ml.csv.gz --metadata tmp/repro_manifest.json
.\.venv\Scripts\python.exe -B -m ml.validate_data `
  --manifest tmp/repro_manifest.json --evidence tmp/repro_validation.json `
  --checklist tmp/repro_checklist.md
```

The full fixed-seed validation also regenerates raw data in memory. Tests
recompute the complete processed output into a hashing sink to verify identical
compressed bytes without storing a duplicate dataset. Temporary-directory tests
may need the execution environment to permit access to their private fixtures.

## Method and assumptions

- Fixed NumPy seed **42**, generator version 1; dependency versions are recorded
  in `data/phase3_dataset_manifest.json`.
- **2026-09-14 00:00 through 2026-11-08 23:59 Asia/Kolkata (IST)**, inclusive:
  56 days, 80,640 unique one-minute timestamps, exactly P1-P12 at every minute.
- Initial slots are vacant. Simulation state continues through midnight;
  there is no daily occupancy reset. Each minute processes departures, then
  Poisson arrival demand and assigns available slots with modest preferences.
  A just-departed slot cannot be reused in the same minute, keeping each state
  transition observable at one-minute resolution. Excess demand is lost; no
  queue, double parking or capacity overflow is generated.
- Weekdays have commute, midday and late-afternoon demand peaks. Weekends have
  weaker midday/evening leisure demand. A daily lognormal multiplier adds shared
  demand variation. Exact Gaussian peak coefficients are in `generate_data.py`.
- Occupied duration is sampled on arrival, independently of future observations:
  lognormal sigma 0.5, mean 300 minutes for weekday 06:00-11:00 arrivals, 110 for
  other weekday arrivals and 100 on weekends, rounded/clipped to 10-720 minutes.
  Only resulting observed states enter features; scheduled departures and latent
  demand/duration parameters are not exported as predictors.
- There are no injected sensor faults, UNKNOWN states, holidays, weather,
  special events, user identities or empirical site calibration. Occupied runs
  crossing dataset boundaries are censored for completed-dwell summaries.

These are reasonable illustrative assumptions, not fitted facts about the
project's parking site. Synthetic performance cannot substantiate real-world
forecast accuracy. This phase does not resolve pending Wokwi runtime issues.

## Outputs and schema

| File | Rows / bytes | Purpose |
| --- | --- | --- |
| `data/synthetic_parking_8weeks_raw.csv` | 80,640 / 5,245,712 | Timestamp, synthetic source, twelve states and observation counts |
| `data/synthetic_parking_8weeks_ml.csv.gz` | 70,515 / 2,077,563 | One processed ML-ready table with partition labels |
| `data/phase3_dataset_manifest.json` | 4,489 bytes | Parameters, schema, versions, hashes, counts and boundaries |

Total data/model artifact storage is **7,327,764 bytes (7.328 MB / 6.988 MiB)**,
below 50,000,000 bytes. No model artifact exists. The only full tables are the
requested raw and processed representations; no separate train/validation/test
files or processed uncompressed copy is saved. Measured DataFrame storage is
1,935,550 bytes raw and 7,757,235 bytes processed, not a peak-process-RAM claim.

Compressed CSV is a deliberate fallback: Windows Application Control blocks
the installed PyArrow DLL, even outside the restricted sandbox. No package or
security policy was changed. The preferred Zstandard Parquet path is implemented
but **not verified in this environment**; use the tested `.csv.gz` output here.
CSV gzip has fixed header mtime=0 and no filename, making the byte stream stable.

Raw columns:

| Columns | Meaning |
| --- | --- |
| `timestamp` | Local minute with explicit +0530 offset; timezone-aware on load |
| `data_source` | Always `synthetic` |
| `P1` through `P12` | uint8: 0 VACANT, 1 OCCUPIED |
| `total_occupied` | uint8 sum of P1-P12, range 0-12 |
| `arrivals`, `departures` | Visible 0->1 / 1->0 transitions that minute, range 0-12 |

Raw loading validates values before narrowing numeric types, avoiding integer
overflow hiding invalid input. Preparation rejects missing, duplicate, unsorted
or irregular timestamps and non-synthetic source values. Generated data requires
no imputation, backfilling or anomaly removal; initial feature gaps and target
tails are removed for declared reasons, never filled using future values.

## Features and target

There are **37 numeric predictor columns**, explicitly allowlisted by
`ml.features.FEATURE_COLUMNS`:

- Twelve current slot states, total occupancy, current arrivals/departures.
- Local hour, minute, weekday (Monday=0), weekend flag, daily and weekday
  sine/cosine encodings. Daily angle is `2*pi*(hour*60+minute)/1440`; weekly
  angle is `2*pi*weekday/7`.
- Occupancy lags at 1, 5, 15, 30, 60, 1,440 and 10,080 minutes.
- Occupancy trailing means over 5, 15, 60 and 1,440 minutes; population standard
  deviations over 15 and 60 minutes. Windows are `[t-window, t)`, using a one-row
  shift before rolling, with full-window minimum observations and ddof=0.
- Current total minus the 15-minute lag, calculated in signed/floating arithmetic.

At forecast origin t, observations at t are assumed available. Target
`occupied_15min_ahead = total_occupied(t+15 minutes)` and `target_timestamp`
records that exact future minute. The target, target timestamp, split, source
and raw timestamp are **not** predictors. Keep this allowlist for future training;
do not train on every numeric column indiscriminately.

There are no fitted scalers, imputers, global occupancy means, centered windows,
future-derived demand features or random splits. A later model phase must fit
any learned preprocessing on training data only. This phase uses one sequential
holdout design; it does not perform tuning or claim model performance.

## Chronological 70/15/15 partition

Remove 10,080 initial rows for the week lag and the final 15 targetless rows.
Reserve two 15-minute gaps before allocating final usable rows: 70% training,
15% validation, remainder testing, using integer floor for the first two counts.
This yields 70,515 rows with proportions differing from 70/15/15 only by rounding.

| Split | Rows | First origin IST | Last origin IST | Last target IST |
| --- | --- | --- | --- | --- |
| train | 49,360 | Sep 21 00:00 | Oct 25 06:39 | Oct 25 06:54 |
| validation | 10,577 | Oct 25 06:55 | Nov 1 15:11 | Nov 1 15:26 |
| test | 10,578 | Nov 1 15:27 | Nov 8 23:44 | Nov 8 23:59 |

Origins excluded at boundaries: Oct 25 06:40-06:54 and Nov 1 15:12-15:26.
The last target of a preceding partition is strictly before the next
partition's first origin. Past observations from earlier partitions and gaps
may supply later lags/rolling history: they would be known at forecast time.
No previous partition's training label reaches a later partition's origin.

## Actual verification

- **18 critical full-artifact checks passed**: timeline, all slots, provenance,
  missing/range checks, slot sum, transitions/dwell, daily/weekly patterns,
  exact targets, current/lag/rolling/calendar features, future intervention and
  prefix invariance, purged boundaries, allowlist, full fixed-seed regeneration,
  file hashes and storage budget.
- **21 software tests passed**, including altered future data, prefix-only
  recomputation, deterministic processed bytes, corrupt-count rejection,
  strict chronological input checks and refusal to overwrite existing output.
- All 12 slots have observed arrivals/departures: 77-100 each; 1,042 completed
  stays, observed dwell 21-720 minutes, median 141. Lag-one occupancy correlation
  is 0.99860, reflecting persistence.
- Mean occupied slots: weekday 09:00-16:59 = 6.4073; weekend same hours = 1.7805;
  weekday 00:00-04:59 = 0.2166. These are synthetic face-validity checks only.

See [acceptance checklist](../reports/phase3_acceptance_checklist.md),
[validation evidence](../reports/evidence/phase3_dataset_validation.json),
test/final-check JSON records and
[Phase 3 PDF](../reports/phase3_historical_dataset_preparation.pdf).

Future work: train/tune on training/validation only, preserve the untouched test
period for final evaluation, compare against persistence/seasonal baselines and
validate on real site observations before operational claims or integration.
