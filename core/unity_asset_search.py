from pathlib import Path

EXCLUDED_DIRS = {
    ".git",
    "Library",
    "Logs",
    "Temp",
    "Obj",
    "Build",
    "Builds",
    "Packages",
}


def should_skip(path: Path):
    return any(part in EXCLUDED_DIRS for part in path.parts)


def search_unity_assets(project_config: dict, pattern: str, extensions=None, limit=50):
    """
    Searches Unity scenes and prefabs for object references.
    """

    if extensions is None:
        extensions = [".unity", ".prefab"]

    unity_root = Path(project_config["unity_project_path"])
    results = []

    if not unity_root.exists():
        return results

    for ext in extensions:
        for path in unity_root.rglob(f"*{ext}"):

            if should_skip(path):
                continue

            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            lines = text.splitlines()

            for i, line in enumerate(lines, start=1):
                if pattern.lower() in line.lower():

                    results.append({
                        "file": str(path),
                        "line": i,
                        "text": line.strip()
                    })

                    if len(results) >= limit:
                        return results

    return results