from dataclasses import dataclass, asdict


@dataclass
class Task:
    id: int
    project_id: str
    title: str
    type: str = "general"
    status: str = "queued"
    notes: str = ""
    channel_id: int | None = None

    def to_dict(self):
        return asdict(self)