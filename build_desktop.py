#!/usr/bin/env python3
"""
Desktop Build & Packaging Script for Zeno Desktop AI Assistant.
Produces a standalone single-file or directory executable using PyInstaller
for Windows (.exe), macOS (.app), and Linux.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ZENO_DIR = BASE_DIR / "zeno" if (BASE_DIR / "zeno").exists() else BASE_DIR

def check_requirements() -> bool:
    print("[*] Checking build dependencies...")
    try:
        import PyInstaller
        print(f"[+] PyInstaller found: version {PyInstaller.__version__}")
        return True
    except ImportError:
        print("[-] PyInstaller is not installed in the current Python environment.")
        print("    Run: pip install pyinstaller")
        return False

def build_executable() -> int:
    os_name = platform.system().lower()
    print(f"[*] Building Zeno Desktop for {platform.system()} ({platform.machine()})...")

    main_script = ZENO_DIR / "main.py"
    if not main_script.exists():
        print(f"[-] Cannot locate main.py at {main_script}")
        return 1

    dist_web = BASE_DIR / "dist"
    if not (dist_web / "index.html").is_file() or not (dist_web / "assets").is_dir():
        print("[-] Frontend build not found. Run `npm run build` before packaging.")
        return 1

    data_separator = ";" if os_name == "windows" else ":"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=Zeno",
        f"--specpath={BASE_DIR / 'build'}",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        f"--add-data={ZENO_DIR / 'resources'}{data_separator}zeno/resources",
        "--collect-all=webview",
        "--copy-metadata=pywebview",
        str(main_script),
    ]
    for frontend_entry in sorted(dist_web.iterdir()):
        if frontend_entry.is_dir() and frontend_entry.name.lower() == "zeno":
            continue
        destination = f"dist/{frontend_entry.name}" if frontend_entry.is_dir() else "dist"
        cmd.append(f"--add-data={frontend_entry}{data_separator}{destination}")

    print(f"[*] Executing command:\n    {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True, cwd=BASE_DIR)
        print("\n==========================================")
        print("  Zeno Desktop Executable Build Success! ")
        print("==========================================")
        print("You can find your packaged executable in:")
        print(f"  {BASE_DIR / 'dist' / 'Zeno'}")
        if os_name == "windows":
            print(f"Executable: {BASE_DIR / 'dist' / 'Zeno' / 'Zeno.exe'}")
        elif os_name == "darwin":
            print(f"Executable: {BASE_DIR / 'dist' / 'Zeno' / 'Zeno.app'}")
        else:
            print(f"Executable: {BASE_DIR / 'dist' / 'Zeno' / 'Zeno'}")
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"[-] PyInstaller failed with exit code {exc.returncode}")
        return exc.returncode
    except Exception as exc:
        print(f"[-] Build error: {exc}")
        return 1

if __name__ == "__main__":
    if check_requirements():
        sys.exit(build_executable())
    else:
        print("[-] Please install PyInstaller and try again.")
        sys.exit(1)
