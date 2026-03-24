def classify_task(task_title: str) -> str:

    lower = task_title.lower()

    if any(word in lower for word in [
        "card art",
        "png",
        "design",
        "card back",
        "frame",
        "icon"
    ]):
        return "art"

    if any(word in lower for word in [
        "card",
        "plant",
        "score",
        "results",
        "turn",
        "ui",
        "bug",
        "fix",
        "null"
    ]):
        return "code"

    return "general"