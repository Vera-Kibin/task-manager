import pytest
from tests.helper import make_service
from src.domain.user import User, Role, Status
from src.domain.task import TaskStatus
from src.domain.event import EventType

class TestStatus:
    def test_change_status_happy_path(self):
        svc, users, _, events = make_service()
        mgr = User(id="m1", email="m@example.com", role=Role.MANAGER, status=Status.ACTIVE)
        dev = User(id="d1", email="d1@example.com", role=Role.USER, status=Status.ACTIVE)
        users.add(mgr); users.add(dev)

        t = svc.create_task("m1", "Implement feature")
        svc.assign_task("m1", t.id, "d1")

        t = svc.change_status("d1", t.id, "IN_PROGRESS")
        assert t.status == TaskStatus.IN_PROGRESS

        t = svc.change_status("d1", t.id, "DONE")
        assert t.status == TaskStatus.DONE

        kinds = [e.type for e in events.list_for_task(t.id)]
        assert kinds.count(EventType.STATUS_CHANGED) == 2

    def test_change_status_forbidden_actor(self):
        svc, users, *_ = make_service()
        owner = User(id="o1", email="o@example.com", role=Role.USER, status=Status.ACTIVE)
        other = User(id="x1", email="x@example.com", role=Role.USER, status=Status.ACTIVE)
        users.add(owner); users.add(other)
        t = svc.create_task("o1", "Task")
        with pytest.raises(PermissionError):
            svc.change_status("x1", t.id, "DONE")

    def test_change_status_invalid_transition_raises(self):
        svc, users, *_ = make_service()
        dev = User(id="d1", email="d@example.com", role=Role.USER, status=Status.ACTIVE)
        users.add(dev)
        t = svc.create_task("d1", "Zadanie")
        with pytest.raises(ValueError):
            svc.change_status("d1", t.id, "DONE")

    def test_change_status_missing_task_raises(self):
        svc, users, *_ = make_service()
        users.add(User(id="u1", email="u1@ex.com", role=Role.USER, status=Status.ACTIVE))
        with pytest.raises(ValueError) as e:
            svc.change_status("u1", "nope", "IN_PROGRESS")
        assert str(e.value) == "Task not found"

    def test_change_status_missing_actor_raises(self):
        svc, users, *_ = make_service()
        users.add(User(id="owner", email="o@ex.com", role=Role.USER, status=Status.ACTIVE))
        t = svc.create_task("owner", "T")
        with pytest.raises(ValueError) as e:
            svc.change_status("ghost", t.id, "IN_PROGRESS")
        assert str(e.value) == "Actor not found"

    def test_change_status_unknown_status_raises(self):
        svc, users, *_ = make_service()
        users.add(User(id="owner", email="o@ex.com", role=Role.USER, status=Status.ACTIVE))
        t = svc.create_task("owner", "T")
        with pytest.raises(ValueError) as e:
            svc.change_status("owner", t.id, "WHAT_IS_THIS")
        assert str(e.value) == "Unknown status"

    def test_change_status_done_forbidden_for_owner_not_assignee(self):
        svc, users, *_ = make_service()
        owner = User(id="o1", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        assgn = User(id="a1", email="a@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(owner); users.add(assgn)
        t = svc.create_task("o1", "T")
        svc.assign_task("o1", t.id, "a1")
        svc.change_status("a1", t.id, "IN_PROGRESS")
        with pytest.raises(PermissionError) as e:
            svc.change_status("o1", t.id, "DONE")
        assert "User cannot change status for this task" in str(e.value)

    def test_change_status_forbidden_when_actor_blocked_even_if_assignee(self):
        svc, users, *_ = make_service()
        m = User(id="m1", email="m@ex.com", role=Role.MANAGER, status=Status.ACTIVE)
        d = User(id="d1", email="d@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(m); users.add(d)
        t = svc.create_task("m1", "Feature")
        svc.assign_task("m1", t.id, "d1")
        d.status = Status.BLOCKED
        with pytest.raises(PermissionError) as e:
            svc.change_status("d1", t.id, "IN_PROGRESS")
        assert "User cannot change status for this task" in str(e.value)

    def test_change_status_manager_can_cancel_anytime(self):
        svc, users, _, events = make_service()
        m = User(id="m", email="m@ex.com", role=Role.MANAGER, status=Status.ACTIVE)
        users.add(m)
        t = svc.create_task("m", "X")
        t = svc.change_status("m", t.id, "CANCELED")
        assert t.status == TaskStatus.CANCELED
        assert any(e.type == EventType.STATUS_CHANGED for e in events.list_for_task(t.id))