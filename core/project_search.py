from pathlib import Path


EXCLUDED_DIR_NAMES = {
    ".git",
    "Library",
    "Logs",
    "Temp",
    "Obj",
    "Build",
    "Builds",
    "Packages",
}


def should_skip(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def search_project_code(project_config: dict, pattern: str, extensions=None, limit: int = 50):
    if extensions is None:
        extensions = [".cs"]

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
                if pattern in line:
                    results.append({
                        "file": str(path),
                        "line": i,
                        "text": line.strip()
                    })

                    if len(results) >= limit:
                        return results

    return results