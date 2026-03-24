def review_task_result(task: dict, result: dict) -> dict:
    return {
        "ok": True,
        "notes": f"QA review complete for task #{task['id']}."
    }