# Approved trial outcome: successful local Windows execution

The user-approved isolated environment at `%LOCALAPPDATA%\SmartParking\ml-runtime` now passes imports, 21 native/contract tests, actual project fitting/evaluation and all 28 saved-model checks. The original venv was preserved and no security policy was changed. See phase4_installation_trial.json and phase4_model_verification.json.

The following pre-trial review is retained as historical context; its blocked status and approval request are superseded by the successful trial above.

# Phase 4 local Windows runtime review

No installation or security-policy change has been performed. A compliant native runtime has not yet been identified.

## Observed blocker

The existing Python 3.12.10 x64 environment has compatible cp312 wheels and no pip dependency conflicts. Native import fails with an Application Control denial. Files match their installed wheel RECORD hashes; copying/reinstalling the same hashes is not a demonstrated remedy.

| scikit-learn native module | Actual SHA-256 |
| --- | --- |
| sklearn/utils/_openmp_helpers.cp312-win_amd64.pyd | dec08cd057ac558eb82df7691089008ca5d9e28e7518ee2889761356e79533d2 |
| sklearn/linear_model/_sag_fast.cp312-win_amd64.pyd | 5b34cef1fac5247d0521b8f5e3e553c6d177ddb04dd9f5ce4d0085f8e5ac7080 |
| sklearn/neighbors/_partition_nodes.cp312-win_amd64.pyd | cc8d0cb9609652fccb6f82b1950e71eedd90e76f7d364d31ed76e97d3fda853a |

Code Integrity event 3077 separately confirms a PyArrow signing denial under policy `{0283ac0f-fff1-49ae-ada1-8a933130cad6}`. That event must not be represented as a correlated scikit-learn policy event. The sklearn import error itself identifies the native module denial.

## Proposed local solution requiring approval

Use a security-owner-approved scientific Python deployment on this Windows laptop. A proposed side-by-side destination is `%LOCALAPPDATA%\SmartParking\ml-runtime`, preserving the current `.venv` and frozen requirements. The exact installer/package source and its existing-policy authorization must be confirmed before creating an environment or installing packages. The initial reproducibility reference is Python 3.12 x64 and the reference versions in `ml/phase4_requirements.txt`.

An ordinary pip reinstall or new location alone is not an approved-trust mechanism or a proven solution. I will not change trust flags, exclusions, signing policies or process mitigations. If the current policy cannot authorize the official native packages through the approved installation process, the administrator must supply a compliant local runtime before training can proceed.

## Read-only manual context check

From a normal Windows PowerShell session, using the existing environment only:

```powershell
.\.venv\Scripts\python.exe -B -c "from sklearn.linear_model import LinearRegression; from sklearn.ensemble import RandomForestRegressor; print('Native imports passed')"
```

This does not install or change anything. If it succeeds there, report that result so the approved execution context can be compared. If it is also denied, provide the diagnostic package to the device/security administrator. Do not disable security features.

## Required verification after approval

1. Run phase4_preflight with a new evidence filename.
2. Run `python -B -m ml.tools.phase4_test_runner --native --output reports/evidence/phase4_native_tests.json`.
3. Run `python -B -m ml.train_phase4 --output-dir ml/artifacts/phase4` exactly once for final evaluation.
4. Run `python -B -m ml.tools.verify_phase4` to verify persisted model predictions/metrics.
5. Require the same permitted local runtime to load the artifact for Streamlit; regenerate the report with actual results.

No final training/evaluation results or committed delivery exist yet.
