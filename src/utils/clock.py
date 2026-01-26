from datetime import datetime

class Clock:
    @staticmethod
    def now() -> datetime:
        return datetime.now()