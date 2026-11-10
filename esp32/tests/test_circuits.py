"""Independent netlist/ownership checks for overview and Wokwi configurations."""

import json
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINS = ((13, 34), (14, 35), (25, 32), (26, 33))


class CircuitTests(unittest.TestCase):
    def check_diagram(self, path, board_numbers, serial=False):
        diagram = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(diagram["version"], 1)
        parts = {part["id"]: part for part in diagram["parts"]}
        self.assertEqual(len(parts), 13 * len(board_numbers))
        self.assertEqual(len(parts), len(diagram["parts"]))
        expected = set()
        parent = {}

        def find(x):
            parent.setdefault(x, x)
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        for number in board_numbers:
            board = f"esp32_{number:02d}"
            self.assertEqual(parts[board]["type"], "board-esp32-devkit-c-v4")
            for local, (trig, echo) in enumerate(PINS):
                slot = f"P{4 * (number - 1) + local + 1}"
                series, shunt = slot + "_echo_series", slot + "_echo_shunt"
                self.assertEqual(parts[slot]["type"], "wokwi-hc-sr04")
                for resistor, value in ((series, "1000"), (shunt, "1800")):
                    self.assertEqual(parts[resistor]["type"], "wokwi-resistor")
                    self.assertEqual(parts[resistor]["attrs"]["value"], value)
                pairs = [
                    (slot + ":VCC", board + ":5V"),
                    (slot + ":GND", board + ":GND.1"),
                    (slot + ":TRIG", f"{board}:{trig}"),
                    (slot + ":ECHO", series + ":1"),
                    (series + ":2", f"{board}:{echo}"),
                    (series + ":2", shunt + ":1"),
                    (shunt + ":2", board + ":GND.1"),
                ]
                expected.update(frozenset(pair) for pair in pairs)
            if serial:
                expected.update((frozenset((board + ":TX", "$serialMonitor:RX")),
                                 frozenset((board + ":RX", "$serialMonitor:TX"))))

        connections = diagram["connections"]
        self.assertEqual(len(connections), len(expected))
        self.assertEqual({frozenset(c[:2]) for c in connections}, expected)
        for wire in connections:
            self.assertEqual(len(wire), 4)
            self.assertIsInstance(wire[2], str)
            self.assertIsInstance(wire[3], list)
            parent[find(wire[0])] = find(wire[1])

        midpoints = []
        grounds = []
        for number in board_numbers:
            board = f"esp32_{number:02d}"
            ground, supply = find(board + ":GND.1"), find(board + ":5V")
            self.assertNotEqual(ground, supply)
            grounds.append(ground)
            for local, (_, echo) in enumerate(PINS):
                midpoint = find(f"{board}:{echo}")
                midpoints.append(midpoint)
                self.assertNotIn(midpoint, (ground, supply))
                slot = f"P{4 * (number - 1) + local + 1}"
                self.assertNotEqual(find(slot + ":ECHO"), midpoint)
        self.assertEqual(len(set(midpoints)), 4 * len(board_numbers))
        self.assertEqual(len(set(grounds)), len(board_numbers))

    def test_twelve_slot_overview(self):
        self.check_diagram(ROOT / "diagram.json", (1, 2, 3))

    def test_independent_simulations(self):
        for number in range(1, 4):
            with self.subTest(board=number):
                folder = ROOT / "simulations" / f"esp32-{number:02d}"
                self.check_diagram(folder / "diagram.json", (number,), serial=True)
                config = tomllib.loads((folder / "wokwi.toml").read_text())
                self.assertEqual(config["wokwi"]["version"], 1)
                for field, suffix in (("firmware", "bin"), ("elf", "elf")):
                    expected = ROOT / ".pio/build" / f"esp32_{number:02d}" / f"firmware.{suffix}"
                    self.assertEqual((folder / config["wokwi"][field]).resolve(), expected.resolve())

    def test_generated_circuits_have_not_drifted(self):
        subprocess.run([sys.executable, str(ROOT / "tools/generate_diagrams.py"), "--check"],
                       check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
