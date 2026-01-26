from abc import ABC, abstractmethod
from typing import List, Optional
from src.domain.user import User
from src.domain.task import Task
from src.domain.event import TaskEvent

class UsersRepository(ABC):
    @abstractmethod
    def get(self, user_id: str) -> Optional[User]: ...
    @abstractmethod
    def add(self, user: User) -> None: ...

class TasksRepository(ABC):
    @abstractmethod
    def get(self, task_id: str) -> Optional[Task]: ...
    @abstractmethod
    def list(self) -> List[Task]: ...
    @abstractmethod
    def add(self, task: Task) -> None: ...
    @abstractmethod
    def update(self, task: Task) -> None: ...

class EventsRepository(ABC):
    @abstractmethod
    def add(self, event: TaskEvent) -> None: ...
    @abstractmethod
    def list_for_task(self, task_id: str) -> list[TaskEvent]: ...