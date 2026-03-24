def classify_task(task_title: str) -> str:

    lower = task_title.lower()

    if any(word in lower for word in ["art", "image", "png", "icon", "design"]):
        return "art"

    if any(word in lower for word in ["bug", "fix", "null", "script", "ui", "logic"]):
        return "code"

    return "general"