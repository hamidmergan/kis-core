from src.features.ai_assistant.scheduling.rate_gate import InMemoryStore
from src.features.ai_assistant.scheduling.weighted_gate import WeightedGate, area_rates


class FakeClock:
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_area_rates_split_by_weight():
    rates = area_rates(2.0, {"chat": 2.0, "ingest": 1.0, "studio": 1.0})
    assert rates["chat"] == 1.0
    assert rates["ingest"] == 0.5
    assert rates["studio"] == 0.5


def test_area_rates_unlimited_when_global_zero():
    rates = area_rates(0.0, {"chat": 2.0, "ingest": 1.0})
    assert rates == {"chat": 0.0, "ingest": 0.0}


def test_gate_grants_per_area_share():
    clock = FakeClock()
    gate = WeightedGate(
        global_per_sec=2.0,
        weights={"chat": 2.0, "ingest": 1.0, "studio": 1.0},
        store=InMemoryStore(),
        now=clock,
        burst=1.0,
    )
    # fresh buckets: each area gets its initial burst token
    assert gate.allow("chat") is True
    assert gate.allow("ingest") is True
    assert gate.allow("studio") is True
    # drained now
    assert gate.allow("chat") is False
    # after 1s: chat refills 1.0 (rate 1/s), ingest/studio only 0.5
    clock.advance(1.0)
    assert gate.allow("chat") is True
    assert gate.allow("ingest") is False  # only 0.5 token
    clock.advance(1.0)
    assert gate.allow("ingest") is True  # now 0.5+0.5 = 1.0


def test_gate_unlimited_when_global_zero():
    gate = WeightedGate(0.0, {"chat": 2.0, "ingest": 1.0}, store=InMemoryStore(), now=FakeClock())
    for _ in range(100):
        assert gate.allow("chat") is True
        assert gate.allow("ingest") is True


def test_unknown_area_passes_through():
    gate = WeightedGate(2.0, {"chat": 1.0}, store=InMemoryStore(), now=FakeClock())
    assert gate.allow("does-not-exist") is True


def test_acquire_waits_then_succeeds():
    clock = FakeClock()
    # single area -> rate = 2/s, token refills after 0.5s
    gate = WeightedGate(2.0, {"chat": 1.0}, store=InMemoryStore(), now=clock, burst=1.0)
    assert gate.allow("chat") is True  # drain the burst token
    assert gate.allow("chat") is False
    # sleep advances the shared clock so a token refills within max_wait
    assert gate.acquire("chat", max_wait=5.0, sleep=lambda dt: clock.advance(1.0), now=clock) is True


def test_acquire_times_out():
    clock = FakeClock()
    # rate 2/s -> token at 0.5s; max_wait 0.3 with 0.1 steps never reaches it
    gate = WeightedGate(2.0, {"chat": 1.0}, store=InMemoryStore(), now=clock, burst=1.0)
    gate.allow("chat")  # drain
    assert gate.acquire("chat", max_wait=0.3, sleep=lambda dt: clock.advance(0.1), now=clock) is False
