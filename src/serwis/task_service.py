from typing import List, Optional
from src.domain.user import Role
from src.domain.task import Task, TaskStatus, Priority
from src.domain.event import TaskEvent, EventType
from src.domain.policies import PermissionPolicy
from src.repo.interface import UsersRepository, TasksRepository, EventsRepository
from src.utils.idgen import IdGenerator
from src.utils.clock import Clock

class TaskService:
    def __init__(self, users: UsersRepository, tasks: TasksRepository, events: EventsRepository, idgen: IdGenerator, clock: Clock):
        self.users = users
        self.tasks = tasks
        self.events = events
        self.idgen = idgen
        self.clock = clock

    # def create_task(self, actor_id: str, title: str, description: str="", priority: str="NORMAL") -> Task:
    #     actor = self.users.get(actor_id)
    #     if not actor or not PermissionPolicy.can_create_task(actor):
    #         raise PermissionError("User cannot create tasks")
    #     if not title or len(title) > 200:
    #         raise ValueError("Invalid title")
    #     pr = Priority[priority]
    #     t = Task(id=self.idgen.new_id(), title=title, description=description, priority=pr, owner_id=actor.id)
    #     self.tasks.add(t)
    #     self.events.add(TaskEvent(self.idgen.new_id(), t.id, self.clock.now(), EventType.CREATED, {"owner": actor.id}))
    #     return t

    def create_task(self, actor_id: str, title: str, description: str = "", priority: str = "NORMAL") -> Task:
        actor = self.users.get(actor_id)
        if not actor or not PermissionPolicy.can_create_task(actor):
            raise PermissionError("User cannot create tasks")
        if not title or len(title) > 200:
            raise ValueError("Invalid title")
        try:
            pr = Priority[priority.upper()]
        except KeyError:
            raise ValueError("Unknown priority")
        t = Task(
            id=self.idgen.new_id(),
            title=title,
            description=description,
            priority=pr,
            owner_id=actor.id,
        )
        self.tasks.add(t)
        self.events.add(TaskEvent(
            self.idgen.new_id(), t.id, self.clock.now(), EventType.CREATED, {"owner": actor.id}
        ))
        return t

    def _is_valid_transition(self, current: TaskStatus, new: TaskStatus) -> bool:
            allowed = {
                TaskStatus.NEW:         {TaskStatus.IN_PROGRESS, TaskStatus.CANCELED},
                TaskStatus.IN_PROGRESS: {TaskStatus.DONE, TaskStatus.CANCELED},
                TaskStatus.DONE:        set(),
                TaskStatus.CANCELED:    set(),
            }
            return new in allowed.get(current, set())
    
    def assign_task(self, actor_id: str, task_id: str, assignee_id: str) -> Task:
        actor = self.users.get(actor_id)
        task  = self.tasks.get(task_id)
        assignee = self.users.get(assignee_id)

        if not task:
            raise ValueError("Task not found")
        if not actor or not assignee:
            raise ValueError("Actor or assignee not found")

        if not PermissionPolicy.can_assign(actor, task, assignee):
            raise PermissionError("User cannot assign this task")

        prev = task.assignee_id
        task.assignee_id = assignee.id
        self.tasks.update(task)

        self.events.add(TaskEvent(
            id=self.idgen.new_id(),
            task_id=task.id,
            timestamp=self.clock.now(),
            type=EventType.ASSIGNED,
            meta={"from": prev, "to": assignee.id, "by": actor.id},
        ))
        return task

    def change_status(self, actor_id: str, task_id: str, new_status: str) -> Task:
        actor = self.users.get(actor_id)
        task  = self.tasks.get(task_id)
        if not task:
            raise ValueError("Task not found")
        if not actor:
            raise ValueError("Actor not found")

        try:
            target = TaskStatus[new_status.upper()]
        except KeyError:
            raise ValueError("Unknown status")
        has_basic_access = (
            actor.role == Role.MANAGER or actor.id in (task.owner_id, task.assignee_id)
        )
        if not has_basic_access:
            raise PermissionError("User cannot change status for this task")
        if not self._is_valid_transition(task.status, target):
            raise ValueError(f"Invalid status transition: {task.status.name} -> {target.name}")
        if not PermissionPolicy.can_change_status(actor, task, target):
            raise PermissionError("User cannot change status for this task")

        prev = task.status
        task.status = target
        self.tasks.update(task)

        self.events.add(TaskEvent(
            id=self.idgen.new_id(),
            task_id=task.id,
            timestamp=self.clock.now(),
            type=EventType.STATUS_CHANGED,
            meta={"from": prev.name, "to": target.name, "by": actor.id},
        ))
        return task
    
    # --- UPDATE ---
    def update_task(
        self,
        actor_id: str,
        task_id: str,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> Task:
        actor = self.users.get(actor_id)
        task  = self.tasks.get(task_id)
        if not actor or not task:
            raise ValueError("Actor or task not found")
        if actor.role != Role.MANAGER:
            if task.status in (TaskStatus.DONE, TaskStatus.CANCELED):
                raise PermissionError("Cannot update finished/canceled task")
            if actor.id not in (task.owner_id, task.assignee_id):
                raise PermissionError("User cannot update this task")

        changes = {}

        if title is not None:
            if not title or len(title) > 200:
                raise ValueError("Invalid title")
            if title != task.title:
                changes["title"] = {"from": task.title, "to": title}
                task.title = title

        if description is not None and description != task.description:
            changes["description"] = {"from": task.description, "to": description}
            task.description = description

        if priority is not None:
            try:
                pr = Priority[priority.upper()]
            except KeyError:
                raise ValueError("Unknown priority")
            if pr != task.priority:
                changes["priority"] = {"from": task.priority.name, "to": pr.name}
                task.priority = pr

        if not changes:
            return task

        self.tasks.update(task)
        self.events.add(TaskEvent(
            id=self.idgen.new_id(),
            task_id=task.id,
            timestamp=self.clock.now(),
            type=EventType.UPDATED,
            meta={"by": actor.id, "changes": changes},
        ))
        return task
    
    # --- DELETE ---
    def delete_task(self, actor_id: str, task_id: str) -> Task:
        actor = self.users.get(actor_id)
        task  = self.tasks.get(task_id)
        if not actor or not task:
            raise ValueError("Actor or task not found")
        if actor.role != Role.MANAGER:
            if actor.id != task.owner_id:
                raise PermissionError("Only owner can delete")
            if task.status == TaskStatus.DONE:
                raise PermissionError("Owner cannot delete DONE task")

        if getattr(task, "is_deleted", False):
            return task
        
        task.is_deleted = True
        self.tasks.update(task)
        self.events.add(TaskEvent(
            id=self.idgen.new_id(),
            task_id=task.id,
            timestamp=self.clock.now(),
            type=EventType.DELETED,
            meta={"by": actor.id},
        ))
        return task
    
    # --- LIST ---
    def list_tasks(
        self,
        actor_id: str,
        *,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> List[Task]:
        actor = self.users.get(actor_id)
        if not actor:
            raise ValueError("Actor not found")
        all_tasks: List[Task] = self.tasks.list() 
        visible = (
            all_tasks
            if actor.role == Role.MANAGER
            else [t for t in all_tasks if actor.id in (t.owner_id, t.assignee_id)]
        )
        visible = [t for t in visible if not getattr(t, "is_deleted", False)]
        if status is not None:
            try:
                st = TaskStatus[status.upper()]
            except KeyError:
                raise ValueError("Unknown status filter")
            visible = [t for t in visible if t.status == st]

        if priority is not None:
            try:
                pr = Priority[priority.upper()]
            except KeyError:
                raise ValueError("Unknown priority filter")
            visible = [t for t in visible if t.priority == pr]

        return visible

    # --- EVENTS ---
    def get_events(self, actor_id: str, task_id: str) -> List[TaskEvent]:
        actor = self.users.get(actor_id)
        task  = self.tasks.get(task_id)
        if not actor or not task:
            raise ValueError("Actor or task not found")

        if actor.role != Role.MANAGER and actor.id not in (task.owner_id, task.assignee_id):
            raise PermissionError("User cannot view events of this task")

        return self.events.list_for_task(task_id)