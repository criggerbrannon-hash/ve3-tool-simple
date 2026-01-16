#!/usr/bin/env python3
"""
VE3 Tool - Worker PIC BASIC 2 Chrome Mode
==========================================
Chạy 2 Chrome SONG SONG - 2 CMD độc lập.

Usage:
    python run_worker_pic_basic_2.py [project_code]
"""

import sys
import os
import subprocess
from pathlib import Path

TOOL_DIR = Path(__file__).parent


def load_chrome_paths():
    import yaml
    settings_path = TOOL_DIR / "config" / "settings.yaml"
    if not settings_path.exists():
        return None, None
    with open(settings_path, 'r', encoding='utf-8') as f:
        settings = yaml.safe_load(f) or {}

    chrome1 = settings.get('chrome_portable', '')
    chrome2 = settings.get('chrome_portable_2', '')

    if not chrome1:
        p = TOOL_DIR / "GoogleChromePortable" / "GoogleChromePortable.exe"
        if p.exists():
            chrome1 = str(p)
    if not chrome2:
        p = TOOL_DIR / "GoogleChromePortable - Copy" / "GoogleChromePortable.exe"
        if p.exists():
            chrome2 = str(p)

    return chrome1, chrome2


def main():
    project = sys.argv[1] if len(sys.argv) > 1 else None
    chrome1, chrome2 = load_chrome_paths()

    print(f"\n{'='*60}")
    print(f"  2-CHROME MODE")
    print(f"{'='*60}")
    print(f"  Chrome 1: {chrome1}")
    print(f"  Chrome 2: {chrome2}")
    print(f"{'='*60}")

    if not chrome1 or not chrome2:
        print("ERROR: Need both Chrome 1 and Chrome 2!")
        return

    # Build commands
    script = str(TOOL_DIR / "run_worker_pic_basic.py")
    cmd1 = f'set CHROME_WORKER_ID=0&& set CHROME_TOTAL_WORKERS=2&& set CHROME_PORTABLE={chrome1}&& python "{script}"'
    cmd2 = f'set CHROME_WORKER_ID=1&& set CHROME_TOTAL_WORKERS=2&& set CHROME_PORTABLE={chrome2}&& set CHROME_PORT_OFFSET=100&& python "{script}"'

    if project:
        cmd1 += f' {project}'
        cmd2 += f' {project}'

    print(f"\n[CMD 1] {cmd1[:80]}...")
    print(f"[CMD 2] {cmd2[:80]}...")
    print(f"\nMở 2 CMD windows và chạy:")
    print(f"\n--- CMD 1 (Chrome 1) ---")
    print(cmd1)
    print(f"\n--- CMD 2 (Chrome 2) ---")
    print(cmd2)

    # Mở 2 CMD windows
    subprocess.Popen(f'start cmd /k "{cmd1}"', shell=True)
    subprocess.Popen(f'start cmd /k "{cmd2}"', shell=True)

    print(f"\n2 CMD windows đã mở!")


if __name__ == "__main__":
    main()
