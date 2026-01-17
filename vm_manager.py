#!/usr/bin/env python3
"""
VM Manager - Quản lý các Chrome workers trên máy ảo.

=============================================================
  VM MANAGER - Central Control for Chrome Workers
=============================================================

Features:
1. Mở/đóng/restart các CMD Chrome workers
2. Giám sát output - phát hiện lỗi tự động
3. Kill Chrome processes trước khi restart (giống làm thủ công)
4. Có thể chạy Excel API riêng

Usage:
    python vm_manager.py              # Chạy với 2 Chrome workers
    python vm_manager.py --workers 1  # Chạy 1 Chrome worker
    python vm_manager.py --excel      # Mở cả Excel API worker

Commands trong Manager:
    status  - Xem trạng thái workers
    restart - Restart tất cả workers
    restart 1 - Restart worker 1
    kill    - Kill tất cả Chrome processes
    excel   - Mở Excel API worker
    quit    - Thoát và đóng tất cả
"""

import subprocess
import sys
import os
import time
import threading
import signal
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
import re

TOOL_DIR = Path(__file__).parent

# ================================================================================
# CONFIGURATION
# ================================================================================

# Patterns để detect lỗi trong output
ERROR_PATTERNS = [
    r"Chrome attempt \d+/\d+ failed",
    r"✗ Chrome error",
    r"✗ Không restart được Chrome",
    r"The browser connection fails",
    r"reCAPTCHA evaluation failed",
    r"✗ Failed:",
    r"ERROR: No SRT file",
    r"Network error",
]

# Patterns cho lỗi fatal (cần restart ngay)
FATAL_ERROR_PATTERNS = [
    r"Chrome attempt 3/3 failed",  # Hết retry
    r"✗ Không restart được Chrome",
    r"The browser connection fails.*Version:",  # Final Chrome error
]

# Thời gian chờ trước khi restart (giây)
RESTART_DELAY = 5

# Số lỗi liên tiếp trước khi restart
MAX_ERRORS_BEFORE_RESTART = 3


# ================================================================================
# WORKER STATUS
# ================================================================================

class WorkerStatus(Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    ERROR = "ERROR"
    RESTARTING = "RESTARTING"


@dataclass
class WorkerInfo:
    """Thông tin về một worker subprocess."""
    worker_id: int
    worker_type: str  # "chrome" or "excel"
    process: Optional[subprocess.Popen] = None
    status: WorkerStatus = WorkerStatus.STOPPED
    start_time: Optional[datetime] = None
    error_count: int = 0
    restart_count: int = 0
    last_error: str = ""
    last_output_line: str = ""


# ================================================================================
# VM MANAGER
# ================================================================================

class VMManager:
    """Manager điều khiển các Chrome workers."""

    def __init__(self, num_chrome_workers: int = 2, auto_restart: bool = True):
        self.num_chrome_workers = num_chrome_workers
        self.auto_restart = auto_restart
        self.workers: Dict[str, WorkerInfo] = {}
        self._stop_flag = False
        self._monitor_threads: List[threading.Thread] = []
        self._lock = threading.Lock()

        # Initialize workers
        for i in range(num_chrome_workers):
            key = f"chrome_{i+1}"
            self.workers[key] = WorkerInfo(
                worker_id=i + 1,
                worker_type="chrome"
            )

        # Excel worker (optional)
        self.workers["excel"] = WorkerInfo(
            worker_id=0,
            worker_type="excel"
        )

    def log(self, msg: str, worker_key: str = "MANAGER"):
        """Log message với timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{worker_key}] {msg}")

    def kill_all_chrome_processes(self):
        """Kill tất cả Chrome processes (giống làm thủ công)."""
        self.log("Killing all Chrome processes...", "MANAGER")

        if sys.platform == "win32":
            # Windows - kill chrome.exe và GoogleChromePortable.exe
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", "chrome.exe"],
                    capture_output=True,
                    timeout=10
                )
            except:
                pass

            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", "GoogleChromePortable.exe"],
                    capture_output=True,
                    timeout=10
                )
            except:
                pass
        else:
            # Linux/Mac
            try:
                subprocess.run(["pkill", "-f", "chrome"], capture_output=True, timeout=10)
            except:
                pass

        time.sleep(2)  # Đợi Chrome đóng hoàn toàn
        self.log("Chrome processes killed", "MANAGER")

    def get_chrome_worker_script(self, worker_id: int) -> str:
        """Lấy script path cho Chrome worker."""
        if worker_id == 1:
            return str(TOOL_DIR / "_run_chrome1.py")
        elif worker_id == 2:
            return str(TOOL_DIR / "_run_chrome2.py")
        else:
            return str(TOOL_DIR / f"_run_chrome{worker_id}.py")

    def start_worker(self, worker_key: str) -> bool:
        """Start một worker subprocess."""
        if worker_key not in self.workers:
            self.log(f"Worker {worker_key} not found", "ERROR")
            return False

        worker = self.workers[worker_key]

        # Nếu đang chạy, không start lại
        if worker.process and worker.process.poll() is None:
            self.log(f"Worker {worker_key} already running", worker_key)
            return True

        worker.status = WorkerStatus.STARTING
        self.log(f"Starting {worker_key}...", worker_key)

        try:
            if worker.worker_type == "chrome":
                script = self.get_chrome_worker_script(worker.worker_id)

                # Check script exists
                if not Path(script).exists():
                    self.log(f"Script not found: {script}", "ERROR")
                    worker.status = WorkerStatus.ERROR
                    return False

                # Start subprocess
                if sys.platform == "win32":
                    # Windows - mở CMD mới
                    cmd = f'start "Chrome Worker {worker.worker_id}" cmd /k "cd /d {TOOL_DIR} && python {script}"'
                    worker.process = subprocess.Popen(
                        cmd,
                        shell=True,
                        cwd=str(TOOL_DIR)
                    )
                else:
                    # Linux - chạy trong background với output capture
                    worker.process = subprocess.Popen(
                        [sys.executable, script],
                        cwd=str(TOOL_DIR),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1
                    )

                    # Start monitor thread
                    monitor = threading.Thread(
                        target=self._monitor_worker_output,
                        args=(worker_key,),
                        daemon=True
                    )
                    monitor.start()
                    self._monitor_threads.append(monitor)

            elif worker.worker_type == "excel":
                script = str(TOOL_DIR / "run_excel_api.py")

                if not Path(script).exists():
                    self.log(f"Excel script not found: {script}", "ERROR")
                    worker.status = WorkerStatus.ERROR
                    return False

                if sys.platform == "win32":
                    cmd = f'start "Excel API Worker" cmd /k "cd /d {TOOL_DIR} && python {script}"'
                    worker.process = subprocess.Popen(cmd, shell=True, cwd=str(TOOL_DIR))
                else:
                    worker.process = subprocess.Popen(
                        [sys.executable, script],
                        cwd=str(TOOL_DIR),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1
                    )

            worker.status = WorkerStatus.RUNNING
            worker.start_time = datetime.now()
            worker.error_count = 0
            self.log(f"Started {worker_key} (PID: {worker.process.pid if worker.process else 'N/A'})", worker_key)
            return True

        except Exception as e:
            self.log(f"Failed to start {worker_key}: {e}", "ERROR")
            worker.status = WorkerStatus.ERROR
            worker.last_error = str(e)
            return False

    def stop_worker(self, worker_key: str) -> bool:
        """Stop một worker subprocess."""
        if worker_key not in self.workers:
            return False

        worker = self.workers[worker_key]

        if worker.process:
            self.log(f"Stopping {worker_key}...", worker_key)
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
        return True

    def restart_worker(self, worker_key: str, kill_chrome: bool = True) -> bool:
        """
        Restart một worker.

        Args:
            worker_key: Key của worker
            kill_chrome: Có kill Chrome processes trước không (giống làm thủ công)
        """
        if worker_key not in self.workers:
            return False

        worker = self.workers[worker_key]
        worker.status = WorkerStatus.RESTARTING
        worker.restart_count += 1

        self.log(f"Restarting {worker_key} (lần {worker.restart_count})...", worker_key)

        # 1. Stop worker subprocess
        self.stop_worker(worker_key)

        # 2. Kill Chrome processes nếu là Chrome worker
        if kill_chrome and worker.worker_type == "chrome":
            self.kill_all_chrome_processes()

        # 3. Đợi một chút
        time.sleep(RESTART_DELAY)

        # 4. Start lại
        return self.start_worker(worker_key)

    def _monitor_worker_output(self, worker_key: str):
        """Monitor output của worker subprocess (Linux only)."""
        worker = self.workers[worker_key]

        while not self._stop_flag and worker.process:
            try:
                line = worker.process.stdout.readline()
                if not line:
                    if worker.process.poll() is not None:
                        # Process đã kết thúc
                        self.log(f"Process exited (code: {worker.process.returncode})", worker_key)
                        worker.status = WorkerStatus.STOPPED

                        # Auto restart nếu được bật
                        if self.auto_restart and not self._stop_flag:
                            self.log("Auto-restarting...", worker_key)
                            time.sleep(RESTART_DELAY)
                            self.restart_worker(worker_key)
                        break
                    continue

                line = line.strip()
                worker.last_output_line = line

                # Print output
                print(f"[{worker_key}] {line}")

                # Check for errors
                self._check_for_errors(worker_key, line)

            except Exception as e:
                self.log(f"Monitor error: {e}", worker_key)
                break

    def _check_for_errors(self, worker_key: str, line: str):
        """Check output line cho errors."""
        worker = self.workers[worker_key]

        # Check fatal errors
        for pattern in FATAL_ERROR_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                self.log(f"FATAL ERROR detected: {line[:100]}", worker_key)
                worker.last_error = line
                worker.status = WorkerStatus.ERROR

                if self.auto_restart:
                    self.log("Auto-restart triggered by fatal error", worker_key)
                    # Restart trong thread riêng để không block
                    threading.Thread(
                        target=self.restart_worker,
                        args=(worker_key,),
                        daemon=True
                    ).start()
                return

        # Check normal errors
        for pattern in ERROR_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                worker.error_count += 1
                worker.last_error = line
                self.log(f"Error detected ({worker.error_count}): {line[:80]}", worker_key)

                if worker.error_count >= MAX_ERRORS_BEFORE_RESTART and self.auto_restart:
                    self.log(f"Too many errors ({worker.error_count}), restarting...", worker_key)
                    threading.Thread(
                        target=self.restart_worker,
                        args=(worker_key,),
                        daemon=True
                    ).start()
                return

    def start_all_chrome_workers(self):
        """Start tất cả Chrome workers."""
        self.log("Starting all Chrome workers...", "MANAGER")

        # Kill Chrome trước khi start (clean state)
        self.kill_all_chrome_processes()

        for key in self.workers:
            if self.workers[key].worker_type == "chrome":
                time.sleep(2)  # Delay giữa các workers
                self.start_worker(key)

    def stop_all_workers(self):
        """Stop tất cả workers."""
        self._stop_flag = True

        for key in self.workers:
            self.stop_worker(key)

        self.kill_all_chrome_processes()

    def get_status_summary(self) -> str:
        """Lấy tóm tắt trạng thái."""
        lines = [
            "",
            "=" * 60,
            "  WORKER STATUS",
            "=" * 60,
        ]

        for key, worker in self.workers.items():
            if worker.worker_type == "excel" and worker.status == WorkerStatus.STOPPED:
                continue  # Skip Excel nếu không chạy

            status_emoji = {
                WorkerStatus.STOPPED: "⏹️",
                WorkerStatus.STARTING: "🔄",
                WorkerStatus.RUNNING: "✅",
                WorkerStatus.ERROR: "❌",
                WorkerStatus.RESTARTING: "🔄",
            }.get(worker.status, "❓")

            uptime = ""
            if worker.start_time:
                delta = datetime.now() - worker.start_time
                minutes = int(delta.total_seconds() // 60)
                uptime = f" (uptime: {minutes}m)"

            lines.append(
                f"  {status_emoji} {key}: {worker.status.value}"
                f" | errors: {worker.error_count}"
                f" | restarts: {worker.restart_count}"
                f"{uptime}"
            )

            if worker.last_error:
                lines.append(f"      Last error: {worker.last_error[:60]}...")

        lines.append("=" * 60)
        return "\n".join(lines)

    def run_interactive(self):
        """Chạy interactive mode với command prompt."""
        print("""
╔═══════════════════════════════════════════════════════════════╗
║              VM MANAGER - Chrome Worker Control               ║
╠═══════════════════════════════════════════════════════════════╣
║  Commands:                                                    ║
║    status       - Xem trạng thái workers                      ║
║    restart      - Restart tất cả Chrome workers               ║
║    restart 1    - Restart Chrome worker 1                     ║
║    restart 2    - Restart Chrome worker 2                     ║
║    kill         - Kill tất cả Chrome processes                ║
║    excel        - Mở Excel API worker                         ║
║    stop excel   - Dừng Excel API worker                       ║
║    quit/exit    - Thoát và đóng tất cả                        ║
╚═══════════════════════════════════════════════════════════════╝
""")

        # Start Chrome workers
        self.start_all_chrome_workers()

        # Interactive loop
        try:
            while not self._stop_flag:
                try:
                    cmd = input("\n[VM Manager] > ").strip().lower()

                    if not cmd:
                        continue

                    elif cmd == "status":
                        print(self.get_status_summary())

                    elif cmd == "restart":
                        for key in self.workers:
                            if self.workers[key].worker_type == "chrome":
                                self.restart_worker(key)

                    elif cmd.startswith("restart "):
                        try:
                            worker_num = int(cmd.split()[1])
                            key = f"chrome_{worker_num}"
                            if key in self.workers:
                                self.restart_worker(key)
                            else:
                                print(f"Worker {worker_num} not found")
                        except ValueError:
                            print("Usage: restart <worker_number>")

                    elif cmd == "kill":
                        self.kill_all_chrome_processes()

                    elif cmd == "excel":
                        self.start_worker("excel")

                    elif cmd == "stop excel":
                        self.stop_worker("excel")

                    elif cmd in ("quit", "exit", "q"):
                        print("\nShutting down...")
                        break

                    else:
                        print(f"Unknown command: {cmd}")
                        print("Commands: status, restart, kill, excel, quit")

                except EOFError:
                    break
                except KeyboardInterrupt:
                    print("\nUse 'quit' to exit properly")

        finally:
            self.stop_all_workers()
            print("VM Manager stopped.")


# ================================================================================
# MAIN
# ================================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="VM Manager - Quản lý Chrome workers trên máy ảo"
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=2,
        help="Số Chrome workers (default: 2)"
    )
    parser.add_argument(
        "--no-auto-restart",
        action="store_true",
        help="Tắt auto-restart khi có lỗi"
    )
    parser.add_argument(
        "--excel",
        action="store_true",
        help="Mở cả Excel API worker"
    )

    args = parser.parse_args()

    manager = VMManager(
        num_chrome_workers=args.workers,
        auto_restart=not args.no_auto_restart
    )

    if args.excel:
        manager.start_worker("excel")

    manager.run_interactive()


if __name__ == "__main__":
    main()
