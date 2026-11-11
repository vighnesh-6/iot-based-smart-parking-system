"""Independent full-artifact acceptance checks; failed critical checks exit nonzero."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.features import FEATURE_COLUMNS,HORIZON,LAGS,MEAN_WINDOWS,STD_WINDOWS,WARMUP,engineer_features,split_counts
from ml.generate_data import DAYS,SEED,SLOTS,SOURCE,content_digest,generate,read_raw
from ml.prepare_data import file_hash,read_processed


def validate(raw, processed, manifest):
    checks = {}
    def check(name, condition, evidence):
        checks[name] = {"status":"PASS" if bool(condition) else "FAIL","evidence":evidence}

    n = DAYS*1440
    time = raw["timestamp"]
    check("eight_weeks_one_minute",len(raw)==n and time.is_unique and time.is_monotonic_increasing
          and time.diff().iloc[1:].eq(pd.Timedelta(minutes=1)).all(),
          {"rows":len(raw),"expected_rows":n,"first":str(time.iloc[0]),"last":str(time.iloc[-1])})
    check("all_twelve_slots",all(s in raw and s in processed for s in SLOTS)
          and all(raw[s].isin([0,1]).all() for s in SLOTS),list(SLOTS))
    check("synthetic_provenance",set(raw["data_source"].astype(str))=={SOURCE}
          and set(processed["data_source"].astype(str))=={SOURCE},"All records explicitly synthetic; no live database input")
    check("missing_values_and_numeric_ranges",not raw.isna().any().any() and not processed.isna().any().any()
          and raw["total_occupied"].between(0,12).all()
          and processed["occupied_15min_ahead"].between(0,12).all()
          and all(np.isfinite(processed[c].to_numpy()).all() for c in FEATURE_COLUMNS),
          {"raw_missing":int(raw.isna().sum().sum()),"processed_missing":int(processed.isna().sum().sum())})
    values = raw[list(SLOTS)].to_numpy(dtype="int8")
    total = raw["total_occupied"].to_numpy()
    check("total_equals_slot_sum",np.array_equal(values.sum(axis=1),total),"Every raw minute checked, not a sample")
    changes = np.diff(values,axis=0,prepend=np.zeros((1,12),dtype="int8"))
    arrivals = (changes==1).sum(axis=1)
    departures = (changes==-1).sum(axis=1)
    slot_metrics = {}
    complete_durations = []
    for i,slot in enumerate(SLOTS):
        edges = np.diff(np.r_[0,values[:,i],0])
        starts, ends = np.flatnonzero(edges==1), np.flatnonzero(edges==-1)
        durations = [int(b-a) for a,b in zip(starts,ends) if b < len(raw)]
        complete_durations.extend(durations)
        slot_metrics[slot] = {"arrivals":int((changes[:,i]==1).sum()),"departures":int((changes[:,i]==-1).sum()),
                              "occupied_fraction":round(float(values[:,i].mean()),5)}
    check("slot_arrivals_departures_and_dwell",np.array_equal(arrivals,raw["arrivals"])
          and np.array_equal(departures,raw["departures"])
          and all(v["arrivals"]>0 and v["departures"]>0 for v in slot_metrics.values())
          and bool(complete_durations) and min(complete_durations)>=10 and max(complete_durations)<=720,
          {"per_slot":slot_metrics,"completed_stays":len(complete_durations),
           "dwell_min":min(complete_durations),"dwell_median":float(np.median(complete_durations)),"dwell_max":max(complete_durations)})
    weekday = time.dt.day_of_week<5
    business = time.dt.hour.between(9,16)
    night = time.dt.hour.between(0,4)
    patterns = {"weekday_business_mean":float(raw.loc[weekday & business,"total_occupied"].mean()),
                "weekend_business_mean":float(raw.loc[~weekday & business,"total_occupied"].mean()),
                "weekday_night_mean":float(raw.loc[weekday & night,"total_occupied"].mean()),
                "lag1_autocorrelation":float(raw["total_occupied"].autocorr(1))}
    check("synthetic_daily_weekly_patterns",patterns["weekday_business_mean"]>patterns["weekend_business_mean"]
          and patterns["weekday_business_mean"]>patterns["weekday_night_mean"]
          and patterns["lag1_autocorrelation"]>0.9,patterns)
    indices = pd.Index(time).get_indexer(processed["timestamp"])
    aligned = (indices>=0).all() and (indices+HORIZON<n).all()
    check("exact_fifteen_minute_target",aligned
          and processed["target_timestamp"].reset_index(drop=True).equals(time.iloc[indices+HORIZON].reset_index(drop=True))
          and np.array_equal(processed["occupied_15min_ahead"],total[indices+HORIZON])
          and (processed["target_timestamp"]-processed["timestamp"]).eq(pd.Timedelta(minutes=15)).all(),
          {"checked_rows":len(processed),"horizon_minutes":15})
    check("current_features_match_observation",all(np.array_equal(processed[c],raw[c].iloc[indices])
          for c in (*SLOTS,"total_occupied","arrivals","departures")),"Current state/count features compared against raw timestamp lookup")
    lag_checks = {str(lag):bool(np.array_equal(processed[f"occupied_lag_{lag}"],total[indices-lag])) for lag in LAGS}
    check("all_lags_are_past_only",all(lag_checks.values()),lag_checks)
    cumulative = np.r_[0,np.cumsum(total,dtype="float64")]
    square = np.r_[0,np.cumsum(total.astype("float64")**2)]
    rolling_checks = {}
    for window in sorted(set(MEAN_WINDOWS+STD_WINDOWS)):
        mean = (cumulative[indices]-cumulative[indices-window])/window
        if window in MEAN_WINDOWS:
            rolling_checks[f"mean_{window}"] = bool(np.allclose(processed[f"occupied_mean_{window}"],mean,atol=1e-5,rtol=0))
        if window in STD_WINDOWS:
            std = np.sqrt(np.maximum(0,(square[indices]-square[indices-window])/window-mean**2))
            rolling_checks[f"std_{window}"] = bool(np.allclose(processed[f"occupied_std_{window}"],std,atol=1e-5,rtol=0))
    check("all_rolling_windows_exclude_future",all(rolling_checks.values()),rolling_checks)
    t = processed["timestamp"].dt
    calendar_checks = {"hour":np.array_equal(processed["hour"],t.hour),"minute":np.array_equal(processed["minute"],t.minute),
        "day_of_week":np.array_equal(processed["day_of_week"],t.day_of_week),"is_weekend":np.array_equal(processed["is_weekend"],(t.day_of_week>=5).astype(int))}
    for name,angle in [("time",2*np.pi*(t.hour*60+t.minute)/1440),("week",2*np.pi*t.day_of_week/7)]:
        calendar_checks[name+"_sin"] = np.allclose(processed[name+"_sin"],np.sin(angle),atol=1e-6)
        calendar_checks[name+"_cos"] = np.allclose(processed[name+"_cos"],np.cos(angle),atol=1e-6)
    calendar_checks["occupied_change_15"] = np.array_equal(processed["occupied_change_15"],total[indices].astype(int)-total[indices-15])
    check("calendar_and_change_features",all(calendar_checks.values()),{k:bool(v) for k,v in calendar_checks.items()})
    # Intervene only in the future; compare every feature in the complete past prefix.
    cutoff = WARMUP+100
    scratch = raw.iloc[:cutoff+50].copy()
    baseline = engineer_features(scratch).loc[:cutoff,list(FEATURE_COLUMNS)]
    for slot in SLOTS: scratch.loc[cutoff+1:,slot] = 1-scratch.loc[cutoff+1:,slot]
    scratch.loc[cutoff+1:,"total_occupied"] = scratch.loc[cutoff+1:,list(SLOTS)].sum(axis=1).astype("uint8")
    scratch.loc[cutoff+1:,["arrivals","departures"]] = 0
    perturbed = engineer_features(scratch).loc[:cutoff,list(FEATURE_COLUMNS)]
    invariant = np.allclose(baseline.to_numpy(),perturbed.to_numpy(),equal_nan=True,atol=0,rtol=0)
    prefix = engineer_features(raw.iloc[:cutoff+1]).loc[:,list(FEATURE_COLUMNS)]
    check("future_intervention_and_prefix_invariance",invariant and np.allclose(baseline.to_numpy(),prefix.to_numpy(),equal_nan=True,atol=0,rtol=0),
          {"features_checked":len(FEATURE_COLUMNS),"past_rows_checked":cutoff+1,"future_rows_changed":49})
    groups = {name:processed.loc[processed["split"]==name,["timestamp","target_timestamp"]] for name in ["train","validation","test"]}
    counts = split_counts(n-WARMUP-HORIZON)
    split_evidence = {name:{"rows":len(group),"fraction":round(len(group)/len(processed),8),
                            "first":str(group["timestamp"].iloc[0]),"last":str(group["timestamp"].iloc[-1]),
                            "last_target":str(group["target_timestamp"].iloc[-1])} for name,group in groups.items()}
    boundaries_ok = all(len(groups[name])==count for name,count in zip(groups,counts))
    for left,right in [("train","validation"),("validation","test")]:
        boundaries_ok &= groups[left]["target_timestamp"].max()<groups[right]["timestamp"].min()
        boundaries_ok &= (groups[right]["timestamp"].min()-groups[left]["timestamp"].max())==pd.Timedelta(minutes=16)
    check("chronological_70_15_15_purged_boundaries",boundaries_ok and processed["timestamp"].is_unique
          and processed["timestamp"].is_monotonic_increasing,split_evidence)
    check("schema_predictor_allowlist",list(manifest["features"])==list(FEATURE_COLUMNS)
          and not {"target_timestamp","occupied_15min_ahead","split","data_source","timestamp"}.intersection(FEATURE_COLUMNS)
          and list(processed.columns)==["timestamp","data_source",*FEATURE_COLUMNS,"target_timestamp","occupied_15min_ahead","split"],
          {"predictor_count":len(FEATURE_COLUMNS),"no_fitted_transforms":True})
    regenerated = generate(seed=SEED)
    digest = content_digest(regenerated)
    check("fixed_seed_full_reproducibility",digest==content_digest(raw)==manifest["raw_content_digest"],
          {"seed":SEED,"regenerated_rows":len(regenerated),"content_sha256":digest})
    return checks


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest",type=Path,default=Path("ml/data/phase3_dataset_manifest.json"))
    parser.add_argument("--evidence",type=Path,default=Path("reports/evidence/phase3_dataset_validation.json"))
    parser.add_argument("--checklist",type=Path,default=Path("reports/phase3_acceptance_checklist.md"))
    args=parser.parse_args()
    if args.evidence.exists() or args.checklist.exists():parser.error("Evidence exists; select new output names")
    manifest=json.loads(args.manifest.read_text())
    raw=read_raw(manifest["raw_file"]["path"])
    processed=read_processed(manifest["processed_file"]["path"],manifest["schema"])
    checks=validate(raw,processed,manifest)
    hashes_ok=all(file_hash(info["path"])==info["sha256"] for info in [manifest["raw_file"],manifest["processed_file"]])
    checks["artifact_checksums"]={"status":"PASS" if hashes_ok else "FAIL","evidence":"Raw and processed files match generation manifest"}
    files=[p for folder in [Path("ml/data"),Path("ml/artifacts")] for p in folder.rglob("*") if p.is_file() and p.name!=".gitkeep"]
    sizes={p.as_posix():p.stat().st_size for p in files}
    total=sum(sizes.values())
    checks["storage_below_50_MB"]={"status":"PASS" if total<50_000_000 else "FAIL","evidence":{"files":sizes,"total_bytes":total,"limit_bytes":50_000_000,"model_artifacts_created":False}}
    passed=all(c["status"]=="PASS" for c in checks.values())
    record={"source":"actual_full_artifact_validation","data_source":"synthetic","checks":checks,"critical_passed":passed,
            "limitations":"Synthetic face-validity only; no calibration or real-world predictive validation"}
    args.evidence.parent.mkdir(parents=True,exist_ok=True)
    with args.evidence.open("x",encoding="utf-8") as stream:json.dump(record,stream,indent=2);stream.write("\n")
    lines=["# Phase 3 dataset acceptance checklist","","All listed data checks are critical. Synthetic data does not establish real-world performance.","","| Requirement | Result | Evidence |","| --- | --- | --- |"]
    lines += [f"| {name} | {check['status']} | phase3_dataset_validation.json: checks.{name} |" for name,check in checks.items()]
    lines += ["",f"Dataset acceptance: {'PASS' if passed else 'FAIL'}.","","Software tests, scope preservation and final PDF visual verification are recorded separately in phase3_final_checks.json."]
    with args.checklist.open("x",encoding="utf-8") as stream:stream.write("\n".join(lines)+"\n")
    print(json.dumps({"critical_passed":passed,"checks":{k:v["status"] for k,v in checks.items()},"storage_bytes":total},indent=2))
    return 0 if passed else 1


if __name__=="__main__":raise SystemExit(main())
