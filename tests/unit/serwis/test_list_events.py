import pytest
from tests.helper import make_service
from src.domain.user import User, Role, Status
from src.domain.event import EventType

class TestList:
    def test_list_tasks_user_sees_only_own_and_assigned(self):
        svc, users, *_ = make_service()
        a = User(id="a", email="a@ex.com", role=Role.USER, status=Status.ACTIVE)
        b = User(id="b", email="b@ex.com", role=Role.USER, status=Status.ACTIVE)
        c = User(id="c", email="c@ex.com", role=Role.USER, status=Status.ACTIVE)
        m = User(id="m", email="m@ex.com", role=Role.MANAGER, status=Status.ACTIVE)
        users.add(a); users.add(b); users.add(c); users.add(m)

        t1 = svc.create_task("a", "A1")
        t2 = svc.create_task("b", "B1")
        svc.assign_task("b", t2.id, "c")
        t3 = svc.create_task("b", "B2")
        svc.assign_task("b", t3.id, "a")

        seen_by_a = {t.id for t in svc.list_tasks("a")}
        assert seen_by_a == {t1.id, t3.id}

        seen_by_m = {t.id for t in svc.list_tasks("m")}
        assert seen_by_m == {t1.id, t2.id, t3.id}

    def test_list_tasks_filters_work(self):
        svc, users, *_ = make_service()
        u = User(id="u", email="u@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(u)

        t1 = svc.create_task("u", "T1", priority="NORMAL")
        t2 = svc.create_task("u", "T2", priority="HIGH")
        svc.change_status("u", t2.id, "IN_PROGRESS")

        only_inprog = svc.list_tasks("u", status="IN_PROGRESS")
        assert {t.id for t in only_inprog} == {t2.id}

        only_high = svc.list_tasks("u", priority="HIGH")
        assert {t.id for t in only_high} == {t2.id}

    def test_list_tasks_unknown_status_filter_raises(self):
        svc, users, *_ = make_service()
        users.add(User(id="u", email="u@ex.com", role=Role.USER, status=Status.ACTIVE))
        with pytest.raises(ValueError) as e:
            svc.list_tasks("u", status="??")
        assert str(e.value) == "Unknown status filter"

    def test_list_tasks_unknown_priority_filter_raises(self):
        svc, users, *_ = make_service()
        users.add(User(id="u", email="u@ex.com", role=Role.USER, status=Status.ACTIVE))
        with pytest.raises(ValueError) as e:
            svc.list_tasks("u", priority="ULTRA")
        assert str(e.value) == "Unknown priority filter"

    def test_list_tasks_missing_actor_raises(self):
        svc, *_ = make_service()
        with pytest.raises(ValueError) as e:
            svc.list_tasks("ghost")
        assert str(e.value) == "Actor not found"

class TestEvents:
    def test_get_events_forbidden_for_unrelated_user(self):
        svc, users, *_ = make_service()
        owner = User(id="o1", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        other = User(id="x1", email="x@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(owner); users.add(other)
        t = svc.create_task("o1", "Secret")
        with pytest.raises(PermissionError):
            svc.get_events("x1", t.id)

    def test_get_events_history_contains_created_assigned_status_changes(self):
        svc, users, *_ = make_service()
        m = User(id="m1", email="m@ex.com", role=Role.MANAGER, status=Status.ACTIVE)
        d = User(id="d1", email="d@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(m); users.add(d)
        t = svc.create_task("m1", "Feature")
        svc.assign_task("m1", t.id, "d1")
        svc.change_status("d1", t.id, "IN_PROGRESS")
        svc.change_status("d1", t.id, "DONE")
        kinds = [e.type for e in svc.get_events("d1", t.id)]
        assert EventType.CREATED in kinds
        assert EventType.ASSIGNED in kinds
        assert kinds.count(EventType.STATUS_CHANGED) == 2

    def test_get_events_actor_or_task_not_found(self):
        svc, users, *_ = make_service()
        users.add(User(id="u", email="u@ex.com", role=Role.USER, status=Status.ACTIVE))
        with pytest.raises(ValueError) as e1:
            svc.get_events("ghost", "nope")
        assert str(e1.value) == "Actor or task not found"
        with pytest.raises(ValueError) as e2:
            svc.get_events("u", "nope")
        assert str(e2.value) == "Actor or task not found"