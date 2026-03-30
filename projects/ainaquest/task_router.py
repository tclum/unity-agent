def classify_task(task_title: str) -> str:
    lower = task_title.lower()

    # Prefab/asset signals — check FIRST before art signals
    # "assign artwork" is a prefab operation, not an art creation task
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

    # Art signals — generative/creative art tasks only
    art_signals = [
        "generate card art",
        "create card art",
        "generate artwork",
        "create artwork",
        "card illustration",
        "card frame",
        "card icon",
        "card back ",
        "card back.",
        "card back,",
        "illustration",
        "design asset",
        "generate art",
        "create art",
        "draw",
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

    # Prefab checked first — "assign artwork" beats "artwork" alone
    if any(signal in lower for signal in prefab_signals):
        return "prefab"

    if any(signal in lower for signal in art_signals):
        return "art"

    if any(signal in lower for signal in code_signals):
        return "code"

    return "general"
