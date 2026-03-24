def handle_task(task: dict, project_config: dict) -> dict:
    return {
        "changed_files": [],
        "summary": f"Art agent stub ran for task #{task['id']} in project '{task['project_id']}'."
    }