"""Verify a completed run in its permitted runtime; never trains or selects again."""

import argparse
from datetime import datetime,timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.features import FEATURE_COLUMNS
from ml.phase4_models import MODEL_NAMES,load_predictor,metrics,predictions_agree,select_model,sha256
from ml.train_phase4 import read_partition,verify_manifest,write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,default=Path('ml/artifacts/phase4'))
    parser.add_argument('--output',type=Path,default=Path('reports/evidence/phase4_model_verification.json'))
    args=parser.parse_args()
    if args.output.exists():parser.error('Choose a new verification output filename')
    manifest=json.loads(Path('ml/data/phase3_dataset_manifest.json').read_text());verify_manifest(manifest)
    results=json.loads((args.run_dir/'model_results.json').read_text())
    selection=json.loads((args.run_dir/'validation_selection.json').read_text())
    checks={}
    checks['validation_lock_hash']=sha256(args.run_dir/'validation_selection.json')==results['selection_lock_sha256']
    checks['selected_before_test']=selection['test_opened'] is False and results['test_used_for_selection'] is False
    checks['validation_only_selection']=select_model(selection['validation_scores'])==results['selected_model']==selection['selected_model']
    bundle=load_predictor(args.run_dir/'parking_models.joblib',results['artifact']['sha256'])
    checks['bundle_contract']=bundle.selected_model==results['selected_model'] and bundle.horizon_minutes==15
    x_train,y_train,train_info=read_partition(manifest,'train')
    checks['training_only_scaler']=int(bundle.models['linear_regression'].named_steps['scale'].n_samples_seen_)==len(x_train)
    checks['training_only_scaler'] &= bool(np.allclose(bundle.models['linear_regression'].named_steps['scale'].mean_,x_train.mean(axis=0),atol=1e-10))
    infos={'train':train_info}
    for partition in ['validation','test']:
        x,y,info=read_partition(manifest,partition);infos[partition]=info
        frame=pd.DataFrame(x,columns=FEATURE_COLUMNS,copy=False)
        for name in MODEL_NAMES:
            raw=bundle.models[name].predict(x)
            delivered=bundle.predict(frame,name)
            actual=metrics(y,raw)
            expected=results[partition][name]
            checks[f'{partition}_{name}_same_rows']=actual['rows']==expected['rows']==info['rows']
            checks[f'{partition}_{name}_metric_agreement']=all(
                actual['clipped'][metric] is None and expected['clipped'][metric] is None or
                actual['clipped'][metric] is not None and expected['clipped'][metric] is not None and
                abs(actual['clipped'][metric]-expected['clipped'][metric])<1e-10 for metric in ['mae','rmse','r2'])
            checks[f'{partition}_{name}_bounded_reload']=bool(np.isfinite(delivered).all() and ((delivered>=0)&(delivered<=12)).all()
                and predictions_agree(delivered,np.clip(raw,0,12)))
        checks[partition+'_row_identity']=info['origin_sha256']==results['partitions'][partition]['origin_sha256']
    checks['purged_boundary_order']=pd.Timestamp(infos['train']['last_target'])<pd.Timestamp(infos['validation']['first_origin']) and pd.Timestamp(infos['validation']['last_target'])<pd.Timestamp(infos['test']['first_origin'])
    checks['all_model_reload_checks']=all(results['reload_checks'].values())
    files={p.as_posix():p.stat().st_size for folder in [Path('ml/data'),Path('ml/artifacts')]
           for p in folder.rglob('*') if p.is_file()}
    checks['storage_below_50_MB']=sum(files.values())<50_000_000
    record={'source':'actual_phase4_saved_model_verification','recorded_at_utc':datetime.now(timezone.utc).isoformat(),
            'passed':all(checks.values()),'checks':checks,'data_model_bytes':sum(files.values()),'files':files,
            'test_metrics_recomputed_for_verification_only':True,'models_retrained_or_reselected':False}
    args.output.parent.mkdir(parents=True,exist_ok=True);write_json(args.output,record)
    print(json.dumps(record,indent=2))
    return 0 if record['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
