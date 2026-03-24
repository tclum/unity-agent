from pathlib import Path


def replace_once(file_path: str, old: str, new: str) -> bool:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Missing file: {file_path}")

    content = path.read_text(encoding="utf-8")

    if old not in content:
        return False

    updated = content.replace(old, new, 1)
    path.write_text(updated, encoding="utf-8")
    return True