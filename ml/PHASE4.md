# Phase 4: local Windows machine learning

Phase 4 fitting, validation comparison, final evaluation and trained-model reload
verification succeeded in the user-approved isolated Windows environment:
`%LOCALAPPDATA%\SmartParking\ml-runtime` (Python 3.12.10 x64).
The existing project `.venv`, frozen requirements and every Phase 1/2/3 artifact
were preserved. No security policy, trust exception or DLL relocation was used.

## Actual results and selected model

All models use the same frozen 37 predictors, 49,360 training rows, 10,577
validation rows and 10,578 test rows. Targets are exactly 15 minutes ahead.

| Model | Validation MAE | Validation RMSE | Validation R2 | Test MAE | Test RMSE | Test R2 |
| --- | --- | --- | --- | --- | --- | --- |
| Persistence | 0.339983 | 0.684103 | 0.950447 | 0.307714 | 0.648092 | 0.945254 |
| Linear Regression | 0.414362 | 0.656363 | 0.954385 | 0.373729 | 0.613500 | 0.950942 |
| Random Forest | 0.436999 | 0.680876 | 0.950914 | 0.394675 | 0.641002 | 0.946445 |

**Persistence is selected by validation MAE.** The tie-breaks were validation
RMSE, then simplicity (persistence, linear, forest). Linear Regression has lower
RMSE, but the predeclared MAE criterion was not changed after seeing the test
results. Learned models are retained for comparison; no improvement over the
baseline in MAE is claimed. These are synthetic holdout results, not real-world
accuracy, live sensor validation or a claim that the best model generalizes.

## Methodology and leakage protection

Persistence predicts current `total_occupied`. Linear Regression uses a
training-fitted StandardScaler followed by ordinary least squares on float64
predictors. Frozen features include exact dependencies (slot sum, change/lag
identities); observed linear rank is 34 of 37 columns. Coefficients are not
interpreted causally and no frozen feature was removed based on held-out scores.

Random Forest uses 100 trees, seed 42, bootstrap, max_samples=0.8,
max_features=0.8 and n_jobs=2. Four predeclared validation candidates combine
depths 8/12 and minimum leaf sizes 10/30. The chosen forest is depth 8, minimum
leaf size 30. Only that forest is saved. Rejected candidates are not persisted.
Numerical thread pools are capped to avoid nested oversubscription.

Targets, target timestamps, split and provenance fields are excluded from X.
The CSV partition reader parses only requested row bounds; test labels are not
parsed during training/validation reads. Validation selection/configurations and
row identities were written to `validation_selection.json` before test access.
The selection-lock hash is checked against the bundle and final results. Every
model was fitted on training only; there was no validation refit or test tuning.
Prior partition target times remain strictly before the next origin boundary.

Metrics are MAE, RMSE and R2. Predictions delivered by the public interface are
clipped to [0,12], without rounding; fractional values are expected counts.
Raw/clipped metrics and clipping frequency are saved. R2 is explicitly undefined
for constant targets. The fixed clipping rule applies equally before selection.
Linear Regression required clipping on 12.31% of validation and 15.03% of test
rows. Persistence and forest required none.

## Run and verify locally

From the repository root:

```powershell
$phase4Python = Join-Path $env:LOCALAPPDATA 'SmartParking\ml-runtime\Scripts\python.exe'
& $phase4Python -B -m pip check
& $phase4Python -B -m ml.tools.phase4_test_runner --native `
  --output reports/evidence/phase4_native_followup.json
# Only for a deliberate new training run; never overwrite released results:
& $phase4Python -B -m ml.train_phase4 --output-dir ml/artifacts/phase4_followup
# Verify the released run without retraining/reselecting:
& $phase4Python -B -m ml.tools.verify_phase4 --run-dir ml/artifacts/phase4 `
  --output reports/evidence/phase4_model_verification_followup.json
```

Outputs use exclusive creation. Native dependency/policy errors are failures;
never bypass them. Repeating evaluation to verify a frozen saved model is allowed;
reusing test results to change configurations/model selection is not.
The original `ml/train.py` placeholder remains byte-identical because Phase 3
fingerprints include it. Phase 4 training is in `ml/train_phase4.py`.

## Approved runtime installation and initial failures

The original `.venv` failed sklearn native imports under Application Control.
ABI and installed-wheel RECORD hashes matched and pip check found no conflicts.
No already working alternative local runtime was present. The user explicitly
approved a new isolated environment outside OneDrive. Existing Python created
it; only official PyPI binary packages at the exact versions listed in
`phase4_requirements.txt` were installed, using an isolated pip configuration.

The first isolated import found missing cloudpickle, not a policy denial. The
three declared dependencies cloudpickle, python-dateutil and tzdata were added
at their existing project pins. The completed preflight and pip check passed.
No security policy was weakened and no DLL was manually relocated. Why the
original environment failed while the clean one works is not conclusively
established. Use the verified isolated interpreter rather than claiming the
original environment was repaired.

The initial full-data run saved its locked selection and trained bundle, then
an exact-equality reload assertion rejected forest roundoff. Two reloads differed
by at most 1.7763568394002505e-15 slots; the other models were exactly equal.
Reload agreement now uses absolute tolerance 1e-12 and relative tolerance zero.
The unchanged artifact was finalized by `ml.tools.finalize_phase4`; no model,
hyperparameter or selected model changed. Test metrics were recomputed for
recovery and independently verified, not used for retuning. The final 21-test
native suite and all 28 saved-model checks passed. Historical failed evidence
is preserved rather than replaced.

## Saved bundle and Phase 5 prediction interface

`ml/artifacts/phase4/parking_models.joblib` is one compressed bundle containing
persistence, the fitted linear pipeline, the selected forest, selected model
name, feature order, 15-minute horizon and dataset/selection hashes. It is
851,974 bytes. Dataset/model directory storage is 8,190,119 bytes (8.190 MB),
including supporting JSON and Git attributes; limit 50,000,000 bytes.
No duplicate dataset, per-model bundle or prediction-row export was saved.

```python
import json
from pathlib import Path
from ml.phase4_models import load_predictor

results = json.loads(Path("ml/artifacts/phase4/model_results.json").read_text())
predictor = load_predictor(
    "ml/artifacts/phase4/parking_models.joblib",
    expected_sha256=results["artifact"]["sha256"],
)
# DataFrame with exactly FEATURE_COLUMNS, one named dict, or a list of dicts.
predicted_counts = predictor.predict(feature_rows)
# Optional comparison: predictor.predict(feature_rows, "linear_regression")
```

Launch the future Streamlit dashboard with a compatible approved local runtime.
Streamlit installation/integration is a separate phase; it has not been added
here. Missing real history or UNKNOWN slots must yield unavailable forecasts,
not synthetic replacements. Named columns are reordered safely. Missing/extra
columns, nonfinite/string/boolean inputs and invalid current slot sums are
rejected. The interface clips all three models to [0,12]. Load only your own
trusted joblib artifact; a checksum is not an authenticity/pickle-safety proof.

## Evidence and limitations

- `phase4_isolated_complete_preflight.json`: successful local native imports.
- `phase4_installation_trial.json`: exact pins, official index and preserved venv.
- `phase4_native_tests_final.json`: 21 actual tests, no failures/errors/skips.
- `phase4_reload_diagnosis.json`: numerical-only failed assertion and correction.
- `phase4_model_verification.json`: all 28 saved-model verification checks passed.
- `ml/artifacts/phase4/validation_selection.json`: lock and all four RF candidates.
- `ml/artifacts/phase4/model_results.json`: actual raw/clipped validation/test metrics.
- Phase 4 acceptance checklist, final verification JSON and comprehensive PDF.

Limitations: uncalibrated synthetic demand, perfect binary observations, strong
persistence, redundant features, four forest configurations and one holdout
period. No real-world performance or live Wokwi success is claimed. No Phase 5,
backend, firmware, data-generation or notebook work is performed.
