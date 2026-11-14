from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

class TaskStatus(str, Enum):
    DRAFT = "draft"
    PLANNED = "planned"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass(frozen=True)
class Task:
    description: str
    task_id: str = ""
    status: TaskStatus = TaskStatus.DRAFT
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValueError("Task description must not be empty.")
