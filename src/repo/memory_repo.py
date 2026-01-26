from typing import Optional, List, Dict
from src.repo.interface import UsersRepository, TasksRepository, EventsRepository
from src.domain.user import User
from src.domain.task import Task
from src.domain.event import TaskEvent

class InMemoryUsers(UsersRepository):
    def __init__(self): self._data: Dict[str, User] = {}
    def get(self, user_id: str) -> Optional[User]: return self._data.get(user_id)
    def add(self, user: User) -> None: self._data[user.id] = user

class InMemoryTasks(TasksRepository):
    def __init__(self): self._data: Dict[str, Task] = {}
    def get(self, task_id: str) -> Optional[Task]: return self._data.get(task_id)
    def list(self) -> List[Task]: return list(self._data.values())
    def add(self, task: Task) -> None: self._data[task.id] = task
    def update(self, task: Task) -> None: self._data[task.id] = task

class InMemoryEvents(EventsRepository):
    def __init__(self): self._by_task: Dict[str, List[TaskEvent]] = {}
    def add(self, event: TaskEvent) -> None:
        self._by_task.setdefault(event.task_id, []).append(event)
    def list_for_task(self, task_id: str) -> List[TaskEvent]:
        return list(self._by_task.get(task_id, []))