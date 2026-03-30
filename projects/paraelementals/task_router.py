def classify_task(task_title: str) -> str:
    lower = task_title.lower()

    # Prefab/asset signals
    prefab_signals = [
        "assign",
        "wire up",
        "wire the",
        "inspector",
        "prefab",
        "scriptable",
        "item data",
        "set damage",
        "set health",
        "set speed",
        "assign sprite",
        "set description",
    ]

    # Art signals — generative/creative only
    art_signals = [
        "generate art",
        "create art",
        "draw",
        "illustration",
        "design asset",
    ]

    # Code signals — side-scroller specific + general
    code_signals = [
        "player",
        "enemy",
        "combat",
        "health",
        "damage",
        "attack",
        "jump",
        "move",
        "collision",
        "hitbox",
        "spawn",
        "inventory",
        "item",
        "pickup",
        "camera",
        "follow",
        "ui",
        "bug",
        "fix",
        "null",
        "animation",
        "controller",
        "respawn",
        "loot",
        "resource",
        "gather",
        "interact",
        "room",
        "scroll",
        "sidescroll",
    ]

    if any(signal in lower for signal in prefab_signals):
        return "prefab"

    if any(signal in lower for signal in art_signals):
        return "art"

    if any(signal in lower for signal in code_signals):
        return "code"

    return "general"
