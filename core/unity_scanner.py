from pathlib import Path


EXCLUDED_PARTS = [
    "Assets/TextMesh Pro",
    "Assets/Plugins",
    "Assets/ThirdParty",
    "Assets/Third Party",
    "Packages",
    "Library",
]


def is_excluded(path: Path) -> bool:
    path_str = str(path).replace("\\", "/")
    return any(excluded in path_str for excluded in EXCLUDED_PARTS)


def find_relevant_files(project_config: dict, keywords: list[str]):
    unity_root = Path(project_config["unity_project_path"])
    assets_dir = unity_root / "Assets"

    results = []

    if not assets_dir.exists():
        return results

    for path in assets_dir.rglob("*.cs"):
        if is_excluded(path):
            continue

        name = path.name.lower()
        parent = str(path.parent).lower()

        score = 0
        for k in keywords:
            if k in name:
                score += 3
            if k in parent:
                score += 1

        if score > 0:
            results.append((score, str(path)))

    results.sort(key=lambda x: (-x[0], x[1]))
    return [path for _, path in results[:10]]