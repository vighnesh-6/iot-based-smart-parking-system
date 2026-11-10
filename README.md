# IoT-Based Smart Parking System

Academic project for simulated parking occupancy monitoring and a labelled
15-minute occupancy forecasting demonstration.

## Current stage

The sensor layer now targets **12 parking slots across three ESP32 boards**,
with four HC-SR04 sensors and four ECHO voltage dividers per board. Firmware
is Serial-only and has three board-specific builds. Wi-Fi, MQTT, ingestion,
database operations, APIs, ML and dashboard behavior are not implemented.
No runtime database has been created. See `esp32/README.md` for wiring,
build/test commands and the Wokwi runtime verification status.

The updated planned architecture is: three ESP32 boards + 12 HC-SR04 sensors
-> future MQTT / Mosquitto -> FastAPI + SQLite -> Streamlit / Plotly, with a
separate offline ML preparation path and backend prediction serving. No MQTT
integration is added in this milestone. Future aggregation must use 12 total
slots and distinguish missing devices from vacant spaces.

Wokwi does not support multiple microcontrollers in one simulation. Therefore
`esp32/diagram.json` is a three-board wiring overview, while three separate
single-board projects under `esp32/simulations/` are the runnable configurations.
See the [Wokwi FAQ](https://docs.wokwi.com/faq#how-do-i-use-multiple-microcontrollers-in-a-single-project).
The original PDF in local `output/pdf/` describes the historical four-slot
baseline; this README and `esp32/README.md` supersede its slot-count assumptions.
The PDF is preserved, and generated output remains untracked.

## Layout

```text
esp32/
  src/main.cpp
  include/config.example.h
  platformio.ini
  diagram.json
  README.md
  simulations/
    esp32-01/{diagram.json,wokwi.toml}
    esp32-02/{diagram.json,wokwi.toml}
    esp32-03/{diagram.json,wokwi.toml}
  tools/
    generate_diagrams.py
    run_host_tests.py
  tests/
    test_circuits.py
    test_firmware.cpp
    fakes/Arduino.h
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

The sensor build and test commands are documented in `esp32/README.md`.
Other modules remain placeholders; this is not an end-to-end parking system.

## Local configuration and data policy

- Keep `.env`, firmware `config.h`, credentials, private keys and logs out of Git.
- `.env.example` contains safe defaults only; the topic suffix must be unique
  for the project when implementation starts.
- Store the live database at `%LOCALAPPDATA%\SmartParking\parking.db`, outside
  this OneDrive-backed project directory. See `database/README.md`.
- Keep synthetic training history explicitly labelled and separate from live
  Wokwi sensor telemetry. Do not use synthetic values for live slot status.
- Wokwi runtime testing remains pending. Build/host-logic/netlist checks do not
  establish successful simulation, physical voltage levels or sensor accuracy.

## Version control

Use meaningful commits for completed work, verify staged content and push each
commit. Never commit secrets, environments, build output, live databases or
temporary files. The compiled original four-slot implementation is preserved
at tag `backup/4-slot-serial-baseline` (commit `c1acc46`). To inspect it without
overwriting this checkout, use a separate clone or `git worktree add`.
