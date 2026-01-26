from dataclasses import dataclass
from enum import Enum, auto
import re

class Role(Enum):
    USER = auto()
    MANAGER = auto()

class Status(Enum):
    ACTIVE = auto()
    BLOCKED = auto()

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

@dataclass
class User:
    id: str
    email: str
    role: Role
    status: Status

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("User.id must be non-empty")
        if not isinstance(self.role, Role):
            raise ValueError("role must be Role enum")
        if not isinstance(self.status, Status):
            raise ValueError("status must be Status enum")
        if not isinstance(self.email, str) or not _EMAIL_RE.match(self.email):
            raise ValueError("invalid email")