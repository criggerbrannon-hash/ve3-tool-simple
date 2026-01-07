#!/usr/bin/env python3
"""
Copy project(s) từ local PROJECTS sang VISUAL folder.

Usage:
    python copy_to_visual.py                    # Copy tất cả projects có ảnh
    python copy_to_visual.py AR47-0028          # Copy 1 project cụ thể
    python copy_to_visual.py AR47-0028 AR47-0029  # Copy nhiều projects
"""

import sys
import shutil
from pathlib import Path

# Paths
TOOL_DIR = Path(__file__).parent
LOCAL_PROJECTS = TOOL_DIR / "PROJECTS"
VISUAL_FOLDER = Path(r"\\tsclient\D\AUTO\VISUAL")

def copy_project_to_visual(code: str) -> bool:
    """Copy 1 project sang VISUAL folder."""
    src = LOCAL_PROJECTS / code
    dst = VISUAL_FOLDER / code

    if not src.exists():
        print(f"  ❌ Project không tồn tại: {src}")
        return False

    # Check có ảnh không
    img_dir = src / "img"
    if not img_dir.exists():
        print(f"  ⚠️ Chưa có thư mục img: {code}")
        return False

    img_files = list(img_dir.glob("scene_*.png")) + list(img_dir.glob("scene_*.mp4"))
    if not img_files:
        print(f"  ⚠️ Chưa có ảnh/video: {code}")
        return False

    print(f"  📤 Copying: {code} ({len(img_files)} files in img/)")

    try:
        # Tạo VISUAL folder nếu chưa có
        VISUAL_FOLDER.mkdir(parents=True, exist_ok=True)

        # Xóa cũ nếu có
        if dst.exists():
            print(f"     Removing old: {dst.name}")
            shutil.rmtree(dst)

        # Copy
        shutil.copytree(src, dst)
        print(f"  ✅ Done: {dst}")
        return True

    except PermissionError:
        print(f"  ❌ Permission denied! Check RDP connection.")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def find_projects_with_images() -> list:
    """Tìm tất cả projects có ảnh."""
    projects = []

    if not LOCAL_PROJECTS.exists():
        print(f"⚠️ PROJECTS folder không tồn tại: {LOCAL_PROJECTS}")
        return projects

    for item in LOCAL_PROJECTS.iterdir():
        if item.is_dir():
            img_dir = item / "img"
            if img_dir.exists():
                img_files = list(img_dir.glob("scene_*.png")) + list(img_dir.glob("scene_*.mp4"))
                if img_files:
                    projects.append(item.name)

    return sorted(projects)


def main():
    print(f"\n{'='*60}")
    print(f"  COPY TO VISUAL")
    print(f"{'='*60}")
    print(f"  Local:  {LOCAL_PROJECTS}")
    print(f"  Visual: {VISUAL_FOLDER}")
    print(f"{'='*60}\n")

    # Check VISUAL folder accessible
    try:
        VISUAL_FOLDER.mkdir(parents=True, exist_ok=True)
        print(f"✅ VISUAL folder accessible\n")
    except PermissionError:
        print(f"❌ Cannot access VISUAL folder!")
        print(f"   Check RDP connection: \\\\tsclient\\D")
        return
    except Exception as e:
        print(f"❌ Error accessing VISUAL: {e}")
        return

    # Get projects to copy
    if len(sys.argv) > 1:
        # Copy specific projects
        projects = sys.argv[1:]
    else:
        # Copy all projects with images
        projects = find_projects_with_images()
        if not projects:
            print("⚠️ Không có project nào có ảnh để copy!")
            return
        print(f"Found {len(projects)} projects with images:\n")

    # Copy
    success = 0
    failed = 0

    for code in projects:
        if copy_project_to_visual(code):
            success += 1
        else:
            failed += 1

    print(f"\n{'='*60}")
    print(f"  Result: {success} success, {failed} failed")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
