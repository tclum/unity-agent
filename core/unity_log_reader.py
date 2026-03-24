from pathlib import Path

LOG_PATH = Path.home() / "Library/Logs/Unity/Editor.log"

def read_unity_log(lines=300):

    if not LOG_PATH.exists():
        return "Unity log not found."

    try:
        with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
            content = f.readlines()

        return "".join(content[-lines:])

    except Exception as e:
        return f"Failed to read Unity log: {e}"
    
def read_filtered_unity_log(keywords=None, lines=500):

    if keywords is None:
        keywords = ["ResultsUI", "Error", "Exception", "NullReference"]

    raw = read_unity_log(lines)

    filtered = []

    for line in raw.splitlines():
        for k in keywords:
            if k in line:
                filtered.append(line)

    return "\n".join(filtered)