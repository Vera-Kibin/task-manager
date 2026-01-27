import pytest
from tests.helper import make_service
from src.domain.user import User, Role, Status
from src.domain.event import EventType

class TestUpdate:
    def test_update_task_ok_by_owner_changes_title_and_priority(self):
        svc, users, _, events = make_service()
        owner = User(id="u1", email="u1@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(owner)
        t = svc.create_task("u1", "Old", "desc", "NORMAL")

        t2 = svc.update_task("u1", t.id, title="New", priority="HIGH")
        assert t2.title == "New"
        assert t2.priority.name == "HIGH"
        assert any(e.type == EventType.UPDATED for e in events.list_for_task(t.id))

    def test_update_task_forbidden_when_done(self):
        svc, users, *_ = make_service()
        owner = User(id="o1", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        assgn = User(id="a1", email="a@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(owner); users.add(assgn)
        t = svc.create_task("o1", "T")
        svc.assign_task("o1", t.id, "a1")
        svc.change_status("a1", t.id, "IN_PROGRESS")
        svc.change_status("a1", t.id, "DONE")
        with pytest.raises(PermissionError):
            svc.update_task("o1", t.id, title="cant-change")

    def test_update_task_actor_not_found_raises(self):
        svc, users, *_ = make_service()
        owner = User(id="u1", email="u1@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(owner)
        t = svc.create_task("u1", "T")
        with pytest.raises(ValueError) as e:
            svc.update_task("ghost", t.id, title="X")
        assert str(e.value) == "Actor or task not found"

    def test_update_task_task_not_found_raises(self):
        svc, users, *_ = make_service()
        owner = User(id="u1", email="u1@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(owner)
        with pytest.raises(ValueError) as e:
            svc.update_task("u1", "nope", title="X")
        assert str(e.value) == "Actor or task not found"

    def test_update_task_invalid_title_raises(self):
        svc, users, *_ = make_service()
        o = User(id="o", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(o)
        t = svc.create_task("o", "Ok")
        with pytest.raises(ValueError) as e:
            svc.update_task("o", t.id, title="")
        assert str(e.value) == "Invalid title"

    def test_update_task_unknown_priority_raises(self):
        svc, users, *_ = make_service()
        o = User(id="o", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(o)
        t = svc.create_task("o", "Ok")
        with pytest.raises(ValueError) as e:
            svc.update_task("o", t.id, priority="ULTRA")
        assert str(e.value) == "Unknown priority"

    def test_update_task_no_changes_no_event(self):
        svc, users, _, events = make_service()
        o = User(id="o", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(o)
        t = svc.create_task("o", "Ok", "d", "NORMAL")
        before = len(events.list_for_task(t.id))
        t2 = svc.update_task("o", t.id)  # brak zmian
        after = len(events.list_for_task(t.id))
        assert t2.id == t.id
        assert before == after

    def test_update_task_forbidden_when_not_owner_nor_assignee(self):
        svc, users, *_ = make_service()
        o = User(id="o", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        x = User(id="x", email="x@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(o); users.add(x)
        t = svc.create_task("o", "Ok")
        with pytest.raises(PermissionError) as e:
            svc.update_task("x", t.id, title="New")
        assert "User cannot update this task" in str(e.value)

    def test_update_task_manager_can_update_done(self):
        svc, users, _, events = make_service()
        m = User(id="m", email="m@ex.com", role=Role.MANAGER, status=Status.ACTIVE)
        d = User(id="d", email="d@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(m); users.add(d)
        t = svc.create_task("m", "Ok")
        svc.assign_task("m", t.id, "d")
        svc.change_status("d", t.id, "IN_PROGRESS")
        svc.change_status("d", t.id, "DONE")
        t2 = svc.update_task("m", t.id, description="after-done")
        assert t2.description == "after-done"
        assert any(e.type == EventType.UPDATED for e in events.list_for_task(t.id))

class TestDelete:
    def test_delete_task_owner_cannot_delete_done_but_manager_can(self):
        svc, users, _, events = make_service()
        owner = User(id="o1", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        assgn = User(id="a1", email="a@ex.com", role=Role.USER, status=Status.ACTIVE)
        mgr   = User(id="m1", email="m@ex.com", role=Role.MANAGER, status=Status.ACTIVE)
        users.add(owner); users.add(assgn); users.add(mgr)
        t = svc.create_task("o1", "DelMe")
        svc.assign_task("o1", t.id, "a1")
        svc.change_status("a1", t.id, "IN_PROGRESS")
        svc.change_status("a1", t.id, "DONE")

        with pytest.raises(PermissionError):
            svc.delete_task("o1", t.id)

        td = svc.delete_task("m1", t.id)
        assert getattr(td, "is_deleted", False) is True
        assert any(e.type == EventType.DELETED for e in events.list_for_task(t.id))

    def test_delete_task_owner_can_delete_when_not_done(self):
        svc, users, _, events = make_service()
        o = User(id="o", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(o)
        t = svc.create_task("o", "Del")
        td = svc.delete_task("o", t.id)
        assert td.is_deleted is True
        assert any(e.type == EventType.DELETED for e in events.list_for_task(t.id))

    def test_delete_task_idempotent_no_second_event(self):
        svc, users, _, events = make_service()
        m = User(id="m", email="m@ex.com", role=Role.MANAGER, status=Status.ACTIVE)
        users.add(m)
        t = svc.create_task("m", "X")

        svc.delete_task("m", t.id)
        before = len([e for e in events.list_for_task(t.id) if e.type == EventType.DELETED])
        svc.delete_task("m", t.id)
        after  = len([e for e in events.list_for_task(t.id) if e.type == EventType.DELETED])
        assert before == 1
        assert after == 1

    def test_delete_task_only_owner_can_delete(self):
        svc, users, *_ = make_service()
        o = User(id="o", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        x = User(id="x", email="x@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(o); users.add(x)
        t = svc.create_task("o", "Ok")
        with pytest.raises(PermissionError) as e:
            svc.delete_task("x", t.id)
        assert "Only owner can delete" in str(e.value)

    def test_delete_task_missing_actor_or_task_raises(self):
        svc, users, *_ = make_service()
        o = User(id="o", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(o)
        with pytest.raises(ValueError) as e:
            svc.delete_task("ghost", "nope")
        assert str(e.value) == "Actor or task not found"