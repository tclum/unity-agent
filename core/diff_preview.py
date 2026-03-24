import difflib
from pathlib import Path


def build_diff_preview(file_path: str, new_content: str, max_chars: int = 4000) -> str:
    path = Path(file_path)

    old_content = path.read_text(encoding="utf-8") if path.exists() else ""

    old_lines = old_content.splitlines()
    new_lines = new_content.splitlines()

    diff = list(difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"{path.name} (current)",
        tofile=f"{path.name} (proposed)",
        lineterm=""
    ))

    if not diff:
        return "[No textual diff detected]"

    text = "\n".join(diff)
    return text[:max_chars]