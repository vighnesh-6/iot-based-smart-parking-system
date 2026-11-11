"""Shared prediction contract with in-process and configured subprocess adapters.

No model logic is implemented here. Both paths call the frozen Phase 4 interface.
"""
from functools import lru_cache
import json
import os
from pathlib import Path
import subprocess
import sys

from dashboard.config import ROOT, Settings


class PredictionError(RuntimeError):
    pass


def read_results(settings):
    result = json.loads(settings.results_path.read_text(encoding='utf-8'))
    if result['selected_model'] != 'persistence' or result['data_source'] != 'synthetic':
        raise ValueError('Unexpected Phase 4 model selection or provenance')
    return result


@lru_cache(maxsize=2)
def _load(path, expected_hash):
    from ml.phase4_models import load_predictor
    return load_predictor(path, expected_hash)


def _in_process(features, settings):
    from ml.phase4_models import sha256
    result = read_results(settings)
    expected = result['artifact']['sha256']
    if sha256(settings.model_path) != expected:
        raise ValueError('Model checksum mismatch')
    predictor = _load(str(settings.model_path), expected)
    values = predictor.predict(features)
    return {'predictions': values.tolist(), 'selected_model': predictor.selected_model,
            'horizon_minutes': predictor.horizon_minutes, 'training_data_source': predictor.data_source}


def predict(features, settings):
    try:
        if settings.prediction_adapter == 'in_process':
            response = _in_process(features, settings)
        else:
            if not settings.ml_python or not Path(settings.ml_python).is_file():
                raise ValueError('Set ML_PYTHON to an approved Python interpreter')
            environment = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
                'MODEL_RESULTS_PATH': str(settings.results_path), 'MODEL_BUNDLE_PATH': str(settings.model_path)}
            process = subprocess.run([settings.ml_python, '-B', '-m', 'dashboard.prediction', '--worker'],
                input=json.dumps(features, allow_nan=False), text=True, encoding='utf-8',
                capture_output=True, timeout=30, cwd=ROOT, env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                shell=False)
            if process.returncode:
                raise PredictionError('Approved prediction worker failed; inspect its runtime and trusted artifact configuration')
            response = json.loads(process.stdout)
        values = response['predictions']
        expected_rows = 1 if isinstance(features, dict) else len(features)
        if response['selected_model'] != 'persistence' or response['horizon_minutes'] != 15 or not isinstance(values, list) or len(values) != expected_rows or not values:
            raise ValueError('Invalid prediction response contract')
        if any(type(v) not in (int, float) or not 0 <= v <= 12 for v in values):
            raise ValueError('Predictions must be finite and within 0-12')
        return response
    except PredictionError:
        raise
    except Exception as error:
        # Do not expose local paths, credentials or native-loader diagnostics to UI users.
        raise PredictionError('Prediction unavailable: invalid inputs, artifact or runtime configuration') from error


def synthetic_example(settings):
    """Read an existing validation row, without generation or artifact writes."""
    from ml.features import FEATURE_COLUMNS
    from ml.train_phase4 import read_partition, verify_manifest
    manifest = json.loads(settings.manifest_path.read_text(encoding='utf-8'))
    # Dataset paths in released metadata are repository-relative.
    for key in ('raw_file', 'processed_file'):
        manifest[key]['path'] = str(ROOT / manifest[key]['path'])
    verify_manifest(manifest)
    x, y, info = read_partition(manifest, 'validation')
    features = {name: float(x[0, index]) for index, name in enumerate(FEATURE_COLUMNS)}
    result = predict(features, settings)
    return {**result, 'origin': info['first_origin'], 'actual_future_occupied': float(y[0]),
            'observation_source': 'synthetic', 'partition': 'validation'}


if __name__ == '__main__':
    if sys.argv[1:] != ['--worker']:
        raise SystemExit('Use --worker for configured local prediction execution')
    try:
        request = json.loads(sys.stdin.read(1_000_001))
        response = _in_process(request, Settings.from_env())
        print(json.dumps(response, allow_nan=False))
    except Exception as error:
        print(f'{type(error).__name__}: {error}', file=sys.stderr)
        raise SystemExit(1)
