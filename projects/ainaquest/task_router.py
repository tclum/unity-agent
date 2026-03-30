def classify_task(task_title: str) -> str:
    lower = task_title.lower()

    # Art signals — use whole-word or unambiguous phrases only
    art_signals = [
        "card art",
        "card artwork",
        "card image",
        "card sprite",
        "card texture",
        "card illustration",
        "card frame",
        "card icon",
        "card back ",
        "card back.",
        "card back,",
        "png",
        "sprite",
        "artwork",
        "illustration",
        "design asset",
    ]

    # Prefab/asset signals
    prefab_signals = [
        "assign",
        "wire up",
        "wire the",
        "inspector",
        "prefab",
        "scriptable",
        "card data",
        "base points",
        "card type",
        "effect type",
        "assign artwork",
        "assign sprite",
        "set points",
        "set description",
    ]

    # Code signals
    code_signals = [
        "card",
        "plant",
        "score",
        "results",
        "turn",
        "ui",
        "bug",
        "fix",
        "null",
        "background",
        "color",
        "colour",
        "green",
        "button",
        "panel",
        "text",
        "animation",
    ]

    if any(signal in lower for signal in art_signals):
        return "art"

    if any(signal in lower for signal in prefab_signals):
        return "prefab"

    if any(signal in lower for signal in code_signals):
        return "code"

    return "general"
