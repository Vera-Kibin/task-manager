from src.utils.clock import Clock
from src.utils.idgen import IdGenerator

def test_idgen_returns_distinct_ids():
    g = IdGenerator()
    assert g.new_id() != g.new_id()

def test_clock_now_returns_datetime():
    c = Clock()
    assert hasattr(c.now(), "year")