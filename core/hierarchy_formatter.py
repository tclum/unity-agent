def format_hierarchy_results(title: str, results: list[dict]) -> str:
    lines = [title]

    if not results:
        lines.append("No scene matches found.")
        return "\n".join(lines)

    for item in results:
        lines.append("")
        lines.append(f"{item['file']}:{item['line']}")
        lines.append(f"Match: {item['match']}")
        lines.append("Context:")
        lines.append(item["snippet"][:2500])

    return "\n".join(lines)