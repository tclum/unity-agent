import threading

from core.orchestrator import run_orchestrator
from integrations.discord_bot import run_bot


if __name__ == "__main__":
    worker = threading.Thread(target=run_orchestrator, daemon=True)
    worker.start()
    run_bot()