#!/usr/bin/env python3
"""
VM Manager - AI Agent System for Chrome Workers
================================================

Hệ thống AI Agent điều phối công việc trên máy ảo:
1. Excel Worker (1 process) - Tạo Excel tuần tự
2. Chrome Workers (N processes) - Tạo ảnh/video song song

Flow:
  Manager quét projects
    ↓
  Thêm vào Task Queue: [excel] → [image] → [video]
    ↓
  Excel Worker xử lý tuần tự: mã 1 → mã 2 → mã 3...
    ↓
  Chrome Workers xử lý song song: ảnh + video

Usage:
    python vm_manager.py                  # 2 Chrome workers (default)
    python vm_manager.py --chrome 3       # 3 Chrome workers
    python vm_manager.py --chrome 5       # 5 Chrome workers
    python vm_manager.py --no-excel       # Không chạy Excel worker

Commands:
    status   - Xem trạng thái
    restart  - Restart tất cả
    restart chrome 1 - Restart Chrome worker 1
    restart excel    - Restart Excel worker
    add KA2-0001     - Thêm project vào queue
    kill     - Kill tất cả Chrome processes
    scale 5  - Scale lên 5 Chrome workers
    quit     - Thoát
"""

import subprocess
import sys
import os
import time
import json
import threading
import queue
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Set
from dataclasses import dataclass, field
from enum import Enum
import re

TOOL_DIR = Path(__file__).parent

# ================================================================================
# CONFIGURATION
# ================================================================================

# Task types
class TaskType(Enum):
    EXCEL = "excel"      # Tạo/hoàn thiện Excel
    IMAGE = "image"      # Tạo ảnh
    VIDEO = "video"      # Tạo video


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkerStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    IDLE = "idle"
    WORKING = "working"
    ERROR = "error"
    RESTARTING = "restarting"


# Error patterns for auto-restart
ERROR_PATTERNS = [
    r"Chrome attempt \d+/\d+ failed",
    r"✗ Chrome error",
    r"✗ Không restart được Chrome",
    r"The browser connection fails",
    r"reCAPTCHA evaluation failed",
    r"403.*error",
]

FATAL_PATTERNS = [
    r"Chrome attempt 3/3 failed",
    r"✗ Không restart được Chrome",
]

# Timing
RESTART_DELAY = 5
SCAN_INTERVAL = 30
MAX_ERRORS = 3


# ================================================================================
# DATA STRUCTURES
# ================================================================================

@dataclass
class Task:
    """Một task trong queue."""
    project_code: str
    task_type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    worker_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: str = ""
    retry_count: int = 0


@dataclass
class WorkerInfo:
    """Thông tin về một worker subprocess."""
    worker_id: str
    worker_type: str  # "excel" or "chrome"
    worker_num: int = 0  # Số thứ tự Chrome (1, 2, 3...)
    process: Optional[subprocess.Popen] = None
    status: WorkerStatus = WorkerStatus.STOPPED
    current_task: Optional[Task] = None
    start_time: Optional[datetime] = None
    error_count: int = 0
    restart_count: int = 0
    completed_tasks: int = 0
    last_output: str = ""


# ================================================================================
# VM MANAGER - AI AGENT
# ================================================================================

class VMManager:
    """
    AI Agent điều phối các workers.
    """

    def __init__(self, num_chrome_workers: int = 2, enable_excel: bool = True):
        self.num_chrome_workers = num_chrome_workers
        self.enable_excel = enable_excel

        # Workers
        self.workers: Dict[str, WorkerInfo] = {}
        self._init_workers()

        # Task queue
        self.task_queue: queue.Queue = queue.Queue()
        self.active_tasks: Dict[str, Task] = {}  # project_code → Task
        self.completed_projects: Set[str] = set()

        # Control
        self._stop_flag = False
        self._lock = threading.Lock()
        self._threads: List[threading.Thread] = []

        # Project tracking
        self.auto_path = self._detect_auto_path()
        self.channel = self._get_channel_from_folder()

    def _init_workers(self):
        """Initialize worker slots."""
        # Excel worker
        if self.enable_excel:
            self.workers["excel"] = WorkerInfo(
                worker_id="excel",
                worker_type="excel"
            )

        # Chrome workers
        for i in range(self.num_chrome_workers):
            worker_id = f"chrome_{i+1}"
            self.workers[worker_id] = WorkerInfo(
                worker_id=worker_id,
                worker_type="chrome",
                worker_num=i + 1
            )

    def _detect_auto_path(self) -> Optional[Path]:
        """Detect network AUTO path."""
        paths = [
            Path(r"\\tsclient\D\AUTO"),
            Path(r"\\vmware-host\Shared Folders\D\AUTO"),
            Path(r"Z:\AUTO"),
            Path(r"Y:\AUTO"),
            Path(r"D:\AUTO"),
        ]
        for p in paths:
            try:
                if p.exists():
                    return p
            except:
                pass
        return None

    def _get_channel_from_folder(self) -> Optional[str]:
        """Get channel filter from folder name."""
        folder = TOOL_DIR.parent.name
        if "-T" in folder:
            return folder.split("-T")[0]
        elif folder.startswith("KA") or folder.startswith("AR"):
            return folder.split("-")[0] if "-" in folder else folder[:3]
        return None

    # ================================================================================
    # LOGGING
    # ================================================================================

    def log(self, msg: str, source: str = "MANAGER", level: str = "INFO"):
        """Log với timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        emoji = {
            "INFO": "  ",
            "WARN": "⚠️",
            "ERROR": "❌",
            "SUCCESS": "✅",
            "TASK": "📋",
        }.get(level, "  ")
        print(f"[{timestamp}] [{source}] {emoji} {msg}")

    # ================================================================================
    # CHROME PROCESS CONTROL
    # ================================================================================

    def kill_all_chrome(self):
        """Kill tất cả Chrome processes."""
        self.log("Killing all Chrome processes...", "SYSTEM")

        if sys.platform == "win32":
            try:
                subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"],
                             capture_output=True, timeout=10)
            except:
                pass
            try:
                subprocess.run(["taskkill", "/F", "/IM", "GoogleChromePortable.exe"],
                             capture_output=True, timeout=10)
            except:
                pass
        else:
            try:
                subprocess.run(["pkill", "-f", "chrome"], capture_output=True, timeout=10)
            except:
                pass

        time.sleep(2)
        self.log("Chrome processes killed", "SYSTEM", "SUCCESS")

    # ================================================================================
    # WORKER CONTROL
    # ================================================================================

    def _get_worker_script(self, worker: WorkerInfo) -> Path:
        """Get script path for worker."""
        if worker.worker_type == "excel":
            return TOOL_DIR / "run_excel_api.py"
        else:
            # Chrome workers: _run_chrome1.py, _run_chrome2.py, etc.
            return TOOL_DIR / f"_run_chrome{worker.worker_num}.py"

    def start_worker(self, worker_id: str) -> bool:
        """Start một worker subprocess."""
        if worker_id not in self.workers:
            self.log(f"Worker {worker_id} not found", "ERROR", "ERROR")
            return False

        worker = self.workers[worker_id]

        # Check if already running
        if worker.process and worker.process.poll() is None:
            self.log(f"{worker_id} already running", worker_id)
            return True

        worker.status = WorkerStatus.STARTING
        script = self._get_worker_script(worker)

        if not script.exists():
            self.log(f"Script not found: {script}", worker_id, "ERROR")
            worker.status = WorkerStatus.ERROR
            return False

        self.log(f"Starting {worker_id}...", worker_id)

        try:
            if sys.platform == "win32":
                # Windows - mở CMD mới
                title = f"{worker.worker_type.upper()} Worker {worker.worker_num or ''}"
                args = ""

                if worker.worker_type == "excel":
                    args = "--loop"  # Excel chạy loop

                cmd = f'start "{title}" cmd /k "cd /d {TOOL_DIR} && python {script.name} {args}"'
                worker.process = subprocess.Popen(cmd, shell=True, cwd=str(TOOL_DIR))
            else:
                # Linux
                args = ["--loop"] if worker.worker_type == "excel" else []
                worker.process = subprocess.Popen(
                    [sys.executable, str(script)] + args,
                    cwd=str(TOOL_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )

                # Monitor thread
                t = threading.Thread(
                    target=self._monitor_worker,
                    args=(worker_id,),
                    daemon=True
                )
                t.start()
                self._threads.append(t)

            worker.status = WorkerStatus.IDLE
            worker.start_time = datetime.now()
            worker.error_count = 0

            self.log(f"{worker_id} started", worker_id, "SUCCESS")
            return True

        except Exception as e:
            self.log(f"Failed to start {worker_id}: {e}", worker_id, "ERROR")
            worker.status = WorkerStatus.ERROR
            return False

    def stop_worker(self, worker_id: str) -> bool:
        """Stop một worker."""
        if worker_id not in self.workers:
            return False

        worker = self.workers[worker_id]

        if worker.process:
            self.log(f"Stopping {worker_id}...", worker_id)
            try:
                worker.process.terminate()
                worker.process.wait(timeout=5)
            except:
                try:
                    worker.process.kill()
                except:
                    pass
            worker.process = None

        worker.status = WorkerStatus.STOPPED
        worker.current_task = None
        return True

    def restart_worker(self, worker_id: str, kill_chrome: bool = True) -> bool:
        """Restart một worker."""
        if worker_id not in self.workers:
            return False

        worker = self.workers[worker_id]
        worker.status = WorkerStatus.RESTARTING
        worker.restart_count += 1

        self.log(f"Restarting {worker_id} (lần {worker.restart_count})...", worker_id)

        # Stop current
        self.stop_worker(worker_id)

        # Kill Chrome if needed
        if kill_chrome and worker.worker_type == "chrome":
            self.kill_all_chrome()

        time.sleep(RESTART_DELAY)

        return self.start_worker(worker_id)

    def _monitor_worker(self, worker_id: str):
        """Monitor worker output (Linux only)."""
        worker = self.workers[worker_id]

        while not self._stop_flag and worker.process:
            try:
                line = worker.process.stdout.readline()
                if not line:
                    if worker.process.poll() is not None:
                        self.log(f"Process exited", worker_id, "WARN")
                        worker.status = WorkerStatus.STOPPED

                        # Auto-restart
                        if not self._stop_flag:
                            time.sleep(RESTART_DELAY)
                            self.restart_worker(worker_id)
                        break
                    continue

                line = line.strip()
                worker.last_output = line
                print(f"[{worker_id}] {line}")

                # Check errors
                self._check_errors(worker_id, line)

            except Exception as e:
                self.log(f"Monitor error: {e}", worker_id, "ERROR")
                break

    def _check_errors(self, worker_id: str, line: str):
        """Check output for errors."""
        worker = self.workers[worker_id]

        # Fatal errors → immediate restart
        for pattern in FATAL_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                self.log(f"FATAL: {line[:80]}", worker_id, "ERROR")
                threading.Thread(
                    target=self.restart_worker,
                    args=(worker_id,),
                    daemon=True
                ).start()
                return

        # Normal errors
        for pattern in ERROR_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                worker.error_count += 1
                self.log(f"Error ({worker.error_count}): {line[:60]}", worker_id, "WARN")

                if worker.error_count >= MAX_ERRORS:
                    self.log(f"Too many errors, restarting...", worker_id, "ERROR")
                    threading.Thread(
                        target=self.restart_worker,
                        args=(worker_id,),
                        daemon=True
                    ).start()
                return

    # ================================================================================
    # SCALING
    # ================================================================================

    def scale_chrome_workers(self, num_workers: int):
        """Scale số lượng Chrome workers."""
        current = self.num_chrome_workers

        if num_workers > current:
            # Scale up
            for i in range(current + 1, num_workers + 1):
                worker_id = f"chrome_{i}"
                self.workers[worker_id] = WorkerInfo(
                    worker_id=worker_id,
                    worker_type="chrome",
                    worker_num=i
                )
                self.start_worker(worker_id)

        elif num_workers < current:
            # Scale down
            for i in range(num_workers + 1, current + 1):
                worker_id = f"chrome_{i}"
                self.stop_worker(worker_id)
                del self.workers[worker_id]

        self.num_chrome_workers = num_workers
        self.log(f"Scaled to {num_workers} Chrome workers", "MANAGER", "SUCCESS")

    # ================================================================================
    # START ALL
    # ================================================================================

    def start_all(self):
        """Start tất cả workers."""
        self.log("Starting all workers...", "MANAGER")

        # Kill Chrome trước (clean state)
        self.kill_all_chrome()

        # Start Excel worker first
        if self.enable_excel:
            self.start_worker("excel")
            time.sleep(2)

        # Start Chrome workers
        for i in range(1, self.num_chrome_workers + 1):
            worker_id = f"chrome_{i}"
            self.start_worker(worker_id)
            time.sleep(2)  # Delay giữa các Chrome

    def stop_all(self):
        """Stop tất cả workers."""
        self._stop_flag = True

        for worker_id in list(self.workers.keys()):
            self.stop_worker(worker_id)

        self.kill_all_chrome()
        self.log("All workers stopped", "MANAGER")

    # ================================================================================
    # STATUS
    # ================================================================================

    def get_status(self) -> str:
        """Get status summary."""
        lines = [
            "",
            "═" * 65,
            "  VM MANAGER STATUS",
            "═" * 65,
            f"  Channel: {self.channel or 'ALL'}",
            f"  Auto path: {self.auto_path or 'Not found'}",
            "",
            "  WORKERS:",
        ]

        for worker_id, worker in self.workers.items():
            emoji = {
                WorkerStatus.STOPPED: "⏹️ ",
                WorkerStatus.STARTING: "🔄",
                WorkerStatus.IDLE: "😴",
                WorkerStatus.WORKING: "⚡",
                WorkerStatus.ERROR: "❌",
                WorkerStatus.RESTARTING: "🔄",
            }.get(worker.status, "❓")

            uptime = ""
            if worker.start_time:
                delta = datetime.now() - worker.start_time
                mins = int(delta.total_seconds() // 60)
                uptime = f" ({mins}m)"

            lines.append(
                f"    {emoji} {worker_id}: {worker.status.value}"
                f" | errors: {worker.error_count}"
                f" | restarts: {worker.restart_count}"
                f" | done: {worker.completed_tasks}"
                f"{uptime}"
            )

        lines.append("")
        lines.append("═" * 65)
        return "\n".join(lines)

    # ================================================================================
    # INTERACTIVE
    # ================================================================================

    def run_interactive(self):
        """Run interactive mode."""
        print(f"""
╔═══════════════════════════════════════════════════════════════════╗
║           VM MANAGER - AI Agent for Chrome Workers                ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  Workers: 1 Excel (tuần tự) + {self.num_chrome_workers} Chrome (song song)              ║
║  Channel: {str(self.channel or 'ALL'):<10}                                            ║
║                                                                   ║
╠═══════════════════════════════════════════════════════════════════╣
║  Commands:                                                        ║
║    status              - Xem trạng thái                           ║
║    restart             - Restart tất cả                           ║
║    restart chrome 1    - Restart Chrome worker 1                  ║
║    restart chrome 2    - Restart Chrome worker 2                  ║
║    restart excel       - Restart Excel worker                     ║
║    kill                - Kill tất cả Chrome processes             ║
║    scale <N>           - Scale lên N Chrome workers               ║
║    quit                - Thoát                                    ║
╚═══════════════════════════════════════════════════════════════════╝
""")

        # Start workers
        self.start_all()

        # Interactive loop
        try:
            while not self._stop_flag:
                try:
                    cmd = input("\n[VM Manager] > ").strip().lower()

                    if not cmd:
                        continue

                    elif cmd == "status":
                        print(self.get_status())

                    elif cmd == "restart":
                        for wid in list(self.workers.keys()):
                            self.restart_worker(wid)

                    elif cmd.startswith("restart chrome "):
                        try:
                            num = int(cmd.split()[-1])
                            self.restart_worker(f"chrome_{num}")
                        except:
                            print("Usage: restart chrome <number>")

                    elif cmd == "restart excel":
                        self.restart_worker("excel")

                    elif cmd == "kill":
                        self.kill_all_chrome()

                    elif cmd.startswith("scale "):
                        try:
                            num = int(cmd.split()[-1])
                            if 1 <= num <= 10:
                                self.scale_chrome_workers(num)
                            else:
                                print("Scale 1-10 Chrome workers")
                        except:
                            print("Usage: scale <number>")

                    elif cmd in ("quit", "exit", "q"):
                        print("\nShutting down...")
                        break

                    else:
                        print(f"Unknown: {cmd}")
                        print("Commands: status, restart, kill, scale, quit")

                except EOFError:
                    break
                except KeyboardInterrupt:
                    print("\nUse 'quit' to exit")

        finally:
            self.stop_all()
            print("VM Manager stopped.")


# ================================================================================
# MAIN
# ================================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="VM Manager - AI Agent System")
    parser.add_argument("--chrome", "-c", type=int, default=2,
                       help="Số Chrome workers (default: 2)")
    parser.add_argument("--no-excel", action="store_true",
                       help="Không chạy Excel worker")

    args = parser.parse_args()

    manager = VMManager(
        num_chrome_workers=args.chrome,
        enable_excel=not args.no_excel
    )

    manager.run_interactive()


if __name__ == "__main__":
    main()
