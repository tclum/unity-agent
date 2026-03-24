import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

STATE_FILE = Path("storage/runtime_state.json")
DEFAULT_PROJECT = os.getenv("DEFAULT_PROJECT", "default")


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {"active_project": DEFAULT_PROJECT}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"active_project": DEFAULT_PROJECT}


def _save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def set_active_project(project_id: str):
    state = _load_state()
    state["active_project"] = project_id
    _save_state(state)


def get_active_project() -> str:
    state = _load_state()
    return state.get("active_project", DEFAULT_PROJECT)