from .user import User, Role, Status
from .task import Task, TaskStatus

class PermissionPolicy:
    @staticmethod
    def can_create_task(actor: User) -> bool:
        return actor.status == Status.ACTIVE

    @staticmethod
    def can_assign(actor: User, task: Task, assignee: User) -> bool:
        if actor.role == Role.MANAGER:
            return assignee.status == Status.ACTIVE
        return (
            actor.status == Status.ACTIVE
            and actor.id == task.owner_id
            and assignee.status == Status.ACTIVE
        )

    @staticmethod
    def can_change_status(actor: User, task: Task, target: TaskStatus) -> bool:
        if actor.role == Role.MANAGER:
            return True
        if actor.status != Status.ACTIVE:
            return False
        if target == TaskStatus.DONE:
            return actor.id == task.assignee_id
        return actor.id in (task.owner_id, task.assignee_id)
    
    @staticmethod
    def can_delete(actor: User, task: Task) -> bool:
        if actor.role == Role.MANAGER:
            return True
        return actor.id == task.owner_id and task.status != TaskStatus.DONE