#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VE3 Tool - Basic Image Generator
Tạo ảnh từ file Excel prompts.

Usage:
    python run_worker_basic.py path/to/AR47-0028_prompts.xlsx
    python run_worker_basic.py                              (chọn file qua dialog)

Output:
    Ảnh được lưu trong thư mục img/ cạnh file Excel
    VD: path/to/img/1.png, path/to/img/2.png, ...
"""

import sys
import time
from pathlib import Path

# Add current directory to path
TOOL_DIR = Path(__file__).parent
sys.path.insert(0, str(TOOL_DIR))


def log(msg: str, level: str = "INFO"):
    """Print log with timestamp."""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")


def select_excel_file() -> Path:
    """Open file dialog to select Excel file."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()  # Hide main window

        file_path = filedialog.askopenfilename(
            title="Chọn file Excel prompts",
            filetypes=[
                ("Excel files", "*.xlsx"),
                ("All files", "*.*")
            ],
            initialdir=str(TOOL_DIR / "PROJECTS")
        )

        root.destroy()

        if file_path:
            return Path(file_path)
        return None

    except Exception as e:
        log(f"Cannot open file dialog: {e}", "ERROR")
        return None


def generate_images(excel_path: Path) -> bool:
    """
    Generate images from Excel prompts.

    Args:
        excel_path: Path to Excel file (e.g., AR47-0028_prompts.xlsx)

    Returns:
        True if successful
    """
    if not excel_path.exists():
        log(f"File not found: {excel_path}")
        return False

    # Get project info
    name = excel_path.stem.replace("_prompts", "")
    project_dir = excel_path.parent
    img_dir = project_dir / "img"

    log("=" * 60)
    log(f"  VE3 BASIC - IMAGE GENERATOR")
    log("=" * 60)
    log(f"  Excel:   {excel_path.name}")
    log(f"  Project: {name}")
    log(f"  Output:  {img_dir}")
    log("=" * 60)

    # Check existing images
    if img_dir.exists():
        existing = list(img_dir.glob("*.png"))
        if existing:
            log(f"  Found {len(existing)} existing images")

    # Run SmartEngine
    try:
        from modules.smart_engine import SmartEngine

        engine = SmartEngine()

        def callback(msg):
            log(f"  {msg}")

        log("\nStarting image generation...")
        log("(This may take a while depending on number of scenes)\n")

        # Run with skip_compose=True (only create images, no video)
        result = engine.run(
            str(excel_path),
            callback=callback,
            skip_compose=True
        )

        if result.get('error'):
            log(f"\nError: {result.get('error')}")
            return False

        # Count results
        if img_dir.exists():
            images = list(img_dir.glob("*.png"))
            videos = list(img_dir.glob("*.mp4"))
            log(f"\nDone!")
            log(f"  Images created: {len(images)}")
            if videos:
                log(f"  Videos created: {len(videos)}")
            log(f"  Output folder: {img_dir}")

        return True

    except Exception as e:
        log(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "=" * 60)
    print("  VE3 TOOL - BASIC IMAGE GENERATOR")
    print("  (Simplified version for image creation only)")
    print("=" * 60 + "\n")

    # Get Excel path
    if len(sys.argv) >= 2:
        excel_path = Path(sys.argv[1])
    else:
        log("No file specified, opening file dialog...")
        excel_path = select_excel_file()

    if not excel_path:
        log("No file selected. Exiting.")
        print("\nUsage: python run_worker_basic.py path/to/excel_prompts.xlsx")
        return

    # Validate file
    if not excel_path.exists():
        log(f"File not found: {excel_path}")
        return

    if not excel_path.suffix.lower() == '.xlsx':
        log(f"Not an Excel file: {excel_path}")
        return

    if "_prompts" not in excel_path.stem:
        log(f"Warning: File name should contain '_prompts' (e.g., AR47-0028_prompts.xlsx)")

    # Generate images
    success = generate_images(excel_path)

    if success:
        print("\n" + "=" * 60)
        print("  COMPLETED SUCCESSFULLY!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("  FAILED - Check errors above")
        print("=" * 60)


if __name__ == "__main__":
    main()
