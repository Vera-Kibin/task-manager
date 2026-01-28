import os, uuid, pytest
from pymongo import MongoClient
from app.api import create_app

def _use_mongo() -> bool:
    return os.environ.get("STORAGE", "memory").lower() == "mongo"

@pytest.fixture
def client():
    if _use_mongo():
        dbname = f"taskmgr_test_{uuid.uuid4().hex}"
        os.environ["MONGO_DB"] = dbname

        app = create_app()
        app.config["TESTING"] = True
        c = app.test_client()
        try:
            yield c
        finally:
            uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
            MongoClient(uri).drop_database(dbname)
    else:
        app = create_app()
        app.config["TESTING"] = True
        yield app.test_client()