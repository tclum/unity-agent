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


def inspect_scene_context(project_config: dict, pattern: str, context_lines: int = 20, limit: int = 10):
    unity_root = Path(project_config["unity_project_path"])
    results = []

    if not unity_root.exists():
        return results

    for path in unity_root.rglob("*.unity"):
        if should_skip(path):
            continue

        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue

        for i, line in enumerate(lines):
            if pattern.lower() in line.lower():
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)

                snippet = "\n".join(lines[start:end])

                results.append({
                    "file": str(path),
                    "line": i + 1,
                    "match": line.strip(),
                    "snippet": snippet
                })

                if len(results) >= limit:
                    return results

    return results