def make_plan(task: dict, project_config: dict) -> list[str]:
    return [
        f"Understand task: {task['title']}",
        f"Use project: {project_config.get('name', task['project_id'])}",
        "Identify relevant files or assets",
        "Prepare safe changes",
        "Review output and summarize results",
    ]