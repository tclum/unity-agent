from core.unity_hierarchy_inspector import inspect_scene_context


def get_scene_context_for_task(project_config: dict, task_title: str) -> str:
    lower = task_title.lower()

    targets = []
    if "results" in lower:
        targets.append("ResultsUI")
        targets.append("ResultsPanel")
    if "confirm" in lower:
        targets.append("ConfirmButton")
    if "transition" in lower:
        targets.append("TurnTransitionPanel")

    snippets = []

    for target in targets[:3]:
        results = inspect_scene_context(
            project_config,
            target,
            context_lines=12,
            limit=1
        )
        for item in results:
            snippets.append(
                f"[{target}] {item['file']}:{item['line']}\n{item['snippet']}"
            )

    return "\n\n".join(snippets)