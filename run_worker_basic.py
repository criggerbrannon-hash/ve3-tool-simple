#!/usr/bin/env python3
"""
VE3 Tool - Worker BASIC Mode (PIC + VIDEO parallel)
===================================================
Chay song song:
- run_worker_pic_basic: Tao anh cho tat ca segments (segment-based)
- run_worker_video_basic: Tao video chi cho SEGMENT DAU TIEN (tuan thu 8s)

Usage:
    python run_worker_basic.py                     (quet va xu ly tu dong)
    python run_worker_basic.py AR47-0028           (chay 1 project cu the)
    python run_worker_basic.py --mode pic          (chi chay pic_basic)
    python run_worker_basic.py --mode video        (chi chay video_basic)
"""

import sys
import os
import time
import threading
import subprocess
from pathlib import Path

# Add current directory to path
TOOL_DIR = Path(__file__).parent
sys.path.insert(0, str(TOOL_DIR))

# Import shared functions
from run_worker import (
    detect_auto_path,
    get_channel_from_folder,
    SCAN_INTERVAL,
)

AUTO_PATH = detect_auto_path()
WORKER_CHANNEL = get_channel_from_folder()


def run_parallel_basic(project: str = None):
    """
    Run PIC_BASIC and VIDEO_BASIC workers in parallel.
    - PIC_BASIC: Creates images for all segments (segment-based prompts)
    - VIDEO_BASIC: Creates videos for FIRST SEGMENT only (8s rule)
    """
    print(f"\n{'='*60}")
    print(f"  VE3 TOOL - BASIC PARALLEL MODE")
    print(f"{'='*60}")
    print(f"  PIC_BASIC:   Images for all segments (main)")
    print(f"  VIDEO_BASIC: Videos for first segment only (background)")
    print(f"  Channel:     {WORKER_CHANNEL or 'ALL'}")
    print(f"{'='*60}")

    # Start VIDEO_BASIC worker in background process
    video_cmd = [sys.executable, str(TOOL_DIR / "run_worker_video_basic.py")]
    if project:
        video_cmd.append(project)

    print(f"\n[BASIC] Starting VIDEO_BASIC worker in background...")
    video_process = subprocess.Popen(
        video_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Thread to print VIDEO output
    def print_video_output():
        try:
            for line in video_process.stdout:
                print(f"[VIDEO_BASIC] {line.rstrip()}")
        except:
            pass

    video_thread = threading.Thread(target=print_video_output, daemon=True)
    video_thread.start()

    # Run PIC_BASIC worker in main thread
    print(f"\n[BASIC] Starting PIC_BASIC worker (main)...")

    try:
        from run_worker_pic_basic import run_scan_loop as pic_scan_loop, process_project_pic_basic

        if project:
            process_project_pic_basic(project)
        else:
            pic_scan_loop()

    except KeyboardInterrupt:
        print("\n\n[BASIC] Stopped by user.")

    finally:
        # Terminate VIDEO worker when PIC is done
        print(f"\n[BASIC] PIC_BASIC finished. Stopping VIDEO_BASIC...")
        try:
            video_process.terminate()
            video_process.wait(timeout=5)
        except:
            video_process.kill()

    print(f"[BASIC] Done!")


def run_pic_basic_mode(project: str = None):
    """Run only PIC_BASIC mode."""
    from run_worker_pic_basic import run_scan_loop, process_project_pic_basic

    if project:
        process_project_pic_basic(project)
    else:
        run_scan_loop()


def run_video_basic_mode(project: str = None):
    """Run only VIDEO_BASIC mode."""
    from run_worker_video_basic import run_scan_loop, process_project_video_basic

    if project:
        process_project_video_basic(project)
    else:
        run_scan_loop()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='VE3 Worker BASIC - PIC + VIDEO parallel')
    parser.add_argument('project', nargs='?', default=None, help='Project code to process')
    parser.add_argument('--mode', choices=['all', 'pic', 'video'], default='all',
                        help='Mode: all (parallel, default), pic (pic_basic only), video (video_basic only)')
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  VE3 TOOL - WORKER BASIC")
    print(f"{'='*60}")
    print(f"  Mode:    {args.mode.upper()}")
    print(f"  Project: {args.project or 'AUTO SCAN'}")
    print(f"{'='*60}")

    if args.mode == 'pic':
        run_pic_basic_mode(args.project)

    elif args.mode == 'video':
        run_video_basic_mode(args.project)

    else:  # 'all' - parallel mode (default)
        run_parallel_basic(args.project)


if __name__ == "__main__":
    main()
