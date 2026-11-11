"""Phase 4 model contracts, metrics and a strict clipped prediction interface.

Native scikit-learn imports are lazy: blocked runtimes can inspect/test contracts
without pretending to train or loading an alternative copy of a blocked DLL.
"""

from dataclasses import dataclass, field
import hashlib
from pathlib import Path

import numpy as np

from ml.features import FEATURE_COLUMNS,HORIZON

MODEL_NAMES = ("persistence","linear_regression","random_forest")
SEED = 42
FOREST_GRID = tuple({"n_estimators":100,"max_depth":depth,"min_samples_leaf":leaf,
                     "max_features":0.8,"max_samples":0.8,"bootstrap":True,
                     "random_state":SEED,"n_jobs":2}
                    for depth in (8,12) for leaf in (10,30))


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(65536),b""):digest.update(chunk)
    return digest.hexdigest()


def numeric_matrix(features):
    if isinstance(features,dict):features=[features]
    if isinstance(features,list):
        if not features or any(not isinstance(row,dict) or set(row)!=set(FEATURE_COLUMNS) for row in features):
            raise ValueError("Provide one or more records with exactly FEATURE_COLUMNS")
        for row in features:
            if any(type(value) not in (int,float) for value in row.values()):
                raise ValueError("Features must be real numeric values, not strings or booleans")
        matrix=np.array([[row[name] for name in FEATURE_COLUMNS] for row in features],dtype="float64")
    elif hasattr(features,"columns") and hasattr(features,"to_numpy"):
        if len(features.columns)!=len(FEATURE_COLUMNS) or set(features.columns)!=set(FEATURE_COLUMNS):
            raise ValueError("Feature frame must have exactly the frozen predictor columns")
        if any(dtype.kind not in "iuf" for dtype in features.dtypes):
            raise ValueError("Feature frame columns must be numeric and non-boolean")
        matrix=features.loc[:,list(FEATURE_COLUMNS)].to_numpy(dtype="float64")
    else:
        raise TypeError("Pass a predictor DataFrame, one feature dict, or a list of feature dicts")
    if matrix.ndim!=2 or not len(matrix) or not np.isfinite(matrix).all():
        raise ValueError("Features must be nonempty, finite and two-dimensional")
    states=matrix[:,:12]
    total=matrix[:,FEATURE_COLUMNS.index("total_occupied")]
    if not np.isin(states,[0,1]).all() or not np.array_equal(total,states.sum(axis=1)):
        raise ValueError("Current twelve binary states must sum to total_occupied")
    for name in FEATURE_COLUMNS:
        column=matrix[:,FEATURE_COLUMNS.index(name)]
        if name.startswith(("occupied_lag_","occupied_mean_")) and not ((column>=0)&(column<=12)).all():
            raise ValueError("Occupancy lags/means must be in 0-12")
        if name.startswith("occupied_std_") and not ((column>=0)&(column<=6.00001)).all():
            raise ValueError("Population standard deviations must be in 0-6")
    return matrix


def clipped_predictions(predictions):
    values=np.asarray(predictions,dtype="float64")
    if values.ndim!=1 or not np.isfinite(values).all():raise ValueError("Predictions must be finite one-dimensional values")
    return np.clip(values,0.0,12.0)


def predictions_agree(left,right):
    """Allow only floating summation roundoff (parallel forest prediction)."""
    a,b=np.asarray(left,dtype='float64'),np.asarray(right,dtype='float64')
    return bool(a.shape==b.shape and a.ndim==1 and np.isfinite(a).all() and np.isfinite(b).all()
                and np.allclose(a,b,rtol=0,atol=1e-12))


def metrics(y,predictions):
    y=np.asarray(y,dtype="float64");predictions=np.asarray(predictions,dtype="float64")
    if y.ndim!=1 or y.shape!=predictions.shape or not len(y) or not np.isfinite(y).all():
        raise ValueError("Metric inputs must be aligned, finite nonempty vectors")
    if not ((y>=0)&(y<=12)).all():raise ValueError("Target outside occupancy range")
    bounded=clipped_predictions(predictions)
    def score(p):
        squared=float(np.sum((y-p)**2));variance=float(np.sum((y-y.mean())**2))
        return {"mae":float(np.mean(np.abs(y-p))),"rmse":float(np.sqrt(squared/len(y))),
                "r2":1-squared/variance if variance else None}
    return {"rows":len(y),"clipped":score(bounded),"raw":score(predictions),
            "clipped_count":int(np.count_nonzero(predictions!=bounded)),
            "clipped_fraction":float(np.mean(predictions!=bounded)),
            "r2_note":"Undefined for constant targets" if not np.var(y) else None}


def select_model(validation_scores):
    if set(validation_scores)!=set(MODEL_NAMES):raise ValueError("All three models must be compared")
    if any(not np.isfinite(score['clipped'][key]) or score['clipped'][key]<0
           for score in validation_scores.values() for key in ['mae','rmse']):
        raise ValueError('Invalid validation score')
    return min(MODEL_NAMES,key=lambda name:(validation_scores[name]["clipped"]["mae"],
               validation_scores[name]["clipped"]["rmse"],MODEL_NAMES.index(name)))


class PersistenceRegressor:
    def predict(self,x):return np.asarray(x)[:,FEATURE_COLUMNS.index("total_occupied")].astype("float64")


def fit_candidates(x_train,y_train,x_validation,y_validation,grid=FOREST_GRID):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import LinearRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from threadpoolctl import threadpool_limits

    models={"persistence":PersistenceRegressor()}
    scores={"persistence":metrics(y_validation,models["persistence"].predict(x_validation))}
    candidates=[]
    with threadpool_limits(limits=1):
        linear=Pipeline([("scale",StandardScaler()),("regressor",LinearRegression())])
        linear.fit(x_train,y_train)
        # Detect any accidental preprocessing fit using validation rows.
        scaler=linear.named_steps["scale"]
        if scaler.n_samples_seen_!=len(x_train) or not np.allclose(scaler.mean_,x_train.mean(axis=0),atol=1e-10):
            raise RuntimeError("Training-only scaler invariant failed")
        models["linear_regression"]=linear
        scores["linear_regression"]=metrics(y_validation,linear.predict(x_validation))
        best_key=None;best_config=None
        for index,config in enumerate(grid):
            forest=RandomForestRegressor(**config)
            forest.fit(x_train,y_train)
            measured=metrics(y_validation,forest.predict(x_validation))
            candidates.append({"candidate":index,"parameters":dict(config),"validation":measured})
            key=(measured["clipped"]["mae"],measured["clipped"]["rmse"],index)
            if best_key is None or key<best_key:
                models["random_forest"],scores["random_forest"]=forest,measured
                best_key,best_config=key,dict(config)
    return models,scores,{"forest_candidates":candidates,"chosen_forest_parameters":best_config,
                         "linear_rank":int(linear.named_steps['regressor'].rank_),
                         "scaler_training_rows":int(scaler.n_samples_seen_),"refit_on_validation":False}


@dataclass
class ParkingPredictor:
    models: dict
    selected_model: str
    metadata: dict = field(default_factory=dict)
    feature_names: tuple = FEATURE_COLUMNS
    horizon_minutes: int = HORIZON
    data_source: str = "synthetic"

    def predict(self,features,model_name=None):
        name=model_name or self.selected_model
        if name not in self.models:raise ValueError("Unknown model")
        return clipped_predictions(self.models[name].predict(numeric_matrix(features)))


def load_predictor(path,expected_sha256):
    """Load only your trusted joblib artifact; checksums are not an authenticity proof."""
    if sha256(path)!=expected_sha256:raise ValueError("Model checksum mismatch")
    import joblib
    bundle=joblib.load(path)
    if not isinstance(bundle,ParkingPredictor) or bundle.feature_names!=FEATURE_COLUMNS or bundle.horizon_minutes!=15:
        raise ValueError("Unexpected model bundle contract")
    if set(bundle.models)!=set(MODEL_NAMES) or bundle.selected_model not in MODEL_NAMES:
        raise ValueError("Incomplete model bundle")
    return bundle
