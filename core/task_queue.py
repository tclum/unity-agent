import json
from pathlib import Path
from core.models import Task

TASK_FILE = Path("storage/tasks.json")


def load_tasks() -> list[dict]:
    if not TASK_FILE.exists():
        return []

    with open(TASK_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tasks(tasks: list[dict]):
    TASK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TASK_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)


def add_task(project_id: str, title: str, task_type: str = "general", notes: str = "", channel_id: int | None = None) -> dict:
    tasks = load_tasks()
    next_id = max([t["id"] for t in tasks], default=0) + 1

    task = Task(
        id=next_id,
        project_id=project_id,
        title=title,
        type=task_type,
        status="queued",
        notes=notes,
        channel_id=channel_id,
    ).to_dict()

    tasks.append(task)
    save_tasks(tasks)
    return task

def get_next_task() -> dict | None:
    tasks = load_tasks()
    for task in tasks:
        if task["status"] == "queued":
            return task
    return None


def update_task_status(task_id: int, status: str):
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = status
            break
    save_tasks(tasks)


def get_task_by_id(task_id: int) -> dict | None:
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            return task
    return None