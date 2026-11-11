# Smart Parking integration reports

## Phase 5: Local-first, cloud-ready Streamlit dashboard

[Comprehensive Phase 5 PDF](phase5_streamlit_dashboard.pdf) documents architecture,
implementation, freshness, causal history, prediction adapters, actual tests,
limitations and the five separate Phase 6 deployment responsibilities.

- **117 tests passed:** 32 dashboard, 43 existing backend and 42 existing ML tests.
- Actual AppTest interactions against the existing API rendered 12 slot cards,
  history/coverage charts and a separate genuine synthetic retrospective forecast.
- Local dashboard page and health return HTTP 200 on port 8501.
- Production readings remain incomplete: **0 occupied, 0 vacant, 12 unknown**;
  P1-P8 unseen, P9-P12 stale. Live forecasting is correctly unavailable.
- Both execution adapters reuse the unchanged Phase 4 predictor. In-process
  execution was tested on local Windows, not on a cloud/Linux host.
- All **119 protected tracked files** remain unchanged. No dependencies were
  installed or removed, and no security policy or existing service was modified.
- The project environment already contained extra Jupyter packages beyond the
  historical requirements snapshot. Their metadata predates Phase 5; the frozen
  pins are preserved. The exact freeze mismatch is recorded, not concealed.
- **11 PDF pages** were rendered and visually reviewed. Cloud deployment and
  real-browser refresh timing remain unverified; no browser control was used.

See [dashboard instructions](../dashboard/README.md),
[acceptance checklist](phase5_acceptance_checklist.md),
[actual tests and observations](evidence/phase5_dashboard_verification.json), and
[final PDF/preservation checks](evidence/phase5_final_checks.json).
The Phase 1-4 reports and all frozen datasets, notebooks and model artifacts below
remain unchanged. Synthetic model review never replaces missing live telemetry.

## Executed Phase 3/4 notebooks

The four title-only notebooks were replaced with these eight manually authored
notebooks in the existing `ml/notebooks/` folder:

| Notebook | Purpose |
| --- | --- |
| [01 Synthetic history and EDA](../ml/notebooks/01_synthetic_history_and_eda.ipynb) | Frozen provenance, minute cadence, slot transitions and patterns |
| [02 Causal feature engineering](../ml/notebooks/02_causal_feature_engineering.ipynb) | Past-only features, exact future labels, intervention and purge checks |
| [03 Training artifact review](../ml/notebooks/03_training_artifact_review.ipynb) | Saved training configuration and training-only scaler verification |
| [04 Frozen evaluation review](../ml/notebooks/04_frozen_evaluation_review.ipynb) | Explicitly archived results, acceptance evidence and limitations |
| [05 Persistence baseline](../ml/notebooks/05_persistence_baseline.ipynb) | Actual saved-baseline predictions and held-out metric reproduction |
| [06 Linear Regression](../ml/notebooks/06_linear_regression.ipynb) | Saved pipeline, clipping and held-out metric reproduction |
| [07 Random Forest](../ml/notebooks/07_random_forest.ipynb) | Saved tuning, configuration and held-out metric reproduction |
| [08 Evaluation and selection](../ml/notebooks/08_model_evaluation_and_selection.ipynb) | Fair comparison, locked selection and prediction interface |

All **8 notebooks / 27 code cells** executed successfully in fresh kernels using
the approved isolated Windows ML runtime. The existing ML suite also passed
**42 tests**. Outputs are saved in the notebooks. Notebook 04 labels archived
evidence explicitly; notebooks 05–08 recompute predictions from the trusted
saved model. No frozen data, source, models or PDFs were rewritten.

[Notebook execution evidence](evidence/notebook_execution_verification.json)
records exact dependency pins, checksums, actual execution timings, regression
test output and preservation checks. It also records an initial failed notebook
assertion corrected by signed integer differencing, plus the blocked Jupyter
launcher. After the operator reported an out-of-order `Path` NameError in
notebook 08, its final verification cell received an explicit import and the
entire notebook passed again from a fresh approved kernel (counts 1–4).
These earlier failures are not counted as passes.

### Local execution

Select `%LOCALAPPDATA%\SmartParking\ml-runtime\Scripts\python.exe` as the notebook
interpreter in VS Code, then run all cells in order. Each notebook verifies its
interpreter and locates the repository root. The project `.venv` is unchanged.
Notebook outputs describe synthetic data only; no live forecast or real-world
accuracy is established. There is no model fitting or dataset generation in
the notebooks. The regression tests separately train small temporary fixtures.

The approved Jupyter packages are `ipykernel==6.30.1`, `nbclient==0.10.2` and
`nbformat==5.10.4`; exact transitive versions and official PyPI wheel hashes are
in the evidence JSON. ML package versions were preserved.

Windows Application Control blocked the installed `jupyter-execute.exe` launcher
with WinError 4551. Python imports passed. With explicit operator approval,
execution used the supported **nbclient Python API** through the approved
interpreter. No policy, trust exception or DLL location was changed.

For the same API route, register a temporary kernel from the repository root:

```powershell
$py = "$env:LOCALAPPDATA\SmartParking\ml-runtime\Scripts\python.exe"
& $py -B -m ipykernel install --prefix "$PWD/tmp/notebook_jupyter" `
  --name smartparking-ml --display-name 'Smart Parking (approved ML runtime)'
$env:JUPYTER_PATH = "$PWD/tmp/notebook_jupyter/share/jupyter"
$env:JUPYTER_RUNTIME_DIR = "$PWD/tmp/notebook_jupyter/runtime"
$env:IPYTHONDIR = "$PWD/tmp/notebook_jupyter/ipython"
$env:PYTHONDONTWRITEBYTECODE = '1'
```

Then run this Python code with that interpreter from the repository root.
It executes existing, manually authored notebooks; it does not generate cells:

```python
import asyncio
from pathlib import Path
import nbformat
from nbclient import NotebookClient

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
for path in sorted(Path("ml/notebooks").glob("*.ipynb")):
    notebook = nbformat.read(path, as_version=4)
    NotebookClient(notebook, kernel_name="smartparking-ml", timeout=180,
                   resources={"metadata": {"path": str(Path.cwd())}}).execute()
    nbformat.write(notebook, path)  # Save actual execution outputs only.
```

On another machine, use an approved local environment and adjust the explicit
interpreter assertion in an authorized working copy. If native imports are
blocked, stop and obtain an approved runtime; do not disable security controls.
All existing phase PDFs below remain unchanged.

## Phase 4: Machine Learning Model Development

[Comprehensive Phase 4 PDF](phase4_machine_learning_model_development.pdf) covers
actual local fitting, validation-only selection, held-out metrics, model bundle,
interface, runtime resolution and limitations.

- The approved isolated Windows runtime passed imports and all **21 tests**.
- All **28 saved-model checks passed**; the original project venv was preserved.
- **Persistence wins validation MAE** (0.339983); test MAE/RMSE/R2 are
  0.307714 / 0.648092 / 0.945254. Linear and forest are saved for comparison.
- All models use identical validation and test rows; selection was locked first.
- Bundle: **851,974 bytes**; total data/model storage: **8,190,119 bytes**.
- Original native import denials and a strict RF floating-point reload failure
  are preserved. Finalization used the unchanged trained artifact with 1e-12
  reload tolerance, without retraining, retuning or changing selection.
- Phase 1/2/3 artifacts remain frozen. These results establish synthetic holdout
  performance only, not real-world accuracy or Wokwi runtime success.

See [local instructions](../ml/PHASE4.md),
[acceptance checklist](phase4_acceptance_checklist.md),
[installation evidence](evidence/phase4_installation_trial.json),
[final native tests](evidence/phase4_native_tests_final.json),
[model verification](evidence/phase4_model_verification.json), and
[final checks](evidence/phase4_final_checks.json).

## Phase 3: Historical Dataset Preparation

[Comprehensive Phase 3 PDF](phase3_historical_dataset_preparation.pdf) documents
synthetic generation, schema, calculations, causal features, target alignment,
chronological partitions, actual tests, storage and limitations.

- Raw: **80,640 one-minute rows**, 8 weeks, exactly P1-P12; all explicitly synthetic.
- Processed: **70,515 rows**, 37 predictors; train 49,360, validation 10,577,
  test 10,578, with 15-minute boundary purges and integer-rounded 70/15/15 allocation.
- **18 critical dataset checks and 21 software tests passed.**
- Dataset/model storage: **7,327,764 bytes (7.328 MB)**; no model trained.
- Processed format is deterministic gzip CSV: Windows Application Control blocks
  the existing PyArrow DLL. Parquet remains unverified; dependencies/security
  policy were preserved. Raw CSV and one compressed processed table are retained.
- Frozen Phase 1/2 implementation, reports/evidence, notebooks and live data remain unchanged.

See [ML instructions](../ml/README.md),
[acceptance checklist](phase3_acceptance_checklist.md),
[dataset validation](evidence/phase3_dataset_validation.json),
[actual test execution](evidence/phase3_tests.json), and
[final verification](evidence/phase3_final_checks.json).
These checks certify synthetic preparation, not real-world accuracy.

## Phase 2: FastAPI and SQLite

[Comprehensive Phase 2 PDF](phase2_fastapi_sqlite.pdf) documents architecture,
telemetry validation, atomic persistence, APIs, commands, actual tests and limits.
See [backend run instructions](../backend/README.md).

- Final automated suite: **43 tests passed**, no skips, failures or errors.
- Real local Mosquitto integration: **7 checks passed** using synthetic fixtures
  confined to unique validation topics and a private temporary database.
- Verified broker/backend transport reconnection, restart persistence,
  deduplication and a synthetic occupancy transition through actual HTTP.
- Production observation: subscriptions were active and health returned 200,
  but the 30-second window received **zero production observations**. Slots
  correctly remained unseen UNKNOWN. No new ESP32-to-API runtime pass is claimed.
- An expanded pre-fix test run caught a Paho exception-handler bug; failed
  evidence is preserved, and the corrected final run passed.
- Existing database files were never selected for automated tests or reset.
  A test-created unrelated database was rejected with unchanged content hash.
  ESP32, ML, dashboard, broker configuration and dependency snapshot stayed unchanged.

Evidence files:

| JSON | Meaning |
| --- | --- |
| phase2_unit_tests.json | Final 43-test run, test IDs, runner output and source hashes |
| phase2_pre_fix_tests.json | Earlier 43-test run with one failure before handler correction |
| phase2_broker_integration.json | Initial successful isolated broker/API test |
| phase2_final_integration.json | Successful seven-check integration rerun after final code correction |
| phase2_production_observation.json | Read-only 30-second production subscription observation |
| phase2_repository_checks.json | Circuit regression, protected paths, dependencies and broker config hash |

The JSON archives and PDF distinguish synthetic backend verification from actual
ESP32 telemetry. Broker session retention and firmware restart identity limits
remain documented; there is no exactly-once or lossless-outage claim.

Generate the Phase 2 PDF with the bundled tooling or another ReportLab-enabled
Python environment: `python reports/generate_phase2_report.py`.

## Phase 1 MQTT audit

[Comprehensive PDF](phase1_mqtt_integration.pdf) covers the three-board, twelve-slot
architecture, configuration, telemetry contract, commands, results and continuation.

## Verification status

- **Build evidence:** all three diagnostic firmware targets compiled successfully.
- **Saved test evidence:** local broker connection/subscription checks and isolated
  Python publisher smoke test passed. Three saved production windows (90/60/45 s)
  received zero production messages; those results remain unchanged.
- **Operator-observed delivery:** the operator later confirmed all three Wokwi
  simulations running simultaneously and telemetry arriving on all three production
  topics, with P1-P4, P5-P8 and P9-P12 respectively. No original screenshot, raw
  production payload or Serial log remains available. This is not independently
  archived runtime evidence.
- **Still unverified:** exact production JSON validation, measured cadence,
  timestamp/NTP accuracy, occupancy transitions and controlled reconnection.
- **Host tests:** diagnostic programs compiled for all boards; execution was not
  attempted after earlier Windows Application Control blocks. A complete final
  host runtime pass is not claimed.

`evidence/phase1_operator_observation.json` records the operator statement only.
Other JSON files retain earlier capture results, broker diagnostics, environment
metadata and diagnostic build hashes. The interrupted diagnostic-restart capture
left no saved evidence and is not counted as a result. No fabricated Serial logs
or production payload fixtures are included.

## Reproduce

Run from the repository root with the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe esp32/tests/test_circuits.py
.\.venv\Scripts\python.exe esp32/tools/run_host_tests.py --compile-only
.\.venv\Scripts\python.exe esp32/tools/check_mqtt.py --smoke --timeout 5
.\.venv\Scripts\python.exe esp32/tools/verify_mqtt_runtime.py `
  --duration 90 --label followup `
  --output reports/evidence/phase1_mqtt_followup.json
```

The final command requires running simulations and a new output filename. It
only subscribes; smoke fixtures use an isolated validation namespace.
See [Serial capture guidance](../esp32/MQTT.md#serial-diagnostics-and-saved-capture).

Generate the PDF with a Python environment containing ReportLab:

```powershell
python reports/generate_phase1_report.py
```

The generator uses Windows Arial and Consolas fonts. Report generation reads the
evidence files; it does not run simulations or promote operator statements into
independent test passes. PDF dependencies were provided by the bundled tooling;
the project's dependency snapshot and virtual environment were preserved.

At the Phase 1 milestone, Mosquitto configuration, circuits and unrelated modules
were unchanged, and FastAPI/SQLite had not started. Phase 2 is documented above;
detailed ESP32 acceptance tests remain open.
# Phase 6 - Sequential integration and deployment readiness

- [Comprehensive Phase 6 PDF](phase6_end_to_end_integration_and_deployment.pdf)
- [Acceptance checklist](phase6_acceptance_checklist.md)
- [Final test and live API evidence](evidence/phase6_final_acceptance.json)
- Per-board raw captures and exact SQLite matches:
  [ESP32-01 capture](evidence/phase6_sequential_esp32_01_mqtt.json),
  [verification](evidence/phase6_sequential_esp32_01_persistence.json);
  [ESP32-02 capture](evidence/phase6_sequential_esp32_02_mqtt.json),
  [verification](evidence/phase6_sequential_esp32_02_persistence.json);
  [ESP32-03 capture](evidence/phase6_sequential_esp32_03_mqtt.json),
  [verification](evidence/phase6_sequential_esp32_03_persistence.json).

All three boards passed **sequential** MQTT-to-SQLite checks (40 messages / 160
matching slot observations). This does not establish simultaneous operation,
continuous monitoring or a genuine live forecast. ESP32-02 repeated one sequence;
the second payload was retained as history-only. No continuous UART log archive
was established. Earlier failed captures and intermediate local checks remain
under `evidence/phase6_*`; the final acceptance file is authoritative.

Individual-slot plots now preserve actual receipt events and gaps; total occupancy
still requires twelve known states. Cloud deployment and Linux runtime verification
remain deferred under the no-install/no-credentials constraints. Previous PDFs
are unchanged. Reproduction commands and zero-cost hosting limitations are in the
Phase 6 report.

## Phase 6 supplement - Persistence-only live inference

- [Visually reviewed verification supplement](phase6_persistence_only_live_supplement.pdf)
- [Actual integration and complete regression evidence](evidence/phase6_persistence_live_integration.json)
- [Reproducible report renderer](generate_phase6_persistence_supplement.py)

The separate `/predictions/persistence-live` endpoint and dashboard panel implement
the exact Persistence rule without replacing the frozen 37-feature interface.
All twelve slots must be genuinely observed, known and fresh, including receipt
and measurement timestamps, within at most 30 seconds. Unavailable responses
explain each blocker and contain no forecast.

All 140 Python regressions passed (51 backend, 44 dashboard, 42 ML, 3 circuit).
Real-API AppTest and the running dashboard's WebSocket fragment refresh passed on
ports 8001/8503. Browser rendering remains blocked by Computer Use policy. Current
SQLite observations are all stale; no genuine live prediction is claimed. The
SQLite file hash and frozen artifacts are unchanged. API8001 is a read-only
verification instance with MQTT disabled; the original collector8000 was left
running and requires a later normal restart to activate its new route. Cloud
deployment has not begun. Existing reports remain unchanged.

## Phase 7 - cloud readiness and deployment gate

- [Phase 7 PDF: verified readiness and actual deployment status](phase7_final_cloud_deployment.pdf)
- [Complete local and public Linux readiness evidence](evidence/phase7_readiness.json)
- [Zero-cost account/deployment runbook](phase7_deployment_runbook.md)
- [Reproducible PDF renderer](generate_phase7_report.py)
- [Successful Linux verification run](https://github.com/vighnesh-6/iot-based-smart-parking-system/actions/runs/43106716753)

PostgreSQL persistence, verified MQTT TLS, configurable API authentication and
three opt-in cloud firmware targets are implemented. Local Windows results:
147 passed, five real-PostgreSQL tests explicitly skipped locally. The successful
Linux run includes real PostgreSQL tests, regression suites, unchanged saved-model
inference, C++ host tests and all six firmware builds. Raw private CI logs were
not retrieved; the public run/job/step conclusions are archived as evidence.

**Deployment remains blocked at account-console access.** Computer Use reports
that the browser access host is unavailable. No provider resources have been
created, no account-specific card-free eligibility has been confirmed, and no
public dashboard URL or real cloud telemetry delivery is claimed. The operator
console handoff is pending. Stop if any provider requires payment details.

The original SQLite file, frozen artifacts, prior PDFs and full 37-feature ML
pipeline are unchanged. Wokwi telemetry still depends on the laptop/simulator;
free-tier sleep and quotas prevent a reliable 24/7-monitoring claim. All twelve
current readings remain stale, so no genuine live forecast is available.
