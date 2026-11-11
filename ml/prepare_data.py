"""Prepare one compact ML-ready file and its reproducibility/schema manifest."""

import argparse
import hashlib
import importlib.metadata
import json
import gzip
import io
from pathlib import Path

from ml.features import FEATURE_COLUMNS,HORIZON,WARMUP,prepare
from ml.generate_data import DAYS,SEED,START,TIMEZONE,content_digest,read_raw


def file_hash(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(65536),b""): digest.update(chunk)
    return digest.hexdigest()


def read_processed(path, schema):
    if Path(path).suffix==".parquet":return __import__("pandas").read_parquet(path)
    import pandas as pd
    dtypes={c:t for c,t in schema.items() if c not in {"timestamp","target_timestamp"}}
    frame=pd.read_csv(path,dtype=dtypes)
    for col in ["timestamp","target_timestamp"]:
        frame[col]=pd.to_datetime(frame[col],utc=True).dt.tz_convert(TIMEZONE)
    return frame


def write_processed(frame, stream, parquet=False):
    if parquet:
        frame.to_parquet(stream,index=False,compression="zstd")
    else:
        with gzip.GzipFile(filename="",fileobj=stream,mode="wb",mtime=0) as compressed:
            with io.TextIOWrapper(compressed,encoding="utf-8",newline="") as text:
                frame.to_csv(text,index=False,date_format="%Y-%m-%dT%H:%M:%S%z",float_format="%.9g",lineterminator="\n")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw",type=Path,default=Path("ml/data/synthetic_parking_8weeks_raw.csv"))
    parser.add_argument("--output",type=Path,default=Path("ml/data/synthetic_parking_8weeks_ml.csv.gz"))
    parser.add_argument("--metadata",type=Path,default=Path("ml/data/phase3_dataset_manifest.json"))
    args=parser.parse_args()
    if args.output.exists() or args.metadata.exists():parser.error("Outputs exist; choose new paths")
    if args.output.suffix==".parquet":
        import pyarrow  # Fail before creating any output when policy blocks the native DLL.
    elif not args.output.name.endswith(".csv.gz"):
        parser.error("Processed output must be .parquet or .csv.gz")
    raw=read_raw(args.raw)
    processed,boundaries=prepare(raw)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.metadata.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("xb") as stream:
        write_processed(processed,stream,parquet=args.output.suffix==".parquet")
    manifest={"generator_version":1,"seed":SEED,"days":DAYS,"start_local":START,"timezone":TIMEZONE,
              "data_source":"synthetic","raw_rows":len(raw),"processed_rows":len(processed),
              "serialization":"parquet_zstd" if args.output.suffix==".parquet" else "csv_gzip_deterministic_header",
              "format_note":"CSV gzip selected because Windows Application Control blocks the installed PyArrow DLL; policy and dependencies were not changed",
              "horizon_minutes":HORIZON,"warmup_rows":WARMUP,"purged_boundary_rows":2*HORIZON,
              "unlabelled_tail_rows":HORIZON,"split_boundaries":boundaries,
              "split_ratios_requested":[0.70,0.15,0.15],
              "features":list(FEATURE_COLUMNS),"target":"occupied_15min_ahead",
              "non_predictor_columns":["timestamp","data_source","target_timestamp","occupied_15min_ahead","split"],
              "schema":{col:str(dtype) for col,dtype in processed.dtypes.items()},
              "raw_content_digest":content_digest(raw),
              "raw_file":{"path":args.raw.as_posix(),"bytes":args.raw.stat().st_size,"sha256":file_hash(args.raw)},
              "processed_file":{"path":args.output.as_posix(),"bytes":args.output.stat().st_size,"sha256":file_hash(args.output)},
              "dataframe_bytes":{"raw":int(raw.memory_usage(deep=True).sum()),"processed":int(processed.memory_usage(deep=True).sum())},
              "versions":{name:importlib.metadata.version(name) for name in ["numpy","pandas","pyarrow"]},
              "assumptions":{"slot_state":"0=VACANT,1=OCCUPIED; perfect synthetic observation",
               "weekday":"Mon-Fri commute and midday peaks; Sat-Sun leisure peaks",
               "duration":"lognormal sigma=0.5; weekday morning mean=300 min, other weekday=110, weekend=100; clipped 10-720 min",
               "demand":"Poisson arrivals with Gaussian hour-of-day peaks and lognormal daily multiplier sigma=0.18",
               "capacity":"12; excess arrivals are lost, not queued; no reuse of a just-departed slot in the same minute",
               "initial_state":"all vacant at midnight; no daily state reset; boundary-censored stays are retained",
               "calendar":"fixed 2026 calendar; no holiday, weather or real-site calibration"}}
    with args.metadata.open("x",encoding="utf-8") as stream:json.dump(manifest,stream,indent=2);stream.write("\n")
    print(json.dumps({"raw_rows":len(raw),"processed_rows":len(processed),"splits":boundaries,
                      "raw_bytes":args.raw.stat().st_size,"processed_bytes":args.output.stat().st_size},indent=2))


if __name__=="__main__":main()
