import time
import threading
from pathlib import Path

from core.task_queue import add_task
from core.project_manager import get_active_project
from core.config_loader import load_project_config

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

# How often to scan for new PNG assets (seconds)
PNG_SCAN_INTERVAL = 15


def fix_png_meta_as_sprite(meta_path: Path) -> bool:
    """
    Ensure a PNG .meta file has textureType=8 (Sprite) and spriteMode=1 (Single).
    Returns True if changes were made.
    """
    try:
        content = meta_path.read_text(encoding="utf-8")
        original = content

        if "textureType: 0" in content:
            content = content.replace("textureType: 0", "textureType: 8")
        if "spriteMode: 0" in content:
            content = content.replace("spriteMode: 0", "spriteMode: 1")

        if content != original:
            meta_path.write_text(content, encoding="utf-8")
            return True
    except Exception as e:
        print(f"[PNGWatcher] Failed to fix meta for {meta_path}: {e}")
    return False


class PNGWatcher:
    """
    Watches Unity Art folders for new PNG files and automatically
    sets their texture type to Sprite in the .meta file.
    """
    def __init__(self):
        self._seen: set[str] = set()
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self, project_config: dict):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, args=(project_config,), daemon=True
        )
        self._thread.start()
        print("[PNGWatcher] Started — watching for new PNG assets.")

    def stop(self):
        self._running = False

    def _run(self, project_config: dict):
        unity_root = Path(project_config["unity_project_path"])
        art_dir = unity_root / "Assets" / "Art"

        # Seed seen set with existing files on startup
        if art_dir.exists():
            for meta in art_dir.rglob("*.png.meta"):
                self._seen.add(str(meta))

        while self._running:
            try:
                self._check_for_new_pngs(art_dir)
            except Exception as e:
                print(f"[PNGWatcher] Error: {e}")
            time.sleep(PNG_SCAN_INTERVAL)

    def _check_for_new_pngs(self, art_dir: Path):
        if not art_dir.exists():
            return

        for meta_path in art_dir.rglob("*.png.meta"):
            meta_str = str(meta_path)
            if meta_str in self._seen:
                continue

            # New PNG detected
            self._seen.add(meta_str)
            png_name = meta_path.stem  # removes .meta, leaves .png
            print(f"[PNGWatcher] New PNG detected: {png_name}")

            changed = fix_png_meta_as_sprite(meta_path)
            if changed:
                print(f"[PNGWatcher] Auto-fixed sprite import type for {png_name}")
            else:
                print(f"[PNGWatcher] {png_name} already configured as sprite")


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

        # Seed position at end of current log so we only catch NEW errors
        if LOG_PATH.exists():
            self._last_size = LOG_PATH.stat().st_size

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

        # Skip generic errors with no useful file/object context
        lower_line = line.lower()
        if "object reference not set to an instance" in lower_line and \
           "at " not in lower_line and "script" not in lower_line:
            return

        # Require minimum context length to be actionable
        context = line.strip()
        if len(context) < 60:
            return

        with self._lock:
            last_seen = self._seen_errors.get(signal, 0)
            if now - last_seen < ERROR_COOLDOWN:
                return
            self._seen_errors[signal] = now

        project_id = get_active_project()
        if not project_id:
            return

        task_title = f"auto: {signal} detected — {context[:120]}"

        task = add_task(
            project_id=project_id,
            title=task_title,
            channel_id=None,
        )

        print(f"[LogWatcher] Auto-created task #{task['id']} for {signal}")


_log_watcher = LogWatcher()
_png_watcher = PNGWatcher()


def start_log_watcher():
    _log_watcher.start()


def start_png_watcher(project_config: dict):
    _png_watcher.start(project_config)


def stop_log_watcher():
    _log_watcher.stop()
    _png_watcher.stop()
