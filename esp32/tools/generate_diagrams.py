"""Generate a 12-slot overview and three independent single-ESP32 circuits.

Run from any directory. --check validates generated files without writing them.
The overview is not a runnable multi-microcontroller Wokwi simulation.
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_PINS = ((13, 34), (14, 35), (25, 32), (26, 33))


def group(board_number, offset=0):
    board = f"esp32_{board_number:02d}"
    parts = [{"type": "board-esp32-devkit-c-v4", "id": board,
              "top": 160, "left": offset, "attrs": {}}]
    wires = []
    for index, (trig, echo) in enumerate(LOCAL_PINS):
        slot = f"P{4 * (board_number - 1) + index + 1}"
        left = offset - 360 + 240 * index
        series, shunt = slot + "_echo_series", slot + "_echo_shunt"
        parts.extend([
            {"type": "wokwi-hc-sr04", "id": slot, "top": -180,
             "left": left, "attrs": {"distance": "100"}},
            {"type": "wokwi-resistor", "id": series, "top": -10,
             "left": left + 80, "rotate": 90, "attrs": {"value": "1000"}},
            {"type": "wokwi-resistor", "id": shunt, "top": 90,
             "left": left + 80, "rotate": 90, "attrs": {"value": "1800"}},
        ])
        wires.extend([
            [slot + ":VCC", board + ":5V", "red", ["v30", "*", "h-100"]],
            [slot + ":GND", board + ":GND.1", "black", ["v50", "*", "h-80"]],
            [slot + ":TRIG", f"{board}:{trig}", "green",
             [f"v{70 + 40 * index}", "*", "h-60"]],
            [slot + ":ECHO", series + ":1", "blue", ["v20"]],
            [series + ":2", f"{board}:{echo}", "blue", ["v20", "*", "h-40"]],
            [series + ":2", shunt + ":1", "blue", []],
            [shunt + ":2", board + ":GND.1", "black", ["v20", "*", "h-80"]],
        ])
    return parts, wires


def document(parts, wires):
    return {"version": 1, "author": "", "editor": "wokwi",
            "parts": parts, "connections": wires}


def outputs():
    parts, wires = [], []
    files = {}
    for board_number in range(1, 4):
        overview_parts, overview_wires = group(board_number, 1120 * (board_number - 1))
        parts.extend(overview_parts)
        wires.extend(overview_wires)
        local_parts, local_wires = group(board_number)
        board = f"esp32_{board_number:02d}"
        local_wires.extend([
            [board + ":TX", "$serialMonitor:RX", "", []],
            [board + ":RX", "$serialMonitor:TX", "", []],
        ])
        path = ROOT / "simulations" / f"esp32-{board_number:02d}" / "diagram.json"
        files[path] = document(local_parts, local_wires)
    files[ROOT / "diagram.json"] = document(parts, wires)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path, content in outputs().items():
        if args.check:
            if not path.exists() or json.loads(path.read_text(encoding="utf-8")) != content:
                raise SystemExit(f"Circuit has drifted; regenerate: {path}")
            print(f"MATCH {path.relative_to(ROOT)}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
            print(f"WROTE {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
