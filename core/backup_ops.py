from pathlib import Path
from datetime import datetime


def backup_file(file_path: str) -> str:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Cannot back up missing file: {file_path}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path("outputs/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)

    backup_path = backup_dir / f"{path.name}.{timestamp}.bak"
    backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    return str(backup_path)