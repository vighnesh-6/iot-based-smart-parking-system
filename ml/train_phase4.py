"""Validation-selected Phase 4 training; test is opened only after selection lock.

Run in a permitted scikit-learn runtime: python -m ml.train_phase4 --output-dir ml/artifacts/phase4
Existing output directories are refused. No Phase 3 artifact is rewritten.
"""

import argparse
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd

from ml.features import FEATURE_COLUMNS,HORIZON
from ml.phase4_models import MODEL_NAMES,ParkingPredictor,fit_candidates,load_predictor,metrics,numeric_matrix,predictions_agree,select_model,sha256

MANIFEST=Path('ml/data/phase3_dataset_manifest.json')


def write_json(path,data):
    with Path(path).open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(data,stream,indent=2,allow_nan=False);stream.write('\n')


def utc_now():return datetime.now(timezone.utc).isoformat()


def read_partition(manifest,name):
    """Read only the requested partition; no test-label parsing during tuning."""
    counts={k:v['rows'] for k,v in manifest['split_boundaries'].items()}
    before=sum(counts[k] for k in ['train','validation','test'][:['train','validation','test'].index(name)])
    dtype={k:v for k,v in manifest['schema'].items() if k not in ['timestamp','target_timestamp']}
    frame=pd.read_csv(manifest['processed_file']['path'],dtype=dtype,nrows=counts[name],skiprows=range(1,before+1))
    if len(frame)!=counts[name] or not frame['split'].eq(name).all():raise ValueError('Unexpected partition rows')
    if not frame['data_source'].eq('synthetic').all() or frame.isna().any().any():raise ValueError('Invalid provenance/missing data')
    for column in ['timestamp','target_timestamp']:frame[column]=pd.to_datetime(frame[column],utc=True)
    if not (frame.target_timestamp-frame.timestamp).eq(pd.Timedelta(minutes=HORIZON)).all():raise ValueError('Incorrect target horizon')
    if not frame.timestamp.is_unique or not frame.timestamp.is_monotonic_increasing:raise ValueError('Unordered partition')
    x=numeric_matrix(frame[list(FEATURE_COLUMNS)])
    y=frame.occupied_15min_ahead.to_numpy(dtype='float64')
    if not ((y>=0)&(y<=12)).all():raise ValueError('Target range violation')
    identity=hashlib.sha256('\n'.join(frame.timestamp.astype(str)).encode()).hexdigest()
    info={'rows':len(frame),'first_origin':str(frame.timestamp.iloc[0]),'last_origin':str(frame.timestamp.iloc[-1]),
          'last_target':str(frame.target_timestamp.iloc[-1]),'origin_sha256':identity}
    x.flags.writeable=False;y.flags.writeable=False
    return x,y,info


def verify_manifest(manifest):
    if manifest['features']!=list(FEATURE_COLUMNS) or manifest['horizon_minutes']!=15:raise ValueError('Frozen schema mismatch')
    for record in [manifest['raw_file'],manifest['processed_file']]:
        if sha256(record['path'])!=record['sha256']:raise ValueError('Frozen dataset checksum mismatch')


def run(output_dir):
    # Dependency preflight before creating output: failures cannot leave fake model evidence.
    import joblib
    import sklearn
    from sklearn.linear_model import LinearRegression
    from sklearn.ensemble import RandomForestRegressor
    manifest=json.loads(MANIFEST.read_text())
    verify_manifest(manifest)
    output_dir=Path(output_dir)
    output_dir.mkdir(parents=True,exist_ok=False)
    # Preserve lock/results bytes for the recorded hashes on every Git checkout.
    with (output_dir/'.gitattributes').open('x',encoding='utf-8',newline='\n') as stream:
        stream.write('* -text\n')
    started=utc_now()
    x_train,y_train,train_info=read_partition(manifest,'train')
    x_val,y_val,val_info=read_partition(manifest,'validation')
    if pd.Timestamp(train_info['last_target'])>=pd.Timestamp(val_info['first_origin']):raise ValueError('Leaking train/validation boundary')
    models,val_scores,tuning=fit_candidates(x_train,y_train,x_val,y_val)
    selected=select_model(val_scores)
    selection={'selected_model':selected,'selection_rule':'clipped MAE, then clipped RMSE, then persistence/linear/forest simplicity',
               'validation_scores':val_scores,'tuning':tuning,'training_partition':train_info,'validation_partition':val_info,
               'test_opened':False,'locked_at_utc':utc_now(),'dataset_sha256':manifest['processed_file']['sha256']}
    lock_path=output_dir/'validation_selection.json';write_json(lock_path,selection)
    lock_hash=sha256(lock_path)
    print('Validation selection locked:',selected,flush=True)
    # This is the first test read. No training/tuning is called after this point.
    x_test,y_test,test_info=read_partition(manifest,'test')
    if pd.Timestamp(val_info['last_target'])>=pd.Timestamp(test_info['first_origin']):raise ValueError('Leaking validation/test boundary')
    test_scores={name:metrics(y_test,models[name].predict(x_test)) for name in MODEL_NAMES}
    if sha256(lock_path)!=lock_hash:raise RuntimeError('Selection changed after test access')
    bundle=ParkingPredictor(models,selected,metadata={'dataset_sha256':manifest['processed_file']['sha256'],
                'validation_selection_sha256':lock_hash,'trained_on':'train_only','seed':42,'clipping':[0,12]})
    artifact=output_dir/'parking_models.joblib'
    with artifact.open('xb') as stream:joblib.dump(bundle,stream,compress=3)
    digest=sha256(artifact)
    reloaded=load_predictor(artifact,digest)
    # Build named input frames only for verification; all models use identical held-out rows.
    test_frame=pd.DataFrame(x_test,columns=FEATURE_COLUMNS,copy=False)
    reload_checks={name:predictions_agree(reloaded.predict(test_frame,name),np.clip(models[name].predict(x_test),0,12)) for name in MODEL_NAMES}
    if not all(reload_checks.values()):raise RuntimeError('Saved/reloaded prediction mismatch')
    result={'source':'actual_phase4_model_execution','started_at_utc':started,'completed_at_utc':utc_now(),
        'data_source':'synthetic','selected_model':selected,'validation':val_scores,'test':test_scores,
        'partitions':{'train':train_info,'validation':val_info,'test':test_info},'selection_lock_sha256':lock_hash,
        'test_used_for_selection':False,'test_evaluation_stages':1,'models_refitted_on_validation':False,
        'artifact':{'path':artifact.as_posix(),'bytes':artifact.stat().st_size,'sha256':digest},
        'reload_checks':reload_checks,'reload_absolute_tolerance':1e-12,'prediction_range':[0,12],'round_predictions':False,
        'runtime':{'platform':platform.platform(),'python':sys.version.split()[0],
                   'versions':{name:importlib.metadata.version(name) for name in ['scikit-learn','numpy','pandas','scipy','joblib','threadpoolctl']}},
        'limitations':'Synthetic evaluation only; no real-world accuracy or live integration claim.'}
    # Count all existing data/model files, including this bundle and lock.
    storage=sum(p.stat().st_size for folder in [Path('ml/data'),Path('ml/artifacts')] for p in folder.rglob('*') if p.is_file())
    if storage>=50_000_000:raise RuntimeError('Data/model storage budget exceeded')
    result['data_model_bytes_before_results_json']=storage
    write_json(output_dir/'model_results.json',result)
    if sum(p.stat().st_size for folder in [Path('ml/data'),Path('ml/artifacts')]
           for p in folder.rglob('*') if p.is_file())>=50_000_000:
        raise RuntimeError('Final data/model storage exceeds 50 MB')
    print(json.dumps(result,indent=2))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=Path('ml/artifacts/phase4'))
    args=parser.parse_args()
    if args.output_dir.exists():parser.error('Choose a new output directory; results/models are never overwritten')
    run(args.output_dir)


if __name__=='__main__':main()
