import pytest
from tests.helper import make_service
from src.domain.user import User, Role, Status
from src.domain.event import EventType

class TestCreate:
    def test_create_task_ok(self):
        svc, users, _, events = make_service()
        users.add(User(id="u1", email="u1@example.com", role=Role.USER, status=Status.ACTIVE))

        t = svc.create_task(actor_id="u1", title="Zadanie A", description="opis", priority="NORMAL")
        assert t.title == "Zadanie A"
        assert t.owner_id == "u1"

        evs = events.list_for_task(t.id)
        assert len(evs) == 1
        assert evs[0].type == EventType.CREATED

    def test_create_task_blocked_forbidden(self):
        svc, users, *_ = make_service()
        users.add(User(id="u2", email="u2@example.com", role=Role.USER, status=Status.BLOCKED))
        with pytest.raises(PermissionError):
            svc.create_task(actor_id="u2", title="Nie powinno się udać")

    def test_create_task_invalid_title_raises(self):
        svc, users, *_ = make_service()
        users.add(User(id="u1", email="u1@ex.com", role=Role.USER, status=Status.ACTIVE))
        with pytest.raises(ValueError) as e:
            svc.create_task("u1", "")
        assert str(e.value) == "Invalid title"

    def test_create_task_unknown_priority_raises(self):
        svc, users, *_ = make_service()
        users.add(User(id="u1", email="u1@ex.com", role=Role.USER, status=Status.ACTIVE))
        with pytest.raises(ValueError) as e:
            svc.create_task("u1", "T", priority="NOPE")
        assert str(e.value) == "Unknown priority"

    def test_create_task_actor_missing_forbidden(self):
        svc, *_ = make_service()
        with pytest.raises(PermissionError) as e:
            svc.create_task(actor_id="ghost", title="T")
        assert "User cannot create tasks" in str(e.value)

class TestAssign:
    def test_assign_task_ok_by_manager(self):
        svc, users, _, events = make_service()
        mgr = User(id="m1", email="m@example.com", role=Role.MANAGER, status=Status.ACTIVE)
        dev = User(id="d1", email="d@example.com", role=Role.USER,    status=Status.ACTIVE)
        users.add(mgr); users.add(dev)
        t = svc.create_task(actor_id="m1", title="Fix bug")

        t2 = svc.assign_task(actor_id="m1", task_id=t.id, assignee_id="d1")
        assert t2.assignee_id == "d1"
        assert any(e.type == EventType.ASSIGNED for e in events.list_for_task(t.id))

    def test_assign_task_forbidden_when_not_owner_nor_manager(self):
        svc, users, *_ = make_service()
        owner = User(id="o1", email="o@example.com", role=Role.USER, status=Status.ACTIVE)
        other = User(id="x1", email="x@example.com", role=Role.USER, status=Status.ACTIVE)
        target= User(id="t1", email="t@example.com", role=Role.USER, status=Status.ACTIVE)
        users.add(owner); users.add(other); users.add(target)

        t = svc.create_task(actor_id="o1", title="Sekretne zadanie")
        with pytest.raises(PermissionError):
            svc.assign_task(actor_id="x1", task_id=t.id, assignee_id="t1")

    def test_assign_task_missing_task_raises(self):
        svc, users, *_ = make_service()
        users.add(User(id="owner", email="o@ex.com", role=Role.USER, status=Status.ACTIVE))
        users.add(User(id="assignee", email="a@ex.com", role=Role.USER, status=Status.ACTIVE))
        with pytest.raises(ValueError) as e:
            svc.assign_task(actor_id="owner", task_id="no-such", assignee_id="assignee")
        assert str(e.value) == "Task not found"

    def test_assign_task_missing_actor_or_assignee_raises(self):
        svc, users, *_ = make_service()
        users.add(User(id="owner", email="o@ex.com", role=Role.USER, status=Status.ACTIVE))
        t = svc.create_task("owner", "T")
        with pytest.raises(ValueError) as e:
            svc.assign_task(actor_id="ghost", task_id=t.id, assignee_id="nobody")
        assert str(e.value) == "Actor or assignee not found"

    def test_assign_task_blocked_assignee_forbidden(self):
        svc, users, *_ = make_service()
        mgr = User(id="m", email="m@ex.com", role=Role.MANAGER, status=Status.ACTIVE)
        blocked = User(id="d", email="d@ex.com", role=Role.USER, status=Status.BLOCKED)
        users.add(mgr); users.add(blocked)
        t = svc.create_task("m", "T")
        with pytest.raises(PermissionError) as e:
            svc.assign_task("m", t.id, "d")
        assert "User cannot assign this task" in str(e.value)

    def test_assign_task_event_meta_prev_on_reassign(self):
        svc, users, _, events = make_service()
        m  = User(id="m",  email="m@ex.com", role=Role.MANAGER, status=Status.ACTIVE)
        a1 = User(id="a1", email="a1@ex.com", role=Role.USER,    status=Status.ACTIVE)
        a2 = User(id="a2", email="a2@ex.com", role=Role.USER,    status=Status.ACTIVE)
        users.add(m); users.add(a1); users.add(a2)

        t = svc.create_task("m", "R")
        svc.assign_task("m", t.id, "a1")
        svc.assign_task("m", t.id, "a2")

        evs = [e for e in events.list_for_task(t.id) if e.type == EventType.ASSIGNED]
        assert len(evs) == 2
        assert evs[-1].meta["from"] == "a1"
        assert evs[-1].meta["to"]   == "a2"