import pytest
from src.domain.policies import PermissionPolicy
from src.domain.user import User, Role, Status
from src.domain.task import Task, TaskStatus

class TestPermissionPolicy:
    @staticmethod
    def _u(id, role=Role.USER, status=Status.ACTIVE):
        return User(id=id, email=f"{id}@ex.com", role=role, status=status)

    @staticmethod
    def _t(owner="o"):
        return Task(id="t", title="T", owner_id=owner)

    def test_manager_can_change_status_always_true(self):
        mgr = self._u("m", role=Role.MANAGER)
        task = self._t(owner="x")
        assert PermissionPolicy.can_change_status(mgr, task, TaskStatus.DONE) is True
        assert PermissionPolicy.can_change_status(mgr, task, TaskStatus.IN_PROGRESS) is True
        assert PermissionPolicy.can_change_status(mgr, task, TaskStatus.CANCELED) is True

    def test_can_create_task_blocked_false(self):
        blocked = self._u("u", status=Status.BLOCKED)
        assert PermissionPolicy.can_create_task(blocked) is False

    def test_can_assign_requires_active_assignee_for_manager(self):
        mgr = self._u("m", role=Role.MANAGER)
        task = self._t(owner="x")
        assignee_blocked = self._u("a", status=Status.BLOCKED)
        assert PermissionPolicy.can_assign(mgr, task, assignee_blocked) is False

    def test_can_change_status_user_not_active_false(self):
        actor = self._u("u", status=Status.BLOCKED)
        task = self._t(owner="u")
        assert PermissionPolicy.can_change_status(actor, task, TaskStatus.IN_PROGRESS) is False

    def test_can_delete_owner_done_false_manager_true(self):
        owner = self._u("o")
        manager = self._u("m", role=Role.MANAGER)
        task = self._t(owner="o")
        task.status = TaskStatus.DONE
        assert PermissionPolicy.can_delete(owner, task) is False
        assert PermissionPolicy.can_delete(manager, task) is True