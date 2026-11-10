# IoT-Based Smart Parking System

Academic project for simulated parking occupancy monitoring and a labelled
15-minute occupancy forecasting demonstration.

## Current stage

The sensor layer now targets **12 parking slots across three ESP32 boards**,
with four HC-SR04 sensors and four ECHO voltage dividers per board. Firmware
has three board-specific builds with Phase 1 Wi-Fi/MQTT telemetry and Serial
diagnostics. Phase 1 production delivery is operator-observed; detailed archived
ESP32 runtime acceptance remains incomplete. Phase 2 adds validated MQTT ingestion,
SQLite history/current state and a FastAPI REST API. See `backend/README.md` for
startup, endpoints, tests and limitations. ML and dashboard remain placeholders.
Automated verification uses private temporary databases, preserving live data.

The updated planned architecture is: three ESP32 boards + 12 HC-SR04 sensors
-> MQTT / Mosquitto -> FastAPI + SQLite -> future Streamlit / Plotly, with a
separate offline ML preparation path and backend prediction serving. Phase 1
MQTT details and validation limits are in `esp32/MQTT.md`. Future aggregation must use 12 total
slots and distinguish missing devices from vacant spaces.

Wokwi does not support multiple microcontrollers in one simulation. Therefore
`esp32/diagram.json` is a three-board wiring overview, while three separate
single-board projects under `esp32/simulations/` are the runnable configurations.
See the [Wokwi FAQ](https://docs.wokwi.com/faq#how-do-i-use-multiple-microcontrollers-in-a-single-project).
The original PDF in local `output/pdf/` describes the historical four-slot
baseline; this README and `esp32/README.md` supersede its slot-count assumptions.
The PDF is preserved, and generated output remains untracked.

## Open a simulation in VS Code

Use **File > Open Workspace from File** and choose one of the repository-root
workspace files:

- `smart-parking-esp32-01.code-workspace`: ESP32-01, P1-P4.
- `smart-parking-esp32-02.code-workspace`: ESP32-02, P5-P8.
- `smart-parking-esp32-03.code-workspace`: ESP32-03, P9-P12.

Each workspace puts the intended simulation folder first, so Wokwi can discover
its `wokwi.toml` automatically, and includes the full repository for access to
the shared firmware/build outputs. Run **Wokwi: Start Simulator** from the
Command Palette, or use Play on the `diagram.json` in the named simulation
folder. Do not use Play on the three-board overview `esp32/diagram.json`.
Build the selected environment first if its `.bin`/`.elf` files are missing.
Discovery/path checks do not establish a successful simulation run.

## Layout

```text
esp32/
  src/main.cpp
  include/config.example.h
  include/mqtt_config.h
  platformio.ini
  diagram.json
  README.md
  MQTT.md
  simulations/
    esp32-01/{diagram.json,wokwi.toml}
    esp32-02/{diagram.json,wokwi.toml}
    esp32-03/{diagram.json,wokwi.toml}
  tools/
    generate_diagrams.py
    run_host_tests.py
    check_mqtt.py
  tests/
    test_circuits.py
    test_firmware.cpp
    fakes/Arduino.h
    fakes/WiFi.h
    fakes/MQTT.h
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
smart-parking-esp32-01.code-workspace
smart-parking-esp32-02.code-workspace
smart-parking-esp32-03.code-workspace
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
ML and dashboard modules remain placeholders; end-to-end ESP32-to-API verification
requires fresh production telemetry. Phase 2 broker tests use labelled synthetic fixtures.

## Local configuration and data policy

- Keep `.env`, firmware `config.h`, credentials, private keys and logs out of Git.
- `.env.example` contains safe backend defaults. Production topics stay fixed
  to the three existing ESP32 topics; private credentials remain untracked.
- Store the live database at `%LOCALAPPDATA%\SmartParking\parking.db`, outside
  this OneDrive-backed project directory. See `database/README.md`.
- Keep synthetic training history explicitly labelled and separate from live
  Wokwi sensor telemetry. Do not use synthetic values for live slot status.
- Phase 1 delivery is operator-observed, with no archived payloads. Detailed
  ESP32 runtime tests remain open; Phase 2 synthetic backend checks do not prove
  sensor accuracy or physical voltage levels. See the reports index.

## Version control

For the Phase 2 implementation, complete all checks first, then make one
meaningful commit per changed file with exactly one file per commit, followed
by one push containing all commits. Never commit secrets, environments, build output, live databases or
temporary files. The compiled original four-slot implementation is preserved
at tag `backup/4-slot-serial-baseline` (commit `c1acc46`). To inspect it without
overwriting this checkout, use a separate clone or `git worktree add`.

## Phase 2 reference

See [backend instructions](backend/README.md), [database policy](database/README.md),
and [Phase 2 report](reports/phase2_fastapi_sqlite.pdf). The report distinguishes
automated tests, isolated local-broker integration and production observations.
