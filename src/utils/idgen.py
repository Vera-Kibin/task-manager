import uuid

class IdGenerator:
    @staticmethod
    def new_id() -> str:
        return str(uuid.uuid4())