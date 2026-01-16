#!/usr/bin/env python3
"""
VE3 Tool - Worker PIC BASIC 2 Chrome Mode
==========================================
Chay 2 Chrome SONG SONG de tao anh nhanh hon:
- Chrome 1: Characters + 50% scenes
- Chrome 2: Locations + 50% scenes

FLOW:
1. Phase 1 (song song): Chrome1 tao characters, Chrome2 tao locations
2. Phase 2 (song song): Ca 2 Chrome chia nhau tao scenes (50/50)

Usage:
    python run_worker_pic_basic_2.py                     (quet va xu ly tu dong)
    python run_worker_pic_basic_2.py AR47-0028           (chay 1 project cu the)
"""

import sys
import os
import time
import threading
from pathlib import Path
from typing import List, Dict, Callable

# Add current directory to path
TOOL_DIR = Path(__file__).parent
sys.path.insert(0, str(TOOL_DIR))

# Import tu run_worker (dung chung logic)
from run_worker import (
    detect_auto_path,
    POSSIBLE_AUTO_PATHS,
    get_channel_from_folder,
    matches_channel,
    is_project_complete_on_master,
    has_excel_with_prompts,
    copy_from_master,
    SCAN_INTERVAL,
)

# Import tu run_worker_pic_basic
from run_worker_pic_basic import (
    create_excel_with_api_basic,
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


class DualChromeImageGenerator:
    """
    Tao anh bang 2 Chrome song song.

    Phase 1: Chrome1 tao characters, Chrome2 tao locations (SONG SONG)
    Phase 2: Ca 2 chia nhau tao scenes (SONG SONG)

    QUAN TRONG:
    - Dung 1 SmartEngine de quan ly tokens
    - Lay 2 profiles khac nhau cho 2 threads
    - Moi thread dung 1 profile rieng, khong conflict
    """

    def __init__(self, callback: Callable = None):
        self.callback = callback
        self.stop_flag = False
        self._lock = threading.Lock()

        # Shared engine for token management
        self._shared_engine = None

        # Results
        self.results = {
            "chrome1": {"success": 0, "failed": 0},
            "chrome2": {"success": 0, "failed": 0},
        }

    def log(self, msg: str, level: str = "INFO"):
        """Log message."""
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        full_msg = f"[{ts}] {msg}"

        if self.callback:
            self.callback(full_msg, level)
        else:
            print(full_msg)

    def _get_shared_engine(self) -> 'SmartEngine':
        """Get or create shared SmartEngine for token management."""
        if self._shared_engine is None:
            from modules.smart_engine import SmartEngine
            self._shared_engine = SmartEngine(
                worker_id=0,
                total_workers=1
            )
        return self._shared_engine

    def _get_two_profiles(self) -> tuple:
        """
        Get 2 separate profiles with valid tokens.

        Returns:
            (profile1, profile2) or (None, None) if not enough profiles
        """
        engine = self._get_shared_engine()

        # Get all tokens first
        self.log("Getting tokens for 2 Chrome instances...")
        token_count = engine.get_all_tokens()

        if token_count < 1:
            self.log("No tokens available!", "ERROR")
            return None, None

        # Collect profiles with valid tokens
        all_accounts = engine.headless_accounts + engine.profiles
        valid_profiles = [p for p in all_accounts if p.token and p.status != 'exhausted']

        if len(valid_profiles) < 1:
            self.log("No valid profiles!", "ERROR")
            return None, None

        # Assign profiles
        profile1 = valid_profiles[0]
        profile2 = valid_profiles[1] if len(valid_profiles) > 1 else valid_profiles[0]

        self.log(f"Chrome1 profile: {Path(profile1.value).name}")
        self.log(f"Chrome2 profile: {Path(profile2.value).name}")

        if profile1 == profile2:
            self.log("WARNING: Both Chrome using same profile (only 1 available)", "WARN")

        return profile1, profile2

    def _split_prompts(self, all_prompts: List[Dict]) -> tuple:
        """
        Split prompts into 2 lists for 2 Chrome instances.

        Returns:
            (chrome1_prompts, chrome2_prompts)
            - Chrome 1: Characters (nv*) + odd scenes (s001, s003, ...)
            - Chrome 2: Locations (loc*) + even scenes (s002, s004, ...)
        """
        characters = []
        locations = []
        scenes = []

        for p in all_prompts:
            pid = p.get('id', '')
            if pid.startswith('nv'):
                characters.append(p)
            elif pid.startswith('loc'):
                locations.append(p)
            else:
                scenes.append(p)

        # Sort scenes by ID for consistent splitting
        scenes.sort(key=lambda x: x.get('id', ''))

        # Split scenes: odd to Chrome1, even to Chrome2
        scenes_chrome1 = scenes[::2]   # 0, 2, 4, ... (s001, s003, ...)
        scenes_chrome2 = scenes[1::2]  # 1, 3, 5, ... (s002, s004, ...)

        chrome1_prompts = characters + scenes_chrome1
        chrome2_prompts = locations + scenes_chrome2

        self.log(f"Split: Chrome1={len(chrome1_prompts)} (nv:{len(characters)}, scenes:{len(scenes_chrome1)})")
        self.log(f"Split: Chrome2={len(chrome2_prompts)} (loc:{len(locations)}, scenes:{len(scenes_chrome2)})")

        return chrome1_prompts, chrome2_prompts

    def _worker_thread(self, chrome_id: int, prompts: List[Dict], proj_dir: Path, profile):
        """
        Worker thread for 1 Chrome instance.
        Creates images sequentially within this thread.

        Args:
            chrome_id: 0 or 1
            prompts: List of prompts for this thread
            proj_dir: Project directory
            profile: Profile with valid token to use
        """
        thread_name = f"Chrome{chrome_id + 1}"

        try:
            self.log(f"[{thread_name}] Starting with {len(prompts)} images...")

            # Use shared engine
            engine = self._get_shared_engine()

            # Use the assigned profile
            active_profile = profile
            self.log(f"[{thread_name}] Using profile: {Path(active_profile.value).name}")

            # Process prompts sequentially
            success = 0
            failed = 0

            for i, prompt_data in enumerate(prompts):
                if self.stop_flag:
                    break

                pid = prompt_data.get('id', '')
                output_path = prompt_data.get('output_path', '')

                # Skip if exists
                if Path(output_path).exists():
                    self.log(f"[{thread_name}] [{pid}] Already exists, skip")
                    success += 1
                    continue

                self.log(f"[{thread_name}] [{i+1}/{len(prompts)}] Creating {pid}...")

                # Check token valid - if expired, try to refresh
                if not active_profile.token:
                    self.log(f"[{thread_name}] Token expired, refreshing...")
                    with self._lock:
                        engine.get_all_tokens()

                    if not active_profile.token:
                        self.log(f"[{thread_name}] Cannot refresh token!", "ERROR")
                        failed += len(prompts) - i
                        break

                # Generate image
                ok, token_expired = engine.generate_single_image(prompt_data, active_profile)

                if token_expired:
                    active_profile.token = ""
                    self.log(f"[{thread_name}] Token expired during {pid}", "WARN")

                if ok:
                    success += 1
                    self.log(f"[{thread_name}] [{pid}] OK!", "OK")
                else:
                    failed += 1
                    self.log(f"[{thread_name}] [{pid}] FAILED", "ERROR")

                # Small delay
                time.sleep(0.3)

            # Update results
            with self._lock:
                self.results[f"chrome{chrome_id + 1}"] = {
                    "success": success,
                    "failed": failed,
                }

            self.log(f"[{thread_name}] Done: {success} OK, {failed} FAILED")

        except Exception as e:
            self.log(f"[{thread_name}] Exception: {e}", "ERROR")
            import traceback
            traceback.print_exc()

    def generate_parallel(self, all_prompts: List[Dict], proj_dir: Path) -> Dict:
        """
        Generate images using 2 Chrome instances in parallel.

        Args:
            all_prompts: List of prompt dicts with id, prompt, output_path, etc.
            proj_dir: Project directory

        Returns:
            Dict with success/failed counts
        """
        self.log(f"\n{'='*60}")
        self.log(f"  2-CHROME PARALLEL IMAGE GENERATION")
        self.log(f"  Total images: {len(all_prompts)}")
        self.log(f"{'='*60}")

        if not all_prompts:
            return {"success": 0, "failed": 0}

        # Get 2 profiles with valid tokens
        profile1, profile2 = self._get_two_profiles()
        if not profile1:
            self.log("Cannot get profiles for 2 Chrome!", "ERROR")
            return {"success": 0, "failed": len(all_prompts)}

        # Split prompts between 2 Chrome instances
        chrome1_prompts, chrome2_prompts = self._split_prompts(all_prompts)

        # Create and start threads with assigned profiles
        thread1 = threading.Thread(
            target=self._worker_thread,
            args=(0, chrome1_prompts, proj_dir, profile1),
            name="Chrome1"
        )
        thread2 = threading.Thread(
            target=self._worker_thread,
            args=(1, chrome2_prompts, proj_dir, profile2),
            name="Chrome2"
        )

        self.log(f"\nStarting 2 Chrome threads...")

        thread1.start()
        time.sleep(1)  # Small delay to avoid Chrome conflicts
        thread2.start()

        # Wait for both to finish
        thread1.join()
        thread2.join()

        # Combine results
        total_success = self.results["chrome1"]["success"] + self.results["chrome2"]["success"]
        total_failed = self.results["chrome1"]["failed"] + self.results["chrome2"]["failed"]

        self.log(f"\n{'='*60}")
        self.log(f"  FINAL RESULTS:")
        self.log(f"  Chrome1: {self.results['chrome1']['success']} OK, {self.results['chrome1']['failed']} FAILED")
        self.log(f"  Chrome2: {self.results['chrome2']['success']} OK, {self.results['chrome2']['failed']} FAILED")
        self.log(f"  TOTAL:   {total_success} OK, {total_failed} FAILED")
        self.log(f"{'='*60}")

        return {
            "success": total_success,
            "failed": total_failed,
            "chrome1": self.results["chrome1"],
            "chrome2": self.results["chrome2"],
        }


def get_prompts_from_excel(excel_path: Path, proj_dir: Path) -> List[Dict]:
    """
    Read prompts from Excel and prepare prompt list for image generation.
    """
    from modules.excel_manager import PromptWorkbook

    prompts = []
    img_dir = proj_dir / "img"
    img_dir.mkdir(exist_ok=True)
    nv_dir = proj_dir / "nv"
    nv_dir.mkdir(exist_ok=True)

    wb = PromptWorkbook(str(excel_path))

    # Get characters
    characters = wb.get_characters()
    for char in characters:
        if char.img_prompt:
            char_id = char.id or f"nv{len(prompts) + 1}"
            prompts.append({
                "id": char_id,
                "prompt": char.img_prompt,
                "output_path": str(nv_dir / f"{char_id}.png"),
                "type": "character",
            })

    # Get locations
    locations = wb.get_locations()
    for loc in locations:
        if loc.img_prompt:
            loc_id = loc.id or f"loc{len(prompts) + 1}"
            prompts.append({
                "id": loc_id,
                "prompt": loc.img_prompt,
                "output_path": str(nv_dir / f"{loc_id}.png"),
                "type": "location",
            })

    # Get scenes
    scenes = wb.get_scenes()
    for scene in scenes:
        if scene.img_prompt:
            scene_id = scene.id or f"s{len(prompts) + 1:03d}"

            # Prepare reference files
            reference_files = scene.reference_files or ""
            nv_path = str(nv_dir) if (nv_dir / "nvc.png").exists() or any(nv_dir.glob("nv*.png")) else ""

            prompts.append({
                "id": scene_id,
                "prompt": scene.img_prompt,
                "output_path": str(img_dir / f"{scene_id}.png"),
                "video_prompt": scene.video_prompt or "",
                "reference_files": reference_files,
                "nv_path": nv_path,
                "type": "scene",
            })

    return prompts


def process_project_pic_basic_2(code: str, callback=None) -> bool:
    """Process a single project using 2 Chrome instances in parallel."""

    def log(msg, level="INFO"):
        if callback:
            callback(msg, level)
        else:
            print(msg)

    log(f"\n{'='*60}")
    log(f"[PIC BASIC 2-CHROME] Processing: {code}")
    log(f"{'='*60}")

    # Step 1: Check if already done on master
    if is_project_complete_on_master(code):
        log(f"  Already in VISUAL folder, skip!")
        return True

    # Step 2: Copy from master
    local_dir = copy_from_master(code)
    if not local_dir:
        return False

    # Step 3: Check/Create Excel (BASIC mode)
    excel_path = local_dir / f"{code}_prompts.xlsx"
    srt_path = local_dir / f"{code}.srt"

    if not excel_path.exists():
        if srt_path.exists():
            log(f"  No Excel found, creating (BASIC mode)...")
            if not create_excel_with_api_basic(local_dir, code, callback):
                log(f"  Failed to create Excel, skip!", "ERROR")
                return False
        else:
            log(f"  No Excel and no SRT, skip!")
            return False
    elif not has_excel_with_prompts(local_dir, code):
        log(f"  Excel empty/corrupt, recreating (BASIC mode)...")
        excel_path.unlink()
        if not create_excel_with_api_basic(local_dir, code, callback):
            log(f"  Failed to recreate Excel, skip!", "ERROR")
            return False

    # Step 4: Get prompts from Excel
    log(f"  Reading prompts from Excel...")
    all_prompts = get_prompts_from_excel(excel_path, local_dir)

    if not all_prompts:
        log(f"  No prompts found in Excel!", "ERROR")
        return False

    log(f"  Found {len(all_prompts)} prompts")

    # Step 5: Generate images using 2 Chrome in parallel
    generator = DualChromeImageGenerator(callback=callback)
    result = generator.generate_parallel(all_prompts, local_dir)

    if result.get('failed', 0) > 0:
        log(f"  Some images failed: {result['failed']}", "WARN")

    # Step 6: Check completion
    if is_local_pic_complete(local_dir, code):
        log(f"  Images complete!")
        return True
    else:
        log(f"  Images incomplete", "WARN")
        return False


def scan_incomplete_local_projects() -> list:
    """Scan local PROJECTS for incomplete projects."""
    incomplete = []

    if not LOCAL_PROJECTS.exists():
        return incomplete

    for item in LOCAL_PROJECTS.iterdir():
        if not item.is_dir():
            continue

        code = item.name

        if not matches_channel(code):
            continue

        if is_project_complete_on_master(code):
            continue

        if is_local_pic_complete(item, code):
            continue

        srt_path = item / f"{code}.srt"
        if has_excel_with_prompts(item, code):
            print(f"    - {code}: incomplete (has Excel, no images)")
            incomplete.append(code)
        elif srt_path.exists():
            print(f"    - {code}: has SRT, no Excel")
            incomplete.append(code)

    return sorted(incomplete)


def scan_master_projects() -> list:
    """Scan master PROJECTS folder for pending projects."""
    pending = []

    if not MASTER_PROJECTS.exists():
        return pending

    for item in MASTER_PROJECTS.iterdir():
        if not item.is_dir():
            continue

        code = item.name

        if not matches_channel(code):
            continue

        if is_project_complete_on_master(code):
            continue

        srt_path = item / f"{code}.srt"

        if has_excel_with_prompts(item, code):
            print(f"    - {code}: ready (has prompts)")
            pending.append(code)
        elif srt_path.exists():
            print(f"    - {code}: has SRT")
            pending.append(code)

    return sorted(pending)


def run_scan_loop():
    """Run continuous scan loop for IMAGE generation (2-Chrome mode)."""
    print(f"\n{'='*60}")
    print(f"  VE3 TOOL - WORKER PIC BASIC 2-CHROME")
    print(f"{'='*60}")
    print(f"  Worker folder:   {TOOL_DIR.parent.name}")
    print(f"  Channel filter:  {WORKER_CHANNEL or 'ALL'}")
    print(f"  Mode:            2-CHROME PARALLEL")
    print(f"  Chrome1:         Characters + 50% scenes")
    print(f"  Chrome2:         Locations + 50% scenes")
    print(f"{'='*60}")

    cycle = 0

    while True:
        cycle += 1
        print(f"\n[2-CHROME CYCLE {cycle}] Scanning...")

        incomplete_local = scan_incomplete_local_projects()
        pending_master = scan_master_projects()
        pending = list(dict.fromkeys(incomplete_local + pending_master))

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
                    success = process_project_pic_basic_2(code)
                    if not success:
                        print(f"  Skipping {code}, moving to next...")
                        continue
                except KeyboardInterrupt:
                    print("\n\nStopped by user.")
                    return
                except Exception as e:
                    print(f"  Error processing {code}: {e}")
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


def main():
    import argparse
    parser = argparse.ArgumentParser(description='VE3 Worker PIC BASIC 2-Chrome - Parallel Image Generation')
    parser.add_argument('project', nargs='?', default=None, help='Project code')
    args = parser.parse_args()

    if args.project:
        process_project_pic_basic_2(args.project)
    else:
        run_scan_loop()


if __name__ == "__main__":
    main()
