from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional
from datetime import datetime

class TaskStatus(Enum):
    NEW = auto()
    IN_PROGRESS = auto()
    DONE = auto()
    CANCELED = auto()

class Priority(Enum):
    LOW = auto()
    NORMAL = auto()
    HIGH = auto()

@dataclass
class Task:
    id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.NEW
    priority: Priority = Priority.NORMAL
    owner_id: str = ""
    assignee_id: Optional[str] = None
    due_date: Optional[datetime] = None
    is_deleted: bool = False

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Task.id must be non-empty")
        if not isinstance(self.title, str) or not self.title.strip() or len(self.title) > 200:
            raise ValueError("Invalid title")
        if not isinstance(self.priority, Priority):
            raise ValueError("priority must be Priority enum")
        if not isinstance(self.status, TaskStatus):
            raise ValueError("status must be TaskStatus enum")
        if not isinstance(self.owner_id, str) or not self.owner_id.strip():
            raise ValueError("owner_id must be non-empty")
        if self.due_date is not None and not isinstance(self.due_date, datetime):
            raise ValueError("due_date must be datetime or None")