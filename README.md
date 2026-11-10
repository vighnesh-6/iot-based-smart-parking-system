# IoT-Based Smart Parking System

Academic project for simulated parking occupancy monitoring and a labelled
15-minute occupancy forecasting demonstration.

## Current stage

Repository scaffolding only. Firmware, ingestion, database operations, APIs,
data generation, model training and dashboard behavior are not implemented.
No sensor circuit or runtime database has been created.

The finalized architecture remains: Wokwi + ESP32 + four HC-SR04 sensors ->
MQTT / Mosquitto -> FastAPI + SQLite -> Streamlit / Plotly, with a separate
offline ML preparation path and backend prediction serving. See page 14 of
the architecture report for the repository layout. The existing report stays
in the local `output/pdf/` directory; generated output is not tracked.

## Layout

```text
esp32/
  src/main.cpp
  include/config.example.h
  platformio.ini
  diagram.json
  wokwi.toml
backend/
  __init__.py
  main.py
  mqtt_ingest.py
  db.py
  schemas.py
ml/
  __init__.py
  generate_data.py
  features.py
  train.py
  data/.gitkeep
  artifacts/.gitkeep
  notebooks/
    01_synthetic_data_generation_and_eda.ipynb
    02_feature_engineering.ipynb
    03_model_training.ipynb
    04_model_evaluation.ipynb
dashboard/app.py
database/README.md
config/mosquitto.conf
.env.example
.gitignore
requirements.txt
README.md
```

`.gitkeep` files preserve otherwise empty directories in Git. Each notebook
contains only one title Markdown cell; code cells will be added manually in
the ML phase.

## Existing environment

The existing `.venv` and its installed dependencies are preserved.
`requirements.txt` is an exact `pip freeze` snapshot from that environment,
not a newly installed dependency set. No environment activation is required
to inspect it in Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip --version
.\.venv\Scripts\python.exe -m pip freeze
```

Implementation and launch commands will be added only when those components
exist. The current placeholders are not a runnable system.

## Local configuration and data policy

- Keep `.env`, firmware `config.h`, credentials, private keys and logs out of Git.
- `.env.example` contains safe defaults only; the topic suffix must be unique
  for the project when implementation starts.
- Store the live database at `%LOCALAPPDATA%\SmartParking\parking.db`, outside
  this OneDrive-backed project directory. See `database/README.md`.
- Keep synthetic training history explicitly labelled and separate from live
  Wokwi sensor telemetry. Do not use synthetic values for live slot status.
- Wokwi VS Code entitlement and connectivity will be verified in the next
  implementation stage; no architecture change is introduced here.

## Version control

Use meaningful commits for completed work, verify staged content and push each
commit. Never commit secrets, environments, build output, live databases or
temporary files. This repository starts with scaffolding, not completed modules.
