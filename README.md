# Task Manager (API-first)

**Autor:** Vera Kibin
**Grupa:** 2

## Opis

Prosty Task Manager z rolami (USER/MANAGER), stanami zadań (NEW/IN_PROGRESS/DONE/CANCELED), przypisywaniem, historią zdarzeń oraz miękkim usuwaniem. Architektura: domena + serwis + repo (in-memory/Mongo) + API. Zewnętrzne zależności (generator ID, zegar) są mockowane w testach.

## Wymagania projektowe

- ≥6 funkcjonalności z logiką i walidacją (create/update/assign/change_status/delete/list).
- Historia zdarzeń per task (GET /tasks/{id}/events).
- Uprawnienia zależne od użytkownika (role/status).
- Publiczne API (CRUD + akcje).
- Testy: unit, API, BDD, performance; pokrycie >80%; pipeline’y CI.  
  Szczegóły: “Wymagania do projektu 2025” (założone w repo).

## Struktura

src/
domain/ # User, Task, TaskEvent, enums, PermissionPolicy
serwis/ # TaskService (logika biznesowa)
repo/ # interface + InMemory* + (opcjonalnie) Mongo*
api/ # app.py (Flask/FastAPI), mapowanie endpointów -> TaskService
utils/ # IdGenerator, Clock
tests/
unit/ # testy serwisu i domeny (pytest)
api/ # testy HTTP (requests)
bdd/ # scenariusze Gherkin + step’y
perf/ # prosty test wydajności

## Uruchomienie

### 1) Wirtualne środowisko

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Testy jednostkowe + coverage

```bash
python3 -m coverage run --source=src -m pytest -q
python3 -m coverage report -m
```

### 3) Uruchomienie API (dev)

docker compose -f mongo.yml up -d
export STORAGE=mongo
export MONGO_URI="mongodb://localhost:27017"
export MONGO_DB="taskmgr"
python3 -m flask --app app/api.py --debug run
