import json
from pathlib import Path

PROPOSAL_FILE = Path("storage/proposals.json")


def load_proposals() -> list[dict]:
    if not PROPOSAL_FILE.exists():
        return []

    with open(PROPOSAL_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_proposals(items: list[dict]):
    PROPOSAL_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(PROPOSAL_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)


def add_proposal(
    task_id: int,
    project_id: str,
    file_path: str,
    new_content: str,
    summary: str,
    validation: dict | None = None
) -> dict:

    items = load_proposals()
    next_id = max([p["id"] for p in items], default=0) + 1

    proposal = {
        "id": next_id,
        "task_id": task_id,
        "project_id": project_id,
        "file_path": file_path,
        "new_content": new_content,
        "summary": summary,
        "status": "pending",
        "validation": validation or {
            "is_valid": True,
            "errors": [],
            "warnings": []
        }
    }

    items.append(proposal)
    save_proposals(items)

    return proposal


def get_proposal(proposal_id: int) -> dict | None:
    items = load_proposals()

    for item in items:
        if item["id"] == proposal_id:
            return item

    return None


def update_proposal_status(proposal_id: int, status: str):
    items = load_proposals()

    for item in items:
        if item["id"] == proposal_id:
            item["status"] = status
            break

    save_proposals(items)


def list_proposals(status: str | None = None) -> list[dict]:
    items = load_proposals()

    if status is None:
        return items

    return [item for item in items if item["status"] == status]