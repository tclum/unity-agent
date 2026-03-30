import threading

from core.orchestrator import run_orchestrator
from core.log_watcher import start_log_watcher, start_png_watcher
from core.config_loader import load_project_config
from core.project_manager import get_active_project
from integrations.discord_bot import run_bot


if __name__ == "__main__":
    worker = threading.Thread(target=run_orchestrator, daemon=True)
    worker.start()

    start_log_watcher()

    # Start PNG watcher for active project
    try:
        project_id = get_active_project()
        if project_id:
            project_config = load_project_config(project_id)
            start_png_watcher(project_config)
    except Exception as e:
        print(f"[Main] PNG watcher failed to start: {e}")

    run_bot()
