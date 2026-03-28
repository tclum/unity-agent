import time
import threading
from pathlib import Path

from core.task_queue import add_task
from core.project_manager import get_active_project

LOG_PATH = Path.home() / "Library/Logs/Unity/Editor.log"

# Errors that should auto-trigger a task
ERROR_SIGNALS = [
    "NullReferenceException",
    "MissingReferenceException",
    "ArgumentNullException",
    "IndexOutOfRangeException",
    "UnassignedReferenceException",
]

# How often to poll the log file (seconds)
POLL_INTERVAL = 10

# Cooldown before the same error can trigger again (seconds)
ERROR_COOLDOWN = 120


class LogWatcher:
    def __init__(self):
        self._last_size = 0
        self._seen_errors: dict[str, float] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[LogWatcher] Started — monitoring Unity log for errors.")

    def stop(self):
        self._running = False

    def _run(self):
        while self._running:
            try:
                self._check_log()
            except Exception as e:
                print(f"[LogWatcher] Error during log check: {e}")
            time.sleep(POLL_INTERVAL)

    def _check_log(self):
        if not LOG_PATH.exists():
            return

        current_size = LOG_PATH.stat().st_size

        if current_size <= self._last_size:
            return

        with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(self._last_size)
            new_content = f.read()

        self._last_size = current_size

        for line in new_content.splitlines():
            for signal in ERROR_SIGNALS:
                if signal in line:
                    self._handle_error(signal, line)
                    break

    def _handle_error(self, signal: str, line: str):
        now = time.time()

        with self._lock:
            last_seen = self._seen_errors.get(signal, 0)
            if now - last_seen < ERROR_COOLDOWN:
                return
            self._seen_errors[signal] = now

        project_id = get_active_project()
        if not project_id:
            return

        # Extract a short context from the log line
        context = line.strip()[:120]
        task_title = f"auto: {signal} detected — {context}"

        task = add_task(
            project_id=project_id,
            title=task_title,
            channel_id=None,
        )

        print(f"[LogWatcher] Auto-created task #{task['id']} for {signal}")


_watcher = LogWatcher()


def start_log_watcher():
    _watcher.start()


def stop_log_watcher():
    _watcher.stop()
