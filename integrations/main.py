import threading

from core.orchestrator import run_orchestrator
from core.log_watcher import start_log_watcher
from integrations.discord_bot import run_bot


if __name__ == "__main__":
    worker = threading.Thread(target=run_orchestrator, daemon=True)
    worker.start()

    start_log_watcher()

    run_bot()
