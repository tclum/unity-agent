import subprocess
from pathlib import Path


def git_commit_files(project_config: dict, file_paths: list[str], message: str):
    unity_project_path = project_config.get("unity_project_path")
    if not unity_project_path:
        print("[Git] No unity_project_path set. Skipping commit.")
        return

    repo_path = Path(unity_project_path)

    if not repo_path.exists():
        print(f"[Git] Project path does not exist: {repo_path}. Skipping commit.")
        return

    git_dir = repo_path / ".git"
    if not git_dir.exists():
        print(f"[Git] Not a git repo: {repo_path}. Skipping commit.")
        return

    if not file_paths:
        print("[Git] No file paths provided. Skipping commit.")
        return

    for file_path in file_paths:
        subprocess.run(["git", "-C", str(repo_path), "add", file_path], check=False)

    subprocess.run(["git", "-C", str(repo_path), "commit", "-m", message], check=False)


def git_checkpoint(project_config: dict, message: str):
    print("[Git] Pre-task checkpoint disabled in approval mode.")