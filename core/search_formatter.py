def format_search_results(title: str, results: list[dict]) -> str:
    lines = [title]

    if not results:
        lines.append("No matches found.")
        return "\n".join(lines)

    for item in results:
        lines.append(f"{item['file']}:{item['line']}")
        lines.append(f"  {item['text']}")

    return "\n".join(lines)