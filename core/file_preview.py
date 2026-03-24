from pathlib import Path


def read_preview(file_path: str, max_lines: int = 80) -> str:
    path = Path(file_path)

    if not path.exists():
        return f"[Missing file] {file_path}"

    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        return f"[Read error] {file_path}: {e}"

    preview = "".join(lines[:max_lines]).strip()
    return preview