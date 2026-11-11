"""Synthetic pipeline tests; no production MQTT, database or notebook access."""

import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

from ml.features import FEATURE_COLUMNS,HORIZON,LAGS,MEAN_WINDOWS,STD_WINDOWS,WARMUP,engineer_features,prepare,split_counts
from ml.generate_data import SLOTS,content_digest,generate,read_raw
from ml.prepare_data import file_hash,read_processed,write_processed


class GenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.raw=generate(days=14)

    def test_exact_timeline_and_timezone(self):
        self.assertEqual(len(self.raw),20160)
        self.assertEqual(str(self.raw.timestamp.dt.tz),"Asia/Kolkata")
        self.assertTrue(self.raw.timestamp.diff().iloc[1:].eq(pd.Timedelta(minutes=1)).all())
        self.assertTrue(self.raw.timestamp.is_unique)

    def test_all_slots_binary_and_total(self):
        self.assertTrue(all(self.raw[s].isin([0,1]).all() for s in SLOTS))
        np.testing.assert_array_equal(self.raw[list(SLOTS)].sum(axis=1),self.raw.total_occupied)
        self.assertTrue(self.raw.total_occupied.between(0,12).all())

    def test_each_slot_arrives_and_departs(self):
        diff=self.raw[list(SLOTS)].astype(int).diff().fillna(0)
        self.assertTrue((diff==1).any().all());self.assertTrue((diff==-1).any().all())
        np.testing.assert_array_equal((diff==1).sum(axis=1),self.raw.arrivals)
        np.testing.assert_array_equal((diff==-1).sum(axis=1),self.raw.departures)

    def test_complete_dwell_times_and_persistence(self):
        for slot in SLOTS:
            edge=np.diff(np.r_[0,self.raw[slot].to_numpy(),0])
            starts,ends=np.flatnonzero(edge==1),np.flatnonzero(edge==-1)
            dwell=[b-a for a,b in zip(starts,ends) if b<len(self.raw)]
            self.assertTrue(all(10<=n<=720 for n in dwell))
        self.assertGreater(self.raw.total_occupied.autocorr(1),0.9)

    def test_fixed_seed_and_changed_seed(self):
        a=generate(days=2,seed=42);b=generate(days=2,seed=42)
        self.assertEqual(content_digest(a),content_digest(b))
        self.assertNotEqual(content_digest(a),content_digest(generate(days=2,seed=43)))

    def test_source_and_missing_values(self):
        self.assertEqual(set(self.raw.data_source.astype(str)),{"synthetic"})
        self.assertFalse(self.raw.isna().any().any())

    def test_invalid_days(self):
        for days in [0,-1,True,1.5]:
            with self.assertRaises(ValueError):generate(days=days)


class FeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=generate(days=9)
        cls.features=engineer_features(cls.raw)
        cls.processed,cls.boundaries=prepare(cls.raw)

    def test_each_lag_uses_exact_past_minute(self):
        row=WARMUP+50
        for lag in LAGS:self.assertEqual(self.features.loc[row,f"occupied_lag_{lag}"],self.raw.loc[row-lag,"total_occupied"])

    def test_rolling_features_use_only_past(self):
        row=WARMUP+50
        for window in MEAN_WINDOWS:
            expected=self.raw.total_occupied.iloc[row-window:row].mean()
            self.assertAlmostEqual(self.features.loc[row,f"occupied_mean_{window}"],expected,places=5)
        for window in STD_WINDOWS:
            expected=self.raw.total_occupied.iloc[row-window:row].std(ddof=0)
            self.assertAlmostEqual(self.features.loc[row,f"occupied_std_{window}"],expected,places=5)

    def test_calendar_is_local_and_cyclic(self):
        row=WARMUP+85;t=self.raw.timestamp.iloc[row]
        self.assertEqual(self.features.hour.iloc[row],t.hour)
        self.assertEqual(self.features.day_of_week.iloc[row],t.day_of_week)
        self.assertAlmostEqual(self.features.time_sin.iloc[row]**2+self.features.time_cos.iloc[row]**2,1,places=6)

    def test_future_intervention_cannot_change_any_past_feature(self):
        cutoff=WARMUP+30;altered=self.raw.copy()
        for slot in SLOTS:altered.loc[cutoff+1:,slot]=1-altered.loc[cutoff+1:,slot]
        altered.loc[cutoff+1:,"total_occupied"]=altered.loc[cutoff+1:,list(SLOTS)].sum(axis=1).astype("uint8")
        altered.loc[cutoff+1:,["arrivals","departures"]]=0
        candidate=engineer_features(altered)
        np.testing.assert_allclose(self.features.loc[:cutoff,list(FEATURE_COLUMNS)],candidate.loc[:cutoff,list(FEATURE_COLUMNS)],equal_nan=True,rtol=0,atol=0)

    def test_prefix_computation_equals_full_past(self):
        end=WARMUP+20
        prefix=engineer_features(self.raw.iloc[:end+1])
        np.testing.assert_allclose(prefix[list(FEATURE_COLUMNS)],self.features.loc[:end,list(FEATURE_COLUMNS)],equal_nan=True,rtol=0,atol=0)

    def test_target_exact_future_timestamp_and_value(self):
        index=pd.Index(self.raw.timestamp).get_indexer(self.processed.timestamp)
        np.testing.assert_array_equal(self.processed.occupied_15min_ahead,self.raw.total_occupied.iloc[index+15])
        self.assertTrue((self.processed.target_timestamp-self.processed.timestamp).eq(pd.Timedelta(minutes=15)).all())
        self.assertTrue(self.processed.target_timestamp.reset_index(drop=True).equals(self.raw.timestamp.iloc[index+15].reset_index(drop=True)))

    def test_split_ratios_rounding_and_purged_label_boundaries(self):
        counts=split_counts(len(self.raw)-WARMUP-HORIZON)
        for name,count in zip(["train","validation","test"],counts):
            self.assertEqual((self.processed.split==name).sum(),count)
        for left,right in [("train","validation"),("validation","test")]:
            a=self.processed.loc[self.processed.split==left]
            b=self.processed.loc[self.processed.split==right]
            self.assertLess(a.target_timestamp.max(),b.timestamp.min())
            self.assertEqual(b.timestamp.min()-a.timestamp.max(),pd.Timedelta(minutes=16))

    def test_no_missing_features_after_filtering(self):
        self.assertFalse(self.processed.isna().any().any())
        self.assertEqual(len(self.processed),len(self.raw)-WARMUP-HORIZON-2*HORIZON)
        self.assertFalse({"target_timestamp","occupied_15min_ahead","split","data_source","timestamp"}.intersection(FEATURE_COLUMNS))

    def test_invalid_timestamp_or_source_fails_instead_of_imputation(self):
        for kind in ["duplicate","gap","real"]:
            raw=self.raw.copy()
            if kind=="duplicate":raw.loc[10,"timestamp"]=raw.loc[9,"timestamp"]
            elif kind=="gap":raw.loc[10,"timestamp"]+=pd.Timedelta(seconds=10)
            else:raw["data_source"]="wokwi"
            with self.assertRaises(ValueError):prepare(raw)


class SerializationTests(unittest.TestCase):
    def setUp(self):
        Path('tmp/phase3-tests').mkdir(parents=True,exist_ok=True)
        self.directory=tempfile.TemporaryDirectory(dir='tmp/phase3-tests')
        self.folder=Path(self.directory.name)

    def tearDown(self):self.directory.cleanup()

    def test_raw_csv_roundtrip(self):
        raw=generate(days=1);path=self.folder/'raw.csv'
        raw.to_csv(path,index=False,date_format='%Y-%m-%dT%H:%M:%S%z')
        self.assertEqual(content_digest(raw),content_digest(read_raw(path)))

    def test_invalid_raw_count_does_not_overflow_into_valid_value(self):
        raw=generate(days=1);raw["total_occupied"]=raw.total_occupied.astype('int64');raw.loc[0,"total_occupied"]=256
        path=self.folder/'bad.csv';raw.to_csv(path,index=False)
        with self.assertRaises(ValueError):read_raw(path)

    def test_existing_raw_output_is_never_overwritten(self):
        path=self.folder/'existing.csv';path.write_text('preserve')
        result=subprocess.run([sys.executable,'-B','-m','ml.generate_data','--output',str(path)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertEqual(path.read_text(),'preserve')

    def test_committed_artifact_roundtrip_and_fingerprints(self):
        manifest=json.loads(Path('ml/data/phase3_dataset_manifest.json').read_text())
        frame=read_processed(manifest['processed_file']['path'],manifest['schema'])
        self.assertEqual(len(frame),70515)
        for entry in [manifest['raw_file'],manifest['processed_file']]:
            self.assertEqual(file_hash(entry['path']),entry['sha256'])
        self.assertFalse(frame.isna().any().any())

    def test_processed_bytes_are_reproducible_without_duplicate_file(self):
        manifest=json.loads(Path('ml/data/phase3_dataset_manifest.json').read_text())
        raw=read_raw(manifest['raw_file']['path']);frame,_=prepare(raw)
        class HashSink:
            def __init__(self):self.digest=hashlib.sha256();self.count=0
            def write(self,data):self.digest.update(data);self.count+=len(data);return len(data)
            def tell(self):return self.count
            def flush(self):pass
        sink=HashSink();write_processed(frame,sink)
        self.assertEqual(sink.digest.hexdigest(),manifest['processed_file']['sha256'])
        self.assertEqual(sink.count,manifest['processed_file']['bytes'])
