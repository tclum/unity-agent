from pathlib import Path
from core.backup_ops import backup_file


def apply_proposal_file(file_path: str, new_content: str) -> str:
    path = Path(file_path)
    backup_path = backup_file(file_path) if path.exists() else ""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_content, encoding="utf-8")

    return backup_path