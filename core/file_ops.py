from pathlib import Path


def is_allowed(project_config: dict, relative_path: str) -> bool:
    allowed_paths = project_config.get("allowed_paths", [])
    return any(relative_path.startswith(p) for p in allowed_paths)


def get_full_path(project_config: dict, relative_path: str) -> Path:
    if not is_allowed(project_config, relative_path):
        raise ValueError(f"Path not allowed: {relative_path}")

    unity_root = Path(project_config["unity_project_path"])
    return unity_root / relative_path


def read_text(project_config: dict, relative_path: str) -> str:
    path = get_full_path(project_config, relative_path)
    return path.read_text(encoding="utf-8")


def write_text(project_config: dict, relative_path: str, content: str):
    path = get_full_path(project_config, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")