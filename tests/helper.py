from datetime import datetime
from src.serwis.task_service import TaskService
from src.repo.memory_repo import InMemoryUsers, InMemoryTasks, InMemoryEvents

class FakeIdGen:
    def __init__(self):
        self._n = 0
    def new_id(self) -> str:
        self._n += 1
        return f"id-{self._n}"

class FakeClock:
    def __init__(self, fixed: datetime):
        self._fixed = fixed
    def now(self) -> datetime:
        return self._fixed

def make_service():
    users, tasks, events = InMemoryUsers(), InMemoryTasks(), InMemoryEvents()
    idgen = FakeIdGen()
    clock = FakeClock(datetime(2025, 1, 1, 12, 0, 0))
    return TaskService(users, tasks, events, idgen, clock), users, tasks, events