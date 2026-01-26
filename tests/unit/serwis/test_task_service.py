import pytest
from datetime import datetime

from src.serwis.task_service import TaskService
from src.repo.memory_repo import InMemoryUsers, InMemoryTasks, InMemoryEvents
from src.domain.user import User, Role, Status
from src.domain.task import TaskStatus
from src.domain.event import EventType


# ============================== HELPERS ==============================

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


# ============================== HAPPY PATH ==============================

class TestTaskServiceHappyPath:
    # -------- CREATE --------
    def test_create_task_ok(self):
        svc, users, _, events = make_service()
        users.add(User(id="u1", email="u1@example.com", role=Role.USER, status=Status.ACTIVE))

        t = svc.create_task(actor_id="u1", title="Zadanie A", description="opis", priority="NORMAL")
        assert t.title == "Zadanie A"
        assert t.owner_id == "u1"

        evs = events.list_for_task(t.id)
        assert len(evs) == 1 and evs[0].type == EventType.CREATED

    # -------- ASSIGN --------
    def test_assign_task_ok_by_manager(self):
        svc, users, _, events = make_service()
        mgr = User(id="m1", email="m@example.com", role=Role.MANAGER, status=Status.ACTIVE)
        dev = User(id="d1", email="d@example.com", role=Role.USER,    status=Status.ACTIVE)
        users.add(mgr); users.add(dev)

        t = svc.create_task(actor_id="m1", title="Fix bug")
        t2 = svc.assign_task(actor_id="m1", task_id=t.id, assignee_id="d1")
        assert t2.assignee_id == "d1"

        evs = events.list_for_task(t.id)
        assert any(e.type == EventType.ASSIGNED for e in evs)

    # -------- STATUS --------
    def test_change_status_happy_path(self):
        svc, users, _, events = make_service()
        mgr = User(id="m1", email="m@example.com", role=Role.MANAGER, status=Status.ACTIVE)
        dev = User(id="d1", email="d1@example.com", role=Role.USER, status=Status.ACTIVE)
        users.add(mgr); users.add(dev)

        t = svc.create_task(actor_id="m1", title="Implement feature")
        svc.assign_task(actor_id="m1", task_id=t.id, assignee_id="d1")

        t = svc.change_status(actor_id="d1", task_id=t.id, new_status="IN_PROGRESS")
        assert t.status == TaskStatus.IN_PROGRESS

        t = svc.change_status(actor_id="d1", task_id=t.id, new_status="DONE")
        assert t.status == TaskStatus.DONE

        evs = events.list_for_task(t.id)
        assert [e.type for e in evs].count(EventType.STATUS_CHANGED) == 2


# ============================== PERMISSIONS / FILTERS ==============================

class TestTaskServicePermissionsAndFilters:
    def test_create_task_blocked_forbidden(self):
        svc, users, *_ = make_service()
        blocked = User(id="u2", email="u2@example.com", role=Role.USER, status=Status.BLOCKED)
        users.add(blocked)
        with pytest.raises(PermissionError):
            svc.create_task(actor_id="u2", title="Nie powinno się udać")

    def test_assign_task_forbidden_when_not_owner_nor_manager(self):
        svc, users, *_ = make_service()
        owner = User(id="o1", email="o@example.com", role=Role.USER, status=Status.ACTIVE)
        other = User(id="x1", email="x@example.com", role=Role.USER, status=Status.ACTIVE)
        target= User(id="t1", email="t@example.com", role=Role.USER, status=Status.ACTIVE)
        users.add(owner); users.add(other); users.add(target)

        t = svc.create_task(actor_id="o1", title="Sekretne zadanie")
        with pytest.raises(PermissionError):
            svc.assign_task(actor_id="x1", task_id=t.id, assignee_id="t1")

    def test_change_status_forbidden_actor(self):
        svc, users, *_ = make_service()
        owner = User(id="o1", email="o@example.com", role=Role.USER, status=Status.ACTIVE)
        other = User(id="x1", email="x@example.com", role=Role.USER, status=Status.ACTIVE)
        users.add(owner); users.add(other)

        t = svc.create_task(actor_id="o1", title="Task")
        with pytest.raises(PermissionError):
            svc.change_status(actor_id="x1", task_id=t.id, new_status="DONE")

    def test_list_tasks_user_sees_only_own_and_assigned(self):
        svc, users, *_ = make_service()
        a = User(id="a", email="a@ex.com", role=Role.USER, status=Status.ACTIVE)
        b = User(id="b", email="b@ex.com", role=Role.USER, status=Status.ACTIVE)
        c = User(id="c", email="c@ex.com", role=Role.USER, status=Status.ACTIVE)
        m = User(id="m", email="m@ex.com", role=Role.MANAGER, status=Status.ACTIVE)
        users.add(a); users.add(b); users.add(c); users.add(m)

        t1 = svc.create_task("a", "A1", "", "NORMAL")
        t2 = svc.create_task("b", "B1", "", "NORMAL")
        svc.assign_task("b", t2.id, "c")
        t3 = svc.create_task("b", "B2", "", "NORMAL")
        svc.assign_task("b", t3.id, "a")

        seen_by_a = {t.id for t in svc.list_tasks("a")}
        assert seen_by_a == {t1.id, t3.id}

        seen_by_m = {t.id for t in svc.list_tasks("m")}
        assert seen_by_m == {t1.id, t2.id, t3.id}

    def test_list_tasks_filters_work(self):
        svc, users, *_ = make_service()
        u = User(id="u", email="u@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(u)

        t1 = svc.create_task("u", "T1", "", "NORMAL")
        t2 = svc.create_task("u", "T2", "", "HIGH")
        svc.change_status("u", t2.id, "IN_PROGRESS")

        only_inprog = svc.list_tasks("u", status="IN_PROGRESS")
        assert {t.id for t in only_inprog} == {t2.id}

        only_high = svc.list_tasks("u", priority="HIGH")
        assert {t.id for t in only_high} == {t2.id}

    def test_get_events_forbidden_for_unrelated_user(self):
        svc, users, *_ = make_service()
        owner = User(id="o1", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        other = User(id="x1", email="x@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(owner); users.add(other)

        t = svc.create_task("o1", "Secret", "", "NORMAL")
        with pytest.raises(PermissionError):
            svc.get_events("x1", t.id)


# ============================== CRUD / EVENTS ==============================

class TestTaskServiceCRUD:
    # -------- UPDATE --------
    def test_update_task_ok_by_owner_changes_title_and_priority(self):
        svc, users, _, events = make_service()
        owner = User(id="u1", email="u1@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(owner)

        t = svc.create_task(actor_id="u1", title="Old", description="desc", priority="NORMAL")
        t2 = svc.update_task("u1", t.id, title="New", priority="HIGH")
        assert t2.title == "New"
        assert t2.priority.name == "HIGH"

        evs = events.list_for_task(t.id)
        assert any(e.type == EventType.UPDATED for e in evs)

    def test_update_task_forbidden_when_done(self):
        svc, users, *_ = make_service()
        owner = User(id="o1", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        assgn = User(id="a1", email="a@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(owner); users.add(assgn)

        t = svc.create_task("o1", "T", "", "NORMAL")
        svc.assign_task("o1", t.id, "a1")
        svc.change_status("a1", t.id, "IN_PROGRESS")
        svc.change_status("a1", t.id, "DONE")

        with pytest.raises(PermissionError):
            svc.update_task("o1", t.id, title="cant-change")

    def test_update_task_actor_not_found_raises(self):
        svc, users, *_ = make_service()
        owner = User(id="u1", email="u1@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(owner)
        t = svc.create_task("u1", "T", "", "NORMAL")
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

    # -------- DELETE --------
    def test_delete_task_owner_cannot_delete_done_but_manager_can(self):
        svc, users, _, events = make_service()
        owner = User(id="o1", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        assgn = User(id="a1", email="a@ex.com", role=Role.USER, status=Status.ACTIVE)
        mgr   = User(id="m1", email="m@ex.com", role=Role.MANAGER, status=Status.ACTIVE)
        users.add(owner); users.add(assgn); users.add(mgr)

        t = svc.create_task("o1", "DelMe", "", "NORMAL")
        svc.assign_task("o1", t.id, "a1")
        svc.change_status("a1", t.id, "IN_PROGRESS")
        svc.change_status("a1", t.id, "DONE")

        with pytest.raises(PermissionError):
            svc.delete_task("o1", t.id)

        td = svc.delete_task("m1", t.id)
        assert getattr(td, "is_deleted", False) is True

        evs = events.list_for_task(t.id)
        assert any(e.type == EventType.DELETED for e in evs)

    # -------- EVENTS (HISTORY) --------
    def test_get_events_history_contains_created_assigned_status_changes(self):
        svc, users, *_ = make_service()
        m = User(id="m1", email="m@ex.com", role=Role.MANAGER, status=Status.ACTIVE)
        d = User(id="d1", email="d@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(m); users.add(d)

        t = svc.create_task("m1", "Feature", "", "NORMAL")
        svc.assign_task("m1", t.id, "d1")
        svc.change_status("d1", t.id, "IN_PROGRESS")
        svc.change_status("d1", t.id, "DONE")

        evs = svc.get_events("d1", t.id)
        kinds = [e.type for e in evs]
        assert EventType.CREATED in kinds
        assert EventType.ASSIGNED in kinds
        assert kinds.count(EventType.STATUS_CHANGED) == 2


# ============================== BŁĘDY / WYJĄTKI (DROBIAZGI) ==============================

class TestTaskServiceErrors:
    # -------- CREATE --------
    def test_create_task_invalid_title_raises(self):
        svc, users, *_ = make_service()
        users.add(User(id="u1", email="u1@ex.com", role=Role.USER, status=Status.ACTIVE))
        with pytest.raises(ValueError) as e:
            svc.create_task(actor_id="u1", title="", description="x", priority="NORMAL")
        assert str(e.value) == "Invalid title"

    def test_create_task_unknown_priority_raises(self):
        svc, users, *_ = make_service()
        users.add(User(id="u1", email="u1@ex.com", role=Role.USER, status=Status.ACTIVE))
        with pytest.raises(ValueError) as e:
            svc.create_task(actor_id="u1", title="T", description="x", priority="NOPE")
        assert str(e.value) == "Unknown priority"

    def test_create_task_actor_missing_forbidden(self):
        svc, *_ = make_service()
        with pytest.raises(PermissionError) as e:
            svc.create_task(actor_id="ghost", title="T")
        assert "User cannot create tasks" in str(e.value)

    # -------- ASSIGN --------
    def test_assign_task_missing_task_raises(self):
        svc, users, *_ = make_service()
        users.add(User(id="owner",   email="o@ex.com", role=Role.USER, status=Status.ACTIVE))
        users.add(User(id="assignee",email="a@ex.com", role=Role.USER, status=Status.ACTIVE))
        with pytest.raises(ValueError) as e:
            svc.assign_task(actor_id="owner", task_id="no-such", assignee_id="assignee")
        assert str(e.value) == "Task not found"
        
    def test_assign_task_missing_actor_or_assignee_raises(self):
        svc, users, *_ = make_service()
        users.add(User(id="owner", email="o@ex.com", role=Role.USER, status=Status.ACTIVE))
        t = svc.create_task(actor_id="owner", title="T", description="", priority="NORMAL")
        with pytest.raises(ValueError) as e:
            svc.assign_task(actor_id="ghost", task_id=t.id, assignee_id="nobody")
        assert str(e.value) == "Actor or assignee not found"

    def test_assign_task_blocked_assignee_forbidden(self):
        svc, users, *_ = make_service()
        mgr = User(id="m", email="m@ex.com", role=Role.MANAGER, status=Status.ACTIVE)
        blocked = User(id="d", email="d@ex.com", role=Role.USER, status=Status.BLOCKED)
        users.add(mgr); users.add(blocked)

        t = svc.create_task("m", "T", "", "NORMAL")
        with pytest.raises(PermissionError) as e:
            svc.assign_task(actor_id="m", task_id=t.id, assignee_id="d")
        assert "User cannot assign this task" in str(e.value)

    def test_assign_task_event_meta_prev_on_reassign(self):
        svc, users, _, events = make_service()
        m  = User(id="m",  email="m@ex.com", role=Role.MANAGER, status=Status.ACTIVE)
        a1 = User(id="a1", email="a1@ex.com", role=Role.USER,    status=Status.ACTIVE)
        a2 = User(id="a2", email="a2@ex.com", role=Role.USER,    status=Status.ACTIVE)
        users.add(m); users.add(a1); users.add(a2)

        t = svc.create_task("m", "R", "", "NORMAL")
        svc.assign_task("m", t.id, "a1")
        svc.assign_task("m", t.id, "a2")

        evs = [e for e in events.list_for_task(t.id) if e.type == EventType.ASSIGNED]
        assert len(evs) == 2
        assert evs[-1].meta["from"] == "a1"
        assert evs[-1].meta["to"]   == "a2"

    # -------- CHANGE STATUS --------
    def test_change_status_missing_task_raises(self):
        svc, users, *_ = make_service()
        users.add(User(id="u1", email="u1@ex.com", role=Role.USER, status=Status.ACTIVE))
        with pytest.raises(ValueError) as e:
            svc.change_status(actor_id="u1", task_id="nope", new_status="IN_PROGRESS")
        assert str(e.value) == "Task not found" 

    def test_change_status_missing_actor_raises(self):
        svc, users, *_ = make_service()
        users.add(User(id="owner", email="o@ex.com", role=Role.USER, status=Status.ACTIVE))
        t = svc.create_task(actor_id="owner", title="T", description="", priority="NORMAL")
        with pytest.raises(ValueError) as e:
            svc.change_status(actor_id="ghost", task_id=t.id, new_status="IN_PROGRESS")
        assert str(e.value) == "Actor not found"

    def test_change_status_unknown_status_raises(self):
        svc, users, *_ = make_service()
        users.add(User(id="owner", email="o@ex.com", role=Role.USER, status=Status.ACTIVE))
        t = svc.create_task(actor_id="owner", title="T", description="", priority="NORMAL")
        with pytest.raises(ValueError) as e:
            svc.change_status(actor_id="owner", task_id=t.id, new_status="WHAT_IS_THIS")
        assert str(e.value) == "Unknown status"

    def test_change_status_invalid_transition_raises(self):
        svc, users, *_ = make_service()
        dev = User(id="d1", email="d@example.com", role=Role.USER, status=Status.ACTIVE)
        users.add(dev)
        t = svc.create_task(actor_id="d1", title="Zadanie")
        with pytest.raises(ValueError):
            svc.change_status(actor_id="d1", task_id=t.id, new_status="DONE")

    def test_change_status_done_forbidden_for_owner_not_assignee(self):
        svc, users, *_ = make_service()
        owner = User(id="o1", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        assgn = User(id="a1", email="a@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(owner); users.add(assgn)

        t = svc.create_task("o1", "T", "", "NORMAL")
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

        t = svc.create_task("m1", "Feature", "", "NORMAL")
        svc.assign_task("m1", t.id, "d1")

        d.status = Status.BLOCKED
        with pytest.raises(PermissionError) as e:
            svc.change_status("d1", t.id, "IN_PROGRESS")
        assert "User cannot change status for this task" in str(e.value)  

    def test_change_status_manager_can_cancel_anytime(self):
        svc, users, _, events = make_service()
        m = User(id="m", email="m@ex.com", role=Role.MANAGER, status=Status.ACTIVE)
        users.add(m)

        t = svc.create_task("m", "X", "", "NORMAL")
        t = svc.change_status("m", t.id, "CANCELED")
        assert t.status == TaskStatus.CANCELED
        assert any(e.type == EventType.STATUS_CHANGED for e in events.list_for_task(t.id))

    # -------- UPDATE (edge cases) --------
    def test_update_task_invalid_title_raises(self):
        svc, users, *_ = make_service()
        o = User(id="o", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(o)
        t = svc.create_task("o", "Ok", "", "NORMAL")

        with pytest.raises(ValueError) as e:
            svc.update_task("o", t.id, title="")
        assert str(e.value) == "Invalid title"     

    def test_update_task_unknown_priority_raises(self):
        svc, users, *_ = make_service()
        o = User(id="o", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(o)
        t = svc.create_task("o", "Ok", "", "NORMAL")

        with pytest.raises(ValueError) as e:
            svc.update_task("o", t.id, priority="ULTRA")
        assert str(e.value) == "Unknown priority"

    def test_update_task_no_changes_no_event(self):
        svc, users, _, events = make_service()
        o = User(id="o", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(o)
        t = svc.create_task("o", "Ok", "d", "NORMAL")

        before = len(events.list_for_task(t.id))
        t2 = svc.update_task("o", t.id)  
        after = len(events.list_for_task(t.id))
        assert t2.id == t.id and before == after   

    def test_update_task_forbidden_when_not_owner_nor_assignee(self):
        svc, users, *_ = make_service()
        o = User(id="o", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        x = User(id="x", email="x@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(o); users.add(x)
        t = svc.create_task("o", "Ok", "", "NORMAL")

        with pytest.raises(PermissionError) as e:
            svc.update_task("x", t.id, title="New")
        assert "User cannot update this task" in str(e.value)  
    def test_update_task_manager_can_update_done(self):
        svc, users, _, events = make_service()
        m = User(id="m", email="m@ex.com", role=Role.MANAGER, status=Status.ACTIVE)
        d = User(id="d", email="d@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(m); users.add(d)

        t = svc.create_task("m", "Ok", "", "NORMAL")
        svc.assign_task("m", t.id, "d")
        svc.change_status("d", t.id, "IN_PROGRESS")
        svc.change_status("d", t.id, "DONE")

        t2 = svc.update_task("m", t.id, description="after-done")
        assert t2.description == "after-done"
        assert any(e.type == EventType.UPDATED for e in events.list_for_task(t.id))  

    # -------- DELETE (edge cases) --------
    def test_delete_task_owner_can_delete_when_not_done(self):
        svc, users, _, events = make_service()
        o = User(id="o", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(o)
        t = svc.create_task("o", "Del", "", "NORMAL")

        td = svc.delete_task("o", t.id)
        assert td.is_deleted is True
        assert any(e.type == EventType.DELETED for e in events.list_for_task(t.id))   

    def test_delete_task_idempotent_no_second_event(self):
        svc, users, _, events = make_service()
        m = User(id="m", email="m@ex.com", role=Role.MANAGER, status=Status.ACTIVE)
        users.add(m)
        t = svc.create_task("m", "X", "", "NORMAL")

        svc.delete_task("m", t.id)
        before = len([e for e in events.list_for_task(t.id) if e.type == EventType.DELETED])
        svc.delete_task("m", t.id)
        after  = len([e for e in events.list_for_task(t.id) if e.type == EventType.DELETED])

        assert before == 1 and after == 1                                            

    def test_delete_task_only_owner_can_delete(self):
        svc, users, *_ = make_service()
        o = User(id="o", email="o@ex.com", role=Role.USER, status=Status.ACTIVE)
        x = User(id="x", email="x@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(o); users.add(x)
        t = svc.create_task("o", "Ok", "", "NORMAL")

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

    # -------- LIST (edge cases) --------
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

    # -------- EVENTS (edge cases) --------
    def test_get_events_actor_or_task_not_found(self):
        svc, users, *_ = make_service()
        u = User(id="u", email="u@ex.com", role=Role.USER, status=Status.ACTIVE)
        users.add(u)

        with pytest.raises(ValueError) as e1:
            svc.get_events("ghost", "nope")
        assert str(e1.value) == "Actor or task not found" 

        with pytest.raises(ValueError) as e2:
            svc.get_events("u", "nope")
        assert str(e2.value) == "Actor or task not found"