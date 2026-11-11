"""Finalize an already fitted, selection-locked bundle; never fit or select anew.

Used to preserve the actual first-run artifact after exact-equality verification
rejected harmless parallel forest summation roundoff. Does not overwrite files.
"""

import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd

from ml.features import FEATURE_COLUMNS
from ml.phase4_models import MODEL_NAMES,load_predictor,metrics,predictions_agree,select_model,sha256
from ml.train_phase4 import read_partition,utc_now,verify_manifest,write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,default=Path('ml/artifacts/phase4'))
    args=parser.parse_args();folder=args.run_dir
    if (folder/'model_results.json').exists():parser.error('Results already exist; never overwrite')
    manifest=json.loads(Path('ml/data/phase3_dataset_manifest.json').read_text());verify_manifest(manifest)
    selection=json.loads((folder/'validation_selection.json').read_text());lock_hash=sha256(folder/'validation_selection.json')
    artifact=folder/'parking_models.joblib';artifact_hash=sha256(artifact)
    bundle=load_predictor(artifact,artifact_hash)
    if bundle.metadata['validation_selection_sha256']!=lock_hash or bundle.metadata['dataset_sha256']!=manifest['processed_file']['sha256']:
        raise RuntimeError('Saved bundle does not match immutable selection/dataset')
    if bundle.selected_model!=selection['selected_model'] or select_model(selection['validation_scores'])!=bundle.selected_model:
        raise RuntimeError('Selection mismatch')
    params=bundle.models['random_forest'].get_params()
    if any(params[k]!=v for k,v in selection['tuning']['chosen_forest_parameters'].items()):raise RuntimeError('Forest configuration changed')
    x,y,train_info=read_partition(manifest,'train')
    scaler=bundle.models['linear_regression'].named_steps['scale']
    if scaler.n_samples_seen_!=len(x) or not np.allclose(scaler.mean_,x.mean(axis=0),atol=1e-10):raise RuntimeError('Scaler not training-only')
    del x,y
    x_val,y_val,val_info=read_partition(manifest,'validation')
    for name in MODEL_NAMES:
        actual=metrics(y_val,bundle.models[name].predict(x_val))
        if any(abs(actual['clipped'][metric]-selection['validation_scores'][name]['clipped'][metric])>1e-10 for metric in ['mae','rmse','r2']):
            raise RuntimeError('Saved model no longer matches locked validation scores')
    del x_val,y_val
    x_test,y_test,test_info=read_partition(manifest,'test')
    scores={name:metrics(y_test,bundle.models[name].predict(x_test)) for name in MODEL_NAMES}
    reloaded=load_predictor(artifact,artifact_hash);frame=pd.DataFrame(x_test,columns=FEATURE_COLUMNS,copy=False)
    reload_checks={name:predictions_agree(bundle.predict(frame,name),reloaded.predict(frame,name)) for name in MODEL_NAMES}
    if not all(reload_checks.values()):raise RuntimeError('Trained reload exceeds numerical tolerance')
    if sha256(artifact)!=artifact_hash or sha256(folder/'validation_selection.json')!=lock_hash:raise RuntimeError('Immutable artifact changed')
    result={'source':'actual_phase4_model_execution_finalized_from_unchanged_bundle',
        'started_at_utc':selection['locked_at_utc'],'completed_at_utc':utc_now(),'data_source':'synthetic',
        'selected_model':bundle.selected_model,'validation':selection['validation_scores'],'test':scores,
        'partitions':{'train':train_info,'validation':val_info,'test':test_info},'selection_lock_sha256':lock_hash,
        'test_used_for_selection':False,'test_evaluation_stages':1,'test_metrics_computed_twice_due_to_reload_recovery':True,
        'models_refitted_on_validation':False,'retrained_during_finalization':False,
        'artifact':{'path':artifact.as_posix(),'bytes':artifact.stat().st_size,'sha256':artifact_hash},
        'reload_checks':reload_checks,'reload_absolute_tolerance':1e-12,'prediction_range':[0,12],'round_predictions':False,
        'runtime':{'platform':platform.platform(),'python':sys.version.split()[0],'executable':sys.executable,
                   'versions':{name:importlib.metadata.version(name) for name in ['scikit-learn','numpy','pandas','scipy','joblib','threadpoolctl']}},
        'limitations':'Synthetic evaluation only; no real-world accuracy claim. Original test metrics were recomputed after verification-only roundoff correction; no selection, model or hyperparameter changes.'}
    write_json(folder/'model_results.json',result)
    size=sum(p.stat().st_size for d in [Path('ml/data'),Path('ml/artifacts')] for p in d.rglob('*') if p.is_file())
    if size>=50_000_000:raise RuntimeError('Storage limit exceeded')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
