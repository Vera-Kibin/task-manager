# src/repo/mongo_repo.py
import os
from typing import Optional, List
from datetime import datetime
from pymongo import MongoClient, ASCENDING

from src.repo.interface import UsersRepository, TasksRepository, EventsRepository
from src.domain.user import User, Role, Status
from src.domain.task import Task, TaskStatus, Priority
from src.domain.event import TaskEvent, EventType


# --------- mapowania ---------
def _user_to_doc(u: User) -> dict:
    return {"_id": u.id, "email": u.email, "role": u.role.name, "status": u.status.name}

def _doc_to_user(d: dict) -> User:
    return User(id=d["_id"], email=d["email"], role=Role[d["role"]], status=Status[d["status"]])

def _task_to_doc(t: "Task") -> dict:
    return {
        "_id": t.id,
        "title": t.title,
        "description": t.description,
        "status": t.status.name,
        "priority": t.priority.name,
        "owner_id": t.owner_id,
        "assignee_id": t.assignee_id,
        "due_date": t.due_date,
        "is_deleted": bool(getattr(t, "is_deleted", False)),
    }

def _doc_to_task(d: dict) -> "Task":
    return Task(
        id=d["_id"],
        title=d["title"],
        description=d.get("description", ""),
        status=TaskStatus[d["status"]],
        priority=Priority[d["priority"]],
        owner_id=d["owner_id"],
        assignee_id=d.get("assignee_id"),
        due_date=d.get("due_date"),
        is_deleted=bool(d.get("is_deleted", False)),
    )

def _event_to_doc(e: TaskEvent) -> dict:
    return {
        "_id": e.id,
        "task_id": e.task_id,
        "timestamp": e.timestamp,
        "type": e.type.name,
        "meta": e.meta,
    }

def _doc_to_event(d: dict) -> TaskEvent:
    return TaskEvent(
        id=d["_id"],
        task_id=d["task_id"],
        timestamp=d["timestamp"],
        type=EventType[d["type"]],
        meta=d.get("meta", {}),
    )


# --------- Users ---------
class MongoUsers(UsersRepository):
    def __init__(self, collection=None, uri=None, db_name=None, collection_name="users"):
        if collection is not None:
            self._collection = collection
            self._client = None
            return
        mongo_uri = uri or os.environ.get("MONGO_URI", "mongodb://localhost:27017")
        mongo_db = db_name or os.environ.get("MONGO_DB", "taskmgr")
        self._client = MongoClient(mongo_uri)
        self._collection = self._client[mongo_db][collection_name]

    def get(self, user_id: str) -> Optional[User]:
        d = self._collection.find_one({"_id": user_id})
        return _doc_to_user(d) if d else None

    def add(self, user: User) -> None:
        self._collection.replace_one({"_id": user.id}, _user_to_doc(user), upsert=True)


# --------- Tasks ---------
class MongoTasks(TasksRepository):
    def __init__(self, collection=None, uri=None, db_name=None, collection_name="tasks"):
        if collection is not None:
            self._collection = collection
            self._client = None
            return
        mongo_uri = uri or os.environ.get("MONGO_URI", "mongodb://localhost:27017")
        mongo_db = db_name or os.environ.get("MONGO_DB", "taskmgr")
        self._client = MongoClient(mongo_uri)
        self._collection = self._client[mongo_db][collection_name]

    def add(self, task: "Task") -> None:
        self._collection.replace_one({"_id": task.id}, _task_to_doc(task), upsert=True)

    def get(self, task_id: str) -> Optional["Task"]:
        d = self._collection.find_one({"_id": task_id})
        return _doc_to_task(d) if d else None

    def update(self, task: "Task") -> None:
        self._collection.replace_one({"_id": task.id}, _task_to_doc(task), upsert=True)

    def list(self) -> List["Task"]:
        return [_doc_to_task(d) for d in self._collection.find({})]


# --------- Events ---------
class MongoEvents(EventsRepository):
    def __init__(self, collection=None, uri=None, db_name=None, collection_name="events"):
        if collection is not None:
            self._collection = collection
            self._client = None
            return
        mongo_uri = uri or os.environ.get("MONGO_URI", "mongodb://localhost:27017")
        mongo_db = db_name or os.environ.get("MONGO_DB", "taskmgr")
        self._client = MongoClient(mongo_uri)
        self._collection = self._client[mongo_db][collection_name]
        self._collection.create_index([("task_id", ASCENDING), ("timestamp", ASCENDING)])

    def add(self, event: TaskEvent) -> None:
        self._collection.insert_one(_event_to_doc(event))

    def list_for_task(self, task_id: str) -> List[TaskEvent]:
        cur = self._collection.find({"task_id": task_id}).sort([("timestamp", ASCENDING)])
        return [_doc_to_event(d) for d in cur]