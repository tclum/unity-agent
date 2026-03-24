def format_asset_search(title: str, results: list[dict]):

    lines = [title]

    if not results:
        lines.append("No matches found.")
        return "\n".join(lines)

    for r in results:
        lines.append(f"{r['file']}:{r['line']}")
        lines.append(f"  {r['text']}")

    return "\n".join(lines)