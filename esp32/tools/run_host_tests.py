"""Compile/run production firmware with fake Arduino I/O for all three boards.

Uses an existing g++/clang++ or Visual Studio C++ installation. These are host
logic tests, not hardware or Wokwi simulation tests. Output stays in ignored tmp/.
"""

import argparse
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "tests/test_firmware.cpp"
FAKES = ROOT / "tests/fakes"
OUTPUT = ROOT.parent / "tmp/firmware-host-tests"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compile-only", action="store_true",
                        help="Compile all host tests without executing new binaries")
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    compiler = shutil.which("g++") or shutil.which("clang++")
    vcvars = None
    if not compiler and os.name == "nt":
        vswhere = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Microsoft Visual Studio/Installer/vswhere.exe"
        if vswhere.exists():
            install = subprocess.check_output(
                [str(vswhere), "-latest", "-products", "*", "-requires",
                 "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property",
                 "installationPath"], text=True).strip()
            if install:
                candidate = Path(install) / "VC/Auxiliary/Build/vcvars64.bat"
                if candidate.exists():
                    vcvars = candidate
    if not compiler and not vcvars:
        raise SystemExit("Host C++ compiler missing: install g++/clang++ or Visual Studio C++ Build Tools.")

    compiler_env = None
    msvc = None
    if vcvars:
        # cmd requires its own quoting, not subprocess's C-runtime argv quoting.
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        command = f'"{comspec}" /d /s /c ""{vcvars}" >nul && set"'
        settings = subprocess.check_output(command, text=True)
        compiler_env = dict(os.environ)
        for line in settings.splitlines():
            key, separator, value = line.partition("=")
            if separator and key:
                compiler_env[key] = value
        path = next(v for k, v in compiler_env.items() if k.upper() == "PATH")
        msvc = shutil.which("cl.exe", path=path)
        if not msvc:
            raise SystemExit("Visual Studio environment did not provide cl.exe")

    executables = []
    for board in range(1, 4):
        executable = OUTPUT / (f"esp32_{board:02d}" + (".exe" if os.name == "nt" else ""))
        if compiler:
            subprocess.run([compiler, "-std=c++17", "-Wall", "-Wextra", "-pedantic",
                            f"-DPARKING_BOARD_ID={board}", "-I", str(FAKES),
                            "-I", str(ROOT / "include"), str(TEST),
                            "-o", str(executable)], check=True, cwd=OUTPUT)
        else:
            subprocess.run([msvc, "/nologo", "/std:c++17", "/EHsc", "/W4",
                            f"/DPARKING_BOARD_ID={board}", f"/I{FAKES}",
                            f"/I{ROOT / 'include'}", str(TEST),
                            f"/Fe:{executable}", f"/Fo:{OUTPUT / (str(board) + '.obj')}"],
                           check=True, cwd=OUTPUT, env=compiler_env)
        executables.append(executable)
    print("All three host test programs compiled.", flush=True)
    if args.compile_only:
        print("Compile-only requested: no host test binaries executed.")
        return
    for executable in executables:
        try:
            subprocess.run([str(executable)], check=True)
        except OSError as error:
            if getattr(error, "winerror", None) == 4551:
                raise SystemExit(f"Windows Application Control blocked {executable.name}. "
                                 "Compilation is verified; remaining host runtime tests are not. "
                                 "Do not disable security policy to run these tests.") from error
            raise


if __name__ == "__main__":
    main()
