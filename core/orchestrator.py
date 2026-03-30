import importlib
import time

from core.task_queue import get_next_task, update_task_status
from core.config_loader import load_project_config
from agents.planner_agent import make_plan
from agents.code_agent import handle_task as handle_code_task
from agents.art_agent import handle_task as handle_art_task
from agents.prefab_agent import handle_task as handle_prefab_task
from agents.qa_agent import review_task_result
from integrations.git_manager import git_checkpoint
from integrations.discord_notifier import send_message
from core.proposal_validator import validate_patch_for_file


def load_project_router(project_id: str):
    module_name = f"projects.{project_id}.task_router"
    return importlib.import_module(module_name)


def process_task(task: dict):
    print(f"\n[Orchestrator] Processing task #{task['id']}: {task['title']}")
    update_task_status(task["id"], "in_progress")

    project_config = load_project_config(task["project_id"])
    router = load_project_router(task["project_id"])

    inferred_type = router.classify_task(task["title"])
    task_type = task["type"] if task["type"] != "general" else inferred_type

    plan = make_plan(task, project_config)
    print("[Planner]")
    for step in plan:
        print(f" - {step}")

    git_checkpoint(project_config, f"agent checkpoint before task {task['id']}")

    if task_type == "art":
        result = handle_art_task(task, project_config)
    elif task_type == "prefab":
        result = handle_prefab_task(task, project_config)
    else:
        result = handle_code_task(task, project_config)

    qa_result = review_task_result(task, result)

    print("[Result]")
    print(result["summary"])
    if task.get("channel_id"):
        send_message(
            task["channel_id"],
            f"Task #{task['id']} result:\n\n{result['summary']}"
        )

    print("[QA]")
    print(qa_result["notes"])
    if task.get("channel_id"):
        send_message(
            task["channel_id"],
            f"Task #{task['id']} completed.\nQA: {qa_result['notes']}"
        )

    update_task_status(task["id"], "done")
    print(f"[Orchestrator] Completed task #{task['id']}")


def run_orchestrator():
    print("[Orchestrator] Started.")
    while True:
        task = get_next_task()
        if task:
            try:
                process_task(task)
            except Exception as e:
                print(f"[Orchestrator] Error: {e}")
                update_task_status(task["id"], "failed")
        time.sleep(5)
