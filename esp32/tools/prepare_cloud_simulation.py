"""Prepare an ignored cloud simulation folder; never change local workspaces/circuits."""
import argparse
import hashlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def prepare(board):
    if board not in (1,2,3):
        raise ValueError('Board must be 1,2 or3')
    firmware = ROOT / f'esp32/.pio/build/esp32_{board:02d}_cloud'
    paths = [firmware/'firmware.bin', firmware/'firmware.elf']
    if not all(path.is_file() and path.stat().st_size for path in paths):
        raise ValueError('Build the assigned cloud target with existing tools first')
    source = ROOT / f'esp32/simulations/esp32-{board:02d}/diagram.json'
    diagram = source.read_bytes()
    target = ROOT / f'tmp/phase7-cloud-simulations/esp32-{board:02d}'
    target.mkdir(parents=True,exist_ok=False)  # Never overwrite an existing simulation.
    with (target/'diagram.json').open('xb') as output:
        output.write(diagram)
    relative = [Path(os.path.relpath(path,target)).as_posix() for path in paths]
    with (target/'wokwi.toml').open('x',encoding='utf-8') as output:
        output.write(f'[wokwi]\nversion = 1\nfirmware = "{relative[0]}"\nelf = "{relative[1]}"\n')
    assert hashlib.sha256((target/'diagram.json').read_bytes()).digest() == hashlib.sha256(diagram).digest()
    return target


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board',type=int,choices=(1,2,3),required=True)
    print(prepare(parser.parse_args().board))
