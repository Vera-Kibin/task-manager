from dataclasses import dataclass
from enum import Enum, auto
from datetime import datetime

class EventType(Enum):
    CREATED = auto()
    UPDATED = auto()
    ASSIGNED = auto()
    STATUS_CHANGED = auto()
    DELETED = auto()

@dataclass
class TaskEvent:
    id: str
    task_id: str
    timestamp: datetime
    type: EventType
    meta: dict