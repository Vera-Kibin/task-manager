import pytest
from datetime import datetime
from src.domain.task import Task, TaskStatus, Priority

class TestTaskModel:
    def test_valid_defaults_ok(self):
        t = Task(id="t1", title="Hello", owner_id="u1")
        assert t.status is TaskStatus.NEW
        assert t.priority is Priority.NORMAL
        assert t.is_deleted is False

    @pytest.mark.parametrize("bad", ["", "   ", None])
    def test_invalid_title_raises(self, bad):
        with pytest.raises(ValueError):
            Task(id="t1", title=bad, owner_id="u1")

    def test_title_too_long_raises(self):
        with pytest.raises(ValueError):
            Task(id="t1", title="x"*201, owner_id="u1")

    def test_invalid_owner_raises(self):
        with pytest.raises(ValueError):
            Task(id="t1", title="Ok", owner_id="")

    def test_invalid_due_date_type_raises(self):
        with pytest.raises(ValueError):
            Task(id="t1", title="Ok", owner_id="u1", due_date="2025-01-01")

    def test_with_due_date_ok(self):
        dt = datetime(2025,1,1,12,0,0)
        t = Task(id="t1", title="Ok", owner_id="u1", due_date=dt)
        assert t.due_date == dt

class TestTaskModelExtraMessages:
    def test_id_must_be_non_empty_message(self):
        with pytest.raises(ValueError) as e:
            Task(id="", title="Ok", owner_id="u1")
        assert "Task.id must be non-empty" in str(e.value)

    def test_priority_must_be_priority_enum_message(self):
        with pytest.raises(ValueError) as e:
            Task(id="t1", title="Ok", owner_id="u1", priority="HIGH")
        assert "priority must be Priority enum" in str(e.value)

    def test_status_must_be_taskstatus_enum_message(self):
        with pytest.raises(ValueError) as e:
            Task(id="t1", title="Ok", owner_id="u1", status="DONE")
        assert "status must be TaskStatus enum" in str(e.value)