from __future__ import annotations
from dataclasses import asdict
from datetime import datetime
import os
from typing import Optional

from flask import Flask, jsonify, request
from werkzeug.exceptions import NotFound

from src.serwis.task_service import TaskService
from src.repo.memory_repo import InMemoryUsers, InMemoryTasks, InMemoryEvents
from src.utils.idgen import IdGenerator
from src.utils.clock import Clock
from src.domain.user import User, Role, Status
from src.domain.task import Task, TaskStatus, Priority
from src.domain.event import TaskEvent, EventType


# ---------- helpers ----------

def _task_to_dict(t: Task) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "status": t.status.name,
        "priority": t.priority.name,
        "owner_id": t.owner_id,
        "assignee_id": t.assignee_id,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "is_deleted": bool(getattr(t, "is_deleted", False)),
    }

def _event_to_dict(e: TaskEvent) -> dict:
    return {
        "id": e.id,
        "task_id": e.task_id,
        "timestamp": e.timestamp.isoformat(),
        "type": e.type.name,
        "meta": e.meta,
    }

def _actor_id() -> str:
    aid = request.headers.get("X-Actor-Id")
    if not aid:
        raise ValueError("Missing X-Actor-Id header")
    return aid

def create_app() -> Flask:
    app = Flask(__name__)

    # users = InMemoryUsers()
    # tasks = InMemoryTasks()
    # events = InMemoryEvents()
    # idgen = IdGenerator()
    # clock = Clock()
    # svc = TaskService(users, tasks, events, idgen, clock)

    # # seed kilku userow
    # users.add(User(id="m1", email="m@example.com", role=Role.MANAGER, status=Status.ACTIVE))
    # users.add(User(id="u1", email="u1@example.com", role=Role.USER,    status=Status.ACTIVE))
    # users.add(User(id="u2", email="u2@example.com", role=Role.USER,    status=Status.ACTIVE))

    storage = os.environ.get("STORAGE", "memory").lower()
    if storage == "mongo":
        from src.repo.mongo_repo import MongoUsers, MongoTasks, MongoEvents
        mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
        mongo_db  = os.environ.get("MONGO_DB", "taskmgr")
        users  = MongoUsers(uri=mongo_uri, db_name=mongo_db, collection_name="users")
        tasks  = MongoTasks(uri=mongo_uri, db_name=mongo_db, collection_name="tasks")
        events = MongoEvents(uri=mongo_uri, db_name=mongo_db, collection_name="events")
    else:
        from src.repo.memory_repo import InMemoryUsers, InMemoryTasks, InMemoryEvents
        users, tasks, events = InMemoryUsers(), InMemoryTasks(), InMemoryEvents()

    idgen = IdGenerator()
    clock = Clock()
    svc = TaskService(users, tasks, events, idgen, clock)
     # seed kilku userow
    users.add(User(id="m1", email="m@example.com", role=Role.MANAGER, status=Status.ACTIVE))
    users.add(User(id="u1", email="u1@example.com", role=Role.USER,    status=Status.ACTIVE))
    users.add(User(id="u2", email="u2@example.com", role=Role.USER,    status=Status.ACTIVE))

    # ---------- error handling ----------
    @app.errorhandler(ValueError)
    def _value_error(e: ValueError):
        return jsonify({"message": str(e)}), 400

    @app.errorhandler(PermissionError)
    def _perm_error(e: PermissionError):
        return jsonify({"message": str(e)}), 403

    @app.errorhandler(NotFound)
    def _not_found(e: NotFound):
        return jsonify({"message": "Not found"}), 404

    @app.errorhandler(Exception)
    def _unexpected(e: Exception):
        return jsonify({"message": "Internal Server Error"}), 500

    # ---------- USERS ----------
    @app.route("/api/users", methods=["POST"])
    def create_user():
        data = request.get_json(force=True) or {}
        try:
            u = User(
                id=data["id"],
                email=data["email"],
                role=Role[data.get("role", "USER").upper()],
                status=Status[data.get("status", "ACTIVE").upper()],
            )
        except KeyError as ex:
            raise ValueError(f"Missing field: {ex}")
        users.add(u)
        return jsonify({"message": "User created"}), 201

    # ---------- TASKS ----------
    @app.route("/api/tasks", methods=["POST"])
    def create_task():
        actor_id = _actor_id()
        data = request.get_json(force=True) or {}
        title = data.get("title", "")
        description = data.get("description", "")
        priority = data.get("priority", "NORMAL")
        t = svc.create_task(actor_id, title=title, description=description, priority=priority)
        return jsonify(_task_to_dict(t)), 201

    @app.route("/api/tasks/<task_id>", methods=["PATCH"])
    def update_task(task_id: str):
        actor_id = _actor_id()
        data = request.get_json(force=True) or {}
        t = svc.update_task(
            actor_id,
            task_id,
            title=data.get("title"),
            description=data.get("description"),
            priority=data.get("priority"),
        )
        return jsonify(_task_to_dict(t)), 200

    @app.route("/api/tasks/<task_id>/assign", methods=["POST"])
    def assign_task(task_id: str):
        actor_id = _actor_id()
        data = request.get_json(force=True) or {}
        assignee_id = data.get("assignee_id")
        if not assignee_id:
            raise ValueError("Missing assignee_id")
        t = svc.assign_task(actor_id, task_id, assignee_id)
        return jsonify(_task_to_dict(t)), 200

    @app.route("/api/tasks/<task_id>/status", methods=["POST"])
    def change_status(task_id: str):
        actor_id = _actor_id()
        data = request.get_json(force=True) or {}
        new_status = data.get("new_status")
        if not new_status:
            raise ValueError("Missing new_status")
        t = svc.change_status(actor_id, task_id, new_status)
        return jsonify(_task_to_dict(t)), 200

    @app.route("/api/tasks", methods=["GET"])
    def list_tasks():
        actor_id = _actor_id()
        status = request.args.get("status")
        priority = request.args.get("priority")
        items = svc.list_tasks(actor_id, status=status, priority=priority)
        return jsonify([_task_to_dict(t) for t in items]), 200

    @app.route("/api/tasks/<task_id>", methods=["DELETE"])
    def delete_task(task_id: str):
        actor_id = _actor_id()
        t = svc.delete_task(actor_id, task_id)
        return jsonify(_task_to_dict(t)), 200

    # ---------- EVENTS ----------
    @app.route("/api/tasks/<task_id>/events", methods=["GET"])
    def get_events(task_id: str):
        actor_id = _actor_id()
        evs = svc.get_events(actor_id, task_id)
        return jsonify([_event_to_dict(e) for e in evs]), 200

    return app


app = create_app()