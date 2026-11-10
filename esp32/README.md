# Twelve-slot sensor architecture

## Assignment and wiring

Three independent ESP32-DevKitC V4 boards each handle exactly four HC-SR04
sensors. The same local GPIO pairs are reused on separate boards:

| Board / build environment | Slot | TRIG | ECHO GPIO after divider |
| --- | --- | --- | --- |
| ESP32-01 / esp32_01 | P1 | 13 | 34 |
| ESP32-01 / esp32_01 | P2 | 14 | 35 |
| ESP32-01 / esp32_01 | P3 | 25 | 32 |
| ESP32-01 / esp32_01 | P4 | 26 | 33 |
| ESP32-02 / esp32_02 | P5 | 13 | 34 |
| ESP32-02 / esp32_02 | P6 | 14 | 35 |
| ESP32-02 / esp32_02 | P7 | 25 | 32 |
| ESP32-02 / esp32_02 | P8 | 26 | 33 |
| ESP32-03 / esp32_03 | P9 | 13 | 34 |
| ESP32-03 / esp32_03 | P10 | 14 | 35 |
| ESP32-03 / esp32_03 | P11 | 25 | 32 |
| ESP32-03 / esp32_03 | P12 | 26 | 33 |

For every slot Px:

- VCC -> **its assigned board's 5V**.
- GND -> **its assigned board's GND.1**.
- TRIG -> its GPIO in the table, on that same board.
- ECHO -> `Px_echo_series:1` (1,000 ohms).
- `Px_echo_series:2` -> the assigned ECHO GPIO AND `Px_echo_shunt:1` (1,800 ohms).
- `Px_echo_shunt:2` -> the assigned board's GND.1.

The divider produces a calculated 5 * 1800 / (1000 + 1800) = **3.214 V** at
the GPIO for a 5 V ECHO high. Use 1% resistors for physical hardware. Dividers
are independent; no ECHO nodes, GPIOs, 5V rails or grounds are wired between
the three board groups in these isolated circuits. Physical power/wiring
and measured logic levels still need validation before hardware use.
GPIO 34/35 are input-only, which is appropriate for ECHO. Physical sensors
on different boards may still interfere acoustically; the per-board quiet
interval does not coordinate three physical controllers.

## Firmware behavior

`src/main.cpp` is shared by three separate PlatformIO builds. Each environment
defines `PARKING_BOARD_ID=1`, `2` or `3`; a missing/invalid identity is a compile
error. A build contains only its four assigned slot identities, and every
reading includes the board name and slot ID. Do not flash the same board-01
binary onto all three boards; use the matching artifact.

Detection logic is unchanged from the four-slot baseline: a 10 us trigger,
bounded 30 ms echo wait, distance = pulse duration / 58, 2-400 cm valid range,
and 60 ms quiet time between local measurements. Scans target a one-second
interval. Valid distance <= `PARKING_OCCUPIED_THRESHOLD_CM` is **OCCUPIED**;
greater distance is **VACANT**. Timeout/out-of-range is **UNKNOWN**, not VACANT.
The default threshold is still 20 cm; Serial speed is **115200**. To override
the threshold, add a second flag such as `-DPARKING_OCCUPIED_THRESHOLD_CM=25.0f`
to the selected environment while retaining its board-ID flag.

Phase 1 Wi-Fi/MQTT telemetry is now implemented; see [MQTT.md](MQTT.md) for
topics, client IDs, timestamp semantics, reconnection and runtime checks.
The same readings and classifications still appear on Serial. No aggregate
occupancy service is added. Future backend work must use 12 configured slots
and per-device freshness; backend/ML/database/dashboard remain untouched.

## Wokwi project selection

Wokwi currently [does not support multiple microcontrollers in one simulation](https://docs.wokwi.com/faq#how-do-i-use-multiple-microcontrollers-in-a-single-project).
`esp32/diagram.json` therefore shows the full three-board architecture for
wiring inspection only. It is not a single executable 12-slot simulation.
The old root `esp32/wokwi.toml` is removed to avoid offering a misleading launch
configuration. Instead, each of these folders is a separate Wokwi project:

| Project folder | Slots | Firmware path relative to its wokwi.toml |
| --- | --- | --- |
| simulations/esp32-01 | P1-P4 | ../../.pio/build/esp32_01/firmware.bin |
| simulations/esp32-02 | P5-P8 | ../../.pio/build/esp32_02/firmware.bin |
| simulations/esp32-03 | P9-P12 | ../../.pio/build/esp32_03/firmware.bin |

Each has a local diagram with one ESP32, four sensors, eight resistors and a
Serial Monitor connection. The repository contains three portable VS Code
workspace files to make discovery deterministic:

| Open with File > Open Workspace from File | First workspace folder |
| --- | --- |
| smart-parking-esp32-01.code-workspace | esp32/simulations/esp32-01 |
| smart-parking-esp32-02.code-workspace | esp32/simulations/esp32-02 |
| smart-parking-esp32-03.code-workspace | esp32/simulations/esp32-03 |

These files live at the repository root. Each also includes the full repository
as a second workspace folder, preserving access to shared source and compiled
artifacts. Relative firmware paths in all three TOML files remain unchanged.
After opening the intended workspace, run **Wokwi: Start Simulator** from the
Command Palette. Alternatively, open the local `diagram.json` under the first,
named simulation folder and press Play there. Build the corresponding PlatformIO
environment first if its firmware files do not exist.

The installed Wokwi extension automatically checks workspace-folder roots for
`wokwi.toml`; a nested config is not an automatic default when only the whole
repository is opened as a single folder. Its diagram-editor Play button also
looks for `wokwi.toml` beside that particular diagram. Consequently, pressing
Play on the **overview** at `esp32/diagram.json` reports a missing config; that
overview is intentionally not runnable. No root config is added to launch the
unsupported three-board combination.

To stay in an existing repository window instead, run **Wokwi: Select Config
File**, select `esp32/simulations/esp32-0N/wokwi.toml`, then run **Wokwi: Start
Simulator** from the Command Palette. If an old selection persists, reselect
the intended TOML or reload the intended `.code-workspace`. Do not press Play
on the overview after selecting a local configuration.

Concurrent runs require separate VS Code windows, each opened with its board's
workspace. No communication between simulations is implemented. Workspace
discovery and artifact-path checks are separate from runtime verification;
simulation execution is still pending. Browser/Computer Use is not used.

## Build and static/host tests

From the repository root with PlatformIO on PATH:

```powershell
pio run --project-dir esp32
# Or build a single board:
pio run --project-dir esp32 --environment esp32_02
.\.venv\Scripts\python.exe esp32/tools/generate_diagrams.py --check
.\.venv\Scripts\python.exe esp32/tests/test_circuits.py
.\.venv\Scripts\python.exe esp32/tools/run_host_tests.py
# If local Application Control disallows running newly compiled host binaries:
.\.venv\Scripts\python.exe esp32/tools/run_host_tests.py --compile-only
```

On this workstation, the existing isolated tools can be used instead of `pio`:

```powershell
$env:PLATFORMIO_CORE_DIR = Join-Path (Get-Location).Path 'tmp\platformio-core'
.\tmp\platformio-venv\Scripts\python.exe -m platformio run --project-dir esp32
```

`tools/generate_diagrams.py` is the wiring definition for all four diagrams.
After a deliberate circuit change, regenerate without `--check`, review the
diff, then run the independent netlist tests and Wokwi lint. Do not hand-edit
the derived diagrams and leave their generator out of sync.

`tests/test_circuits.py` checks exact slot ownership, divider values and topology,
isolated signal nodes, generated-file consistency and firmware config paths.
`tools/run_host_tests.py` uses an existing g++/clang++ or Visual Studio C++
installation. It includes the production firmware with fake Arduino I/O and
tests all three identities, pin initialization, trigger pulses, range/threshold
boundaries, timeout behavior, four-slot scans and timer wraparound. It does not
simulate ESP32 hardware, acoustic effects or resistor voltages. Host binaries
stay in ignored `tmp/firmware-host-tests/`.

With the official Wokwi CLI available, lint the overview and all local diagrams:

```powershell
.\tmp\tools\wokwi-cli.exe lint esp32/diagram.json
.\tmp\tools\wokwi-cli.exe lint esp32/simulations/esp32-01
.\tmp\tools\wokwi-cli.exe lint esp32/simulations/esp32-02
.\tmp\tools\wokwi-cli.exe lint esp32/simulations/esp32-03
```

Lint verifies supported components and pin references, not multi-board runtime
support or electrical behavior. Wokwi has only [basic analog simulation](https://docs.wokwi.com/parts/wokwi-resistor),
so a divider voltage must not be described as measured in Wokwi.

Prior sensor-only milestone validation: all three PlatformIO environments compiled
successfully (22,116 bytes RAM, 294,000 bytes flash each), and the independent
netlist/config tests passed. Wokwi CLI 0.29.1 lint exited 0 on all four diagrams,
with no errors or warnings, but an informational `unsupported-part` diagnostic
calls `board-esp32-devkit-c-v4` undocumented. The board is nevertheless listed
in Wokwi's official diagram documentation and board registry. Keep this metadata
limitation visible; a zero lint exit code is not a simulation pass.

All 126 ESP32 board endpoints across the overview and local diagrams were also
checked against the [official DevKitC V4 board definition](https://github.com/wokwi/wokwi-boards/blob/main/boards/esp32-devkit-c-v4/board.json),
including their GPIO/power/ground targets. Initial Phase 1 host checks passed
for ESP32-01, including JSON encoding, publish pacing and reconnects. Windows
Application Control blocked ESP32-02 and the final ESP32-01 rerun after additional
identity assertions (WinError 4551); a complete final host-suite pass is not
claimed. ESP32-03 host runtime tests were not run. The compile-only
command passed for all three host test programs without weakening security
settings. The compiled ESP32 ELF slot tables were also inspected: each has
exactly four entries with its assigned P1-P4, P5-P8 or P9-P12 identities and
the GPIO pairs listed above. This limit does not invalidate the successful ESP32 builds,
but it prevents claiming that all three host runtime suites passed.

## Runtime verification status and pending acceptance

**Wokwi runtime testing is pending by user choice.** No 12-slot simulation pass
is claimed. No Wokwi CLI token is configured in this session. To test later,
set an existing `WOKWI_CLI_TOKEN` securely outside Git and run each project with
the CLI, or start its selected configuration in VS Code. Never put the token
in source files, logs, documentation or chat.

For each board, run its real circuit/firmware and capture Serial output while:

1. All four distances are 100 cm: only that board's four slot IDs say VACANT.
2. Each slot individually changes to 10 cm: only that slot changes to OCCUPIED.
3. A reading is exactly 20 cm: OCCUPIED; above the threshold: VACANT.
4. In a disposable test copy, disconnect one ECHO line: that slot becomes UNKNOWN
   with ECHO_TIMEOUT. Do not modify the committed circuit for fault injection.
5. Restore the connection and confirm recovery, slot isolation and stable scans.

An unchanged 100 cm setting that yields UNKNOWN is a failed runtime test, not
a successful demo; investigate divider simulation and pin paths before proceeding.

## Preserved baseline

Tag `backup/4-slot-serial-baseline` points to commit `c1acc46`, which contains
the original four-slot circuit, compiled Serial firmware and old build config.
The tag was pushed before the twelve-slot edits. To inspect it safely in a
separate directory, run `git worktree add ../smart-parking-four-slot backup/4-slot-serial-baseline`.
Do not overwrite the current checkout to compare versions.
