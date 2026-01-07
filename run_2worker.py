#!/usr/bin/env python3
"""
VE3 Tool - Multi Chrome Worker
Chạy nhiều Chrome song song để tăng tốc độ xử lý.

Usage:
    python run_2worker.py           # 2 Chrome (mặc định)
    python run_2worker.py 3         # 3 Chrome
    python run_2worker.py 4         # 4 Chrome

Cách chia công việc:
    - Chrome 1: scenes 1, 3, 5, ... + ảnh nv*/loc* (reference)
    - Chrome 2: scenes 2, 4, 6, ...
    - Chrome 3: scenes 3, 6, 9, ... (nếu có)
    - ...
"""

import sys
import os
import time
import subprocess
from pathlib import Path

TOOL_DIR = Path(__file__).parent


def run_multi_workers(num_workers: int = 2):
    """
    Chạy nhiều Chrome song song.

    Args:
        num_workers: Số lượng Chrome (2-5)
    """
    num_workers = max(2, min(5, num_workers))  # Clamp 2-5

    print(f"\n{'='*60}")
    print(f"  VE3 TOOL - PARALLEL MODE ({num_workers} CHROME)")
    print(f"{'='*60}")
    print(f"  🚀 Tự động mở {num_workers} Chrome song song")
    print(f"  ⏱️  Thời gian: giảm {int((1 - 1/num_workers) * 100)}%")
    print(f"{'='*60}\n")

    # Path to run_worker.py
    worker_script = TOOL_DIR / "run_worker.py"

    if not worker_script.exists():
        print(f"❌ Không tìm thấy: {worker_script}")
        return

    # Spawn worker processes
    processes = []

    for i in range(1, num_workers + 1):
        env = os.environ.copy()
        env['PARALLEL_CHROME'] = f'{i}/{num_workers}'

        # Description
        if i == 1:
            desc = f"scenes {i},{i+num_workers},{i+2*num_workers},... + nv*/loc*"
        else:
            desc = f"scenes {i},{i+num_workers},{i+2*num_workers},..."

        print(f"📌 Starting Chrome {i}/{num_workers} ({desc})")

        proc = subprocess.Popen(
            [sys.executable, str(worker_script)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        processes.append((proc, f"[C{i}]"))

        # Delay between Chrome starts
        if i < num_workers:
            time.sleep(2)

    print(f"\n{'='*60}")
    print(f"  ✅ {num_workers} Chrome đang chạy song song!")
    print(f"  📺 Logs hiển thị bên dưới")
    print(f"  ⏹️  Ctrl+C để dừng tất cả")
    print(f"{'='*60}\n")

    # Read outputs from all processes
    try:
        while True:
            # Check if all processes are done
            all_done = all(proc.poll() is not None for proc, _ in processes)
            if all_done:
                break

            # Read available output from each process
            for proc, label in processes:
                if proc.poll() is None or proc.stdout:
                    try:
                        line = proc.stdout.readline()
                        if line:
                            print(f"{label} {line.rstrip()}")
                    except:
                        pass

            time.sleep(0.05)

    except KeyboardInterrupt:
        print(f"\n\n⏹️ Stopping {num_workers} Chrome processes...")
        for proc, label in processes:
            try:
                proc.terminate()
            except:
                pass
        for proc, _ in processes:
            try:
                proc.wait(timeout=5)
            except:
                proc.kill()
        print("✅ Done!")


def main():
    # Get number of workers from command line
    num_workers = 2  # Default

    if len(sys.argv) >= 2:
        try:
            num_workers = int(sys.argv[1])
        except ValueError:
            print(f"Usage: python run_2worker.py [num_chrome]")
            print(f"  python run_2worker.py      # 2 Chrome")
            print(f"  python run_2worker.py 3    # 3 Chrome")
            print(f"  python run_2worker.py 4    # 4 Chrome")
            return

    run_multi_workers(num_workers)


if __name__ == "__main__":
    main()
