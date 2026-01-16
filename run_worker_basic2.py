#!/usr/bin/env python3
"""
VE3 Tool - Worker BASIC 2 Mode (2-Chrome PIC + VIDEO + Copy)
=============================================================
Quy trình xử lý hoàn chỉnh cho 1 project:
1. run_worker_pic_basic_2: Tạo ảnh với 2 Chrome song song (nhanh hơn)
2. run_worker_video_basic: Tạo video cho segment đầu tiên
3. Copy về máy chủ (VISUAL folder)

Sau khi hoàn thành, project sẽ được chuyển từ PROJECTS -> VISUAL.

Usage:
    python run_worker_basic2.py                     (quét và xử lý tự động)
    python run_worker_basic2.py AR47-0028           (chạy 1 project cụ thể)
    python run_worker_basic2.py --mode pic          (chỉ chạy tạo ảnh)
    python run_worker_basic2.py --mode video        (chỉ chạy tạo video)
"""

import sys
import os
import time
import subprocess
from pathlib import Path

# Add current directory to path
TOOL_DIR = Path(__file__).parent
sys.path.insert(0, str(TOOL_DIR))

# Import shared functions
from run_worker import (
    detect_auto_path,
    get_channel_from_folder,
    matches_channel,
    is_project_complete_on_master,
    has_excel_with_prompts,
    copy_from_master,
    copy_to_visual,
    delete_local_project,
    SCAN_INTERVAL,
)

# Import from run_worker_pic_basic_2
from run_worker_pic_basic_2 import (
    process_project_pic_basic_2,
    load_chrome_paths,
)

# Import from run_worker_pic_basic for local complete check
from run_worker_pic_basic import (
    is_local_pic_complete,
)

# Detect paths
AUTO_PATH = detect_auto_path()
if AUTO_PATH:
    MASTER_PROJECTS = AUTO_PATH / "ve3-tool-simple" / "PROJECTS"
    MASTER_VISUAL = AUTO_PATH / "VISUAL"
else:
    MASTER_PROJECTS = Path(r"\\tsclient\D\AUTO\ve3-tool-simple\PROJECTS")
    MASTER_VISUAL = Path(r"\\tsclient\D\AUTO\VISUAL")

LOCAL_PROJECTS = TOOL_DIR / "PROJECTS"
WORKER_CHANNEL = get_channel_from_folder()


def is_local_video_complete(local_dir: Path, code: str) -> bool:
    """Check if video generation is complete for first segment."""
    try:
        from modules.excel_manager import PromptWorkbook

        excel_path = local_dir / f"{code}_prompts.xlsx"
        img_dir = local_dir / "img"

        if not excel_path.exists() or not img_dir.exists():
            return False

        # Load Excel to get first segment scenes
        wb = PromptWorkbook(str(excel_path))
        wb.load_or_create()

        # Get first segment scenes
        segments = wb.get_story_segments()
        if not segments:
            return True  # No segments = consider done

        first_segment = min(segments, key=lambda s: s.get('srt_range_start', 999999))
        seg_start = first_segment.get('srt_range_start', 1)
        seg_end = first_segment.get('srt_range_end', seg_start + 10)

        scenes = wb.get_scenes()
        first_segment_scenes = []
        for scene in scenes:
            scene_srt_start = getattr(scene, 'srt_start', 0) or 0
            if seg_start <= scene_srt_start <= seg_end:
                first_segment_scenes.append(scene)

        if not first_segment_scenes:
            return True  # No scenes in first segment = done

        # Check if all first segment scenes have videos
        for scene in first_segment_scenes:
            video_path = img_dir / f"{scene.scene_id}.mp4"
            if not video_path.exists():
                return False

        return True

    except Exception as e:
        print(f"  Error checking video complete: {e}")
        return False


def process_project_complete(code: str, callback=None) -> bool:
    """
    Process a single project through complete workflow:
    1. Create images (2 Chrome parallel)
    2. Create videos
    3. Copy to VISUAL (master)
    """
    def log(msg, level="INFO"):
        if callback:
            callback(msg, level)
        else:
            print(msg)

    log(f"\n{'='*70}")
    log(f"  BASIC2 WORKFLOW: {code}")
    log(f"  Step 1: Images (2-Chrome) → Step 2: Videos → Step 3: Copy to VISUAL")
    log(f"{'='*70}")

    local_dir = LOCAL_PROJECTS / code

    # ========== STEP 1: CREATE IMAGES (2 Chrome) ==========
    log(f"\n[STEP 1/3] Creating images with 2 Chrome...")

    if is_local_pic_complete(local_dir, code):
        log(f"  Images already complete, skipping...")
    else:
        success = process_project_pic_basic_2(code, callback)
        if not success:
            log(f"  Image creation failed!", "ERROR")
            return False

        if not is_local_pic_complete(local_dir, code):
            log(f"  Images incomplete after processing!", "WARN")
            # Continue anyway - video might work for available images

    # ========== STEP 2: CREATE VIDEOS ==========
    log(f"\n[STEP 2/3] Creating videos for first segment...")

    if is_local_video_complete(local_dir, code):
        log(f"  Videos already complete, skipping...")
    else:
        try:
            from run_worker_video_basic import process_project_video_basic
            success = process_project_video_basic(code, callback)
            if not success:
                log(f"  Video creation failed or incomplete", "WARN")
                # Continue to copy - partial completion is OK
        except Exception as e:
            log(f"  Video error: {e}", "ERROR")
            # Continue to copy anyway

    # ========== STEP 3: COPY TO VISUAL ==========
    log(f"\n[STEP 3/3] Copying to VISUAL folder...")

    try:
        if copy_to_visual(code):
            log(f"  Copied to VISUAL!")

            # Delete local project to save space
            log(f"  Cleaning up local project...")
            delete_local_project(code)
            log(f"  Local project deleted")

            log(f"\n{'='*70}")
            log(f"  COMPLETE: {code}")
            log(f"{'='*70}")
            return True
        else:
            log(f"  Failed to copy to VISUAL", "ERROR")
            return False

    except Exception as e:
        log(f"  Copy error: {e}", "ERROR")
        return False


def scan_pending_projects() -> list:
    """Scan for projects that need processing."""
    pending = []

    # Scan local projects first (incomplete)
    if LOCAL_PROJECTS.exists():
        for item in LOCAL_PROJECTS.iterdir():
            if not item.is_dir():
                continue

            code = item.name
            if not matches_channel(code):
                continue

            if is_project_complete_on_master(code):
                continue

            # Has Excel or SRT
            if has_excel_with_prompts(item, code) or (item / f"{code}.srt").exists():
                print(f"    - {code}: local incomplete")
                pending.append(code)

    # Scan master projects
    if MASTER_PROJECTS.exists():
        for item in MASTER_PROJECTS.iterdir():
            if not item.is_dir():
                continue

            code = item.name
            if not matches_channel(code):
                continue

            if is_project_complete_on_master(code):
                continue

            if code in pending:
                continue  # Already added from local

            if has_excel_with_prompts(item, code) or (item / f"{code}.srt").exists():
                print(f"    - {code}: master ready")
                pending.append(code)

    return sorted(pending)


def run_scan_loop():
    """Run continuous scan loop for complete workflow."""
    chrome1, chrome2 = load_chrome_paths()

    print(f"\n{'='*70}")
    print(f"  VE3 TOOL - WORKER BASIC2 (Complete Workflow)")
    print(f"{'='*70}")
    print(f"  Worker folder:   {TOOL_DIR.parent.name}")
    print(f"  Channel filter:  {WORKER_CHANNEL or 'ALL'}")
    print(f"  Chrome 1:        {chrome1 or 'NOT CONFIGURED'}")
    print(f"  Chrome 2:        {chrome2 or 'NOT CONFIGURED'}")
    print(f"{'='*70}")
    print(f"  Workflow: Images (2-Chrome) → Videos → Copy to VISUAL")
    print(f"{'='*70}")

    cycle = 0

    while True:
        cycle += 1
        print(f"\n[BASIC2 CYCLE {cycle}] Scanning for pending projects...")

        pending = scan_pending_projects()

        if not pending:
            print(f"  No pending projects")
            print(f"\n  Waiting {SCAN_INTERVAL}s... (Ctrl+C to stop)")
            try:
                time.sleep(SCAN_INTERVAL)
            except KeyboardInterrupt:
                print("\n\nStopped by user.")
                break
        else:
            print(f"  Found: {len(pending)} pending projects")

            for code in pending:
                try:
                    success = process_project_complete(code)
                    if not success:
                        print(f"  [SKIP] {code}, moving to next...")
                        continue
                except KeyboardInterrupt:
                    print("\n\nStopped by user.")
                    return
                except Exception as e:
                    print(f"  [ERROR] {code}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue

            print(f"\n  Processed all pending projects!")
            print(f"  Waiting {SCAN_INTERVAL}s... (Ctrl+C to stop)")
            try:
                time.sleep(SCAN_INTERVAL)
            except KeyboardInterrupt:
                print("\n\nStopped by user.")
                break


def run_pic_only(project: str = None):
    """Run only image creation (2 Chrome mode)."""
    from run_worker_pic_basic_2 import run_scan_loop as pic_scan_loop

    if project:
        process_project_pic_basic_2(project)
    else:
        pic_scan_loop()


def run_video_only(project: str = None):
    """Run only video creation."""
    from run_worker_video_basic import run_scan_loop as video_scan_loop, process_project_video_basic

    if project:
        process_project_video_basic(project)
    else:
        video_scan_loop()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='VE3 Worker BASIC2 - Complete Workflow')
    parser.add_argument('project', nargs='?', default=None, help='Project code to process')
    parser.add_argument('--mode', choices=['all', 'pic', 'video'], default='all',
                        help='Mode: all (complete workflow), pic (images only), video (videos only)')
    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"  VE3 TOOL - WORKER BASIC2")
    print(f"{'='*70}")
    print(f"  Mode:    {args.mode.upper()}")
    print(f"  Project: {args.project or 'AUTO SCAN'}")
    print(f"{'='*70}")

    if args.mode == 'pic':
        run_pic_only(args.project)

    elif args.mode == 'video':
        run_video_only(args.project)

    else:  # 'all' - complete workflow (default)
        if args.project:
            process_project_complete(args.project)
        else:
            run_scan_loop()


if __name__ == "__main__":
    main()
