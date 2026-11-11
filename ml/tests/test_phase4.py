"""Contract tests run without native sklearn; NativeModelTests require it."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from ml.features import FEATURE_COLUMNS
from ml.phase4_models import MODEL_NAMES,ParkingPredictor,PersistenceRegressor,clipped_predictions,fit_candidates,load_predictor,metrics,numeric_matrix,predictions_agree,select_model,sha256
from ml.train_phase4 import read_partition,verify_manifest


def toy_features(rows=100,seed=7):
    rng=np.random.default_rng(seed)
    frame=pd.DataFrame(np.zeros((rows,len(FEATURE_COLUMNS))),columns=FEATURE_COLUMNS)
    for slot in FEATURE_COLUMNS[:12]:frame[slot]=rng.integers(0,2,size=rows)
    frame['total_occupied']=frame[list(FEATURE_COLUMNS[:12])].sum(axis=1)
    frame['hour']=12;frame['day_of_week']=1
    for name in FEATURE_COLUMNS:
        if name.startswith(('occupied_lag_','occupied_mean_')):frame[name]=frame.total_occupied
    return frame


class ConstantEstimator:
    def __init__(self,value):self.value=value
    def predict(self,x):return np.full(len(x),self.value)


class ContractTests(unittest.TestCase):
    def test_reload_agreement_allows_only_tiny_roundoff(self):
        self.assertTrue(predictions_agree([1.0],[1.0+1e-15]))
        self.assertFalse(predictions_agree([1.0],[1.0+1e-9]))
        self.assertFalse(predictions_agree([np.nan],[np.nan]))

    def test_named_input_reorders_safely(self):
        f=toy_features(2)
        np.testing.assert_array_equal(numeric_matrix(f),numeric_matrix(f[list(reversed(FEATURE_COLUMNS))]))

    def test_dict_and_frame_interfaces_agree(self):
        f=toy_features(2)
        np.testing.assert_array_equal(numeric_matrix(f),numeric_matrix(f.to_dict('records')))
        self.assertEqual(numeric_matrix(f.iloc[0].to_dict()).shape,(1,37))

    def test_reject_missing_extra_duplicate_and_target_columns(self):
        frame=toy_features(2)
        for f in [frame.drop(columns='P1'),frame.assign(occupied_15min_ahead=1),frame.assign(target_timestamp=1)]:
            with self.assertRaises(ValueError):numeric_matrix(f)

    def test_reject_nonfinite_strings_booleans_and_wrong_totals(self):
        for kind in ['nan','string','bool','sum','state','lag']:
            f=toy_features(2)
            if kind=='nan':f.loc[0,'time_sin']=np.nan
            elif kind=='string':f['hour']='12'
            elif kind=='bool':f['is_weekend']=False
            elif kind=='sum':f.loc[0,'total_occupied']=99
            elif kind=='state':f.loc[0,'P1']=2
            else:f.loc[0,'occupied_lag_1']=13
            with self.subTest(kind=kind),self.assertRaises(ValueError):numeric_matrix(f)

    def test_clipping_preserves_fractional_counts(self):
        np.testing.assert_array_equal(clipped_predictions([-1,0,1.5,12,15]),[0,0,1.5,12,12])
        with self.assertRaises(ValueError):clipped_predictions([np.inf])

    def test_metric_mathematics_and_clipping_frequency(self):
        measured=metrics([0,2,4],[-1,2,7])
        self.assertAlmostEqual(measured['raw']['mae'],4/3)
        self.assertAlmostEqual(measured['clipped']['rmse'],np.sqrt(9/3))
        self.assertAlmostEqual(measured['clipped']['r2'],1-9/8)
        self.assertEqual(measured['clipped_count'],1)

    def test_constant_r2_is_explicitly_undefined(self):
        self.assertIsNone(metrics([1,1],[1,2])['clipped']['r2'])

    def test_metric_alignment_and_target_range(self):
        for y,p in [([1],[1,2]),([],[]),([13],[2])]:
            with self.assertRaises(ValueError):metrics(y,p)

    def test_persistence_uses_current_total(self):
        f=toy_features(4);p=PersistenceRegressor().predict(numeric_matrix(f))
        np.testing.assert_array_equal(p,f.total_occupied)

    def test_selection_is_validation_only_and_tie_prefers_simple(self):
        scores={name:metrics([0,2],[0,2]) for name in MODEL_NAMES}
        self.assertEqual(select_model(scores),'persistence')
        scores['persistence']=metrics([0,2],[1,1])
        self.assertEqual(select_model(scores),'linear_regression')
        with self.assertRaises(ValueError):select_model({})

    def test_bundle_selects_model_and_clips(self):
        bundle=ParkingPredictor({name:ConstantEstimator(13.5) for name in MODEL_NAMES},'random_forest')
        np.testing.assert_array_equal(bundle.predict(toy_features(3)),[12,12,12])
        self.assertEqual(bundle.horizon_minutes,15)
        with self.assertRaises(ValueError):bundle.predict(toy_features(2),'bad')

    def test_checksum_rejected_before_unpickling(self):
        with self.assertRaises(ValueError):load_predictor('ml/data/phase3_dataset_manifest.json','0'*64)

    def test_fake_bundle_roundtrip_is_contract_only(self):
        import joblib
        Path('tmp/phase4-tests').mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir='tmp/phase4-tests') as temp:
            path=Path(temp)/'fake.joblib'
            bundle=ParkingPredictor({name:ConstantEstimator(3) for name in MODEL_NAMES},'persistence')
            joblib.dump(bundle,path,compress=3)
            reloaded=load_predictor(path,sha256(path))
            np.testing.assert_array_equal(bundle.predict(toy_features(2)),reloaded.predict(toy_features(2)))

    def test_partition_reader_does_not_read_test_during_validation(self):
        import json
        m=json.loads(Path('ml/data/phase3_dataset_manifest.json').read_text())
        with patch('ml.train_phase4.pd.read_csv',wraps=pd.read_csv) as reader:
            _x,_y,info=read_partition(m,'validation')
        self.assertEqual(info['rows'],10577)
        self.assertEqual(reader.call_args.kwargs['nrows'],10577)
        self.assertEqual(reader.call_args.kwargs['skiprows'],range(1,49361))

    def test_manifest_verifies_frozen_checksums(self):
        import json
        m=json.loads(Path('ml/data/phase3_dataset_manifest.json').read_text());verify_manifest(m)
        m['features']=[]
        with self.assertRaises(ValueError):verify_manifest(m)


class NativeModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # A blocked import is an ERROR, never an automatic native-test pass/skip.
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.linear_model import LinearRegression
        cls.x=numeric_matrix(toy_features(100))
        cls.y=np.clip(cls.x[:,12]+np.random.default_rng(5).normal(0,0.2,100),0,12)
        cls.grid=({'n_estimators':6,'max_depth':3,'min_samples_leaf':2,'random_state':42,'n_jobs':1},)
        cls.models,cls.scores,cls.tuning=fit_candidates(cls.x[:70],cls.y[:70],cls.x[70:],cls.y[70:],grid=cls.grid)

    def test_preprocessing_fitted_on_train_only(self):
        scaler=self.models['linear_regression'].named_steps['scale']
        self.assertEqual(scaler.n_samples_seen_,70)
        np.testing.assert_allclose(scaler.mean_,self.x[:70].mean(axis=0))

    def test_identical_validation_row_counts(self):
        self.assertEqual({x['rows'] for x in self.scores.values()},{30})

    def test_seeded_forest_training_repeats(self):
        models,_,_=fit_candidates(self.x[:70],self.y[:70],self.x[70:],self.y[70:],grid=self.grid)
        np.testing.assert_array_equal(models['random_forest'].predict(self.x[70:]),self.models['random_forest'].predict(self.x[70:]))

    def test_native_metric_agreement(self):
        from sklearn.metrics import mean_absolute_error,root_mean_squared_error,r2_score
        predictions=np.clip(self.models['linear_regression'].predict(self.x[70:]),0,12)
        ours=metrics(self.y[70:],predictions)['clipped']
        self.assertAlmostEqual(ours['mae'],mean_absolute_error(self.y[70:],predictions))
        self.assertAlmostEqual(ours['rmse'],root_mean_squared_error(self.y[70:],predictions))
        self.assertAlmostEqual(ours['r2'],r2_score(self.y[70:],predictions))

    def test_trained_bundle_reload_predictions(self):
        import joblib
        Path('tmp/phase4-tests').mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir='tmp/phase4-tests') as temp:
            path=Path(temp)/'trained.joblib'
            bundle=ParkingPredictor(self.models,select_model(self.scores));joblib.dump(bundle,path,compress=3)
            reloaded=load_predictor(path,sha256(path))
            for name in MODEL_NAMES:
                np.testing.assert_array_equal(bundle.predict(toy_features(10),name),reloaded.predict(toy_features(10),name))
