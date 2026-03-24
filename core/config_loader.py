import json
from pathlib import Path

PROJECTS_DIR = Path("projects")


def load_project_config(project_id: str) -> dict:
    config_path = PROJECTS_DIR / project_id / "project_config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Missing config for project '{project_id}'")

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def project_exists(project_id: str) -> bool:
    return (PROJECTS_DIR / project_id / "project_config.json").exists()


def list_projects() -> list[str]:
    projects = []
    for item in PROJECTS_DIR.iterdir():
        if item.is_dir() and (item / "project_config.json").exists():
            projects.append(item.name)
    return sorted(projects)