from src.features.ai_assistant.scheduling.rate_gate import (
    InMemoryStore,
    RateGate,
    gate_for_provider,
)


class FakeClock:
    def __init__(self, t: float = 0.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_allows_up_to_burst_then_blocks():
    gate = RateGate(rate_per_sec=2.0, burst=2, store=InMemoryStore(), now=FakeClock())
    assert gate.allow("p") is True
    assert gate.allow("p") is True
    assert gate.allow("p") is False


def test_refills_over_time():
    clock = FakeClock()
    gate = RateGate(rate_per_sec=2.0, burst=2, store=InMemoryStore(), now=clock)
    gate.allow("p")
    gate.allow("p")
    assert gate.allow("p") is False
    clock.advance(0.5)  # 0.5s * 2/s = 1 token
    assert gate.allow("p") is True
    assert gate.allow("p") is False


def test_keys_are_independent():
    gate = RateGate(rate_per_sec=1.0, burst=1, store=InMemoryStore(), now=FakeClock())
    assert gate.allow("a") is True
    assert gate.allow("b") is True
    assert gate.allow("a") is False


def test_zero_rate_means_unlimited():
    gate = RateGate(rate_per_sec=0.0, burst=1, store=InMemoryStore(), now=FakeClock())
    for _ in range(100):
        assert gate.allow("p") is True


def test_burst_caps_accumulation():
    clock = FakeClock()
    gate = RateGate(rate_per_sec=10.0, burst=3, store=InMemoryStore(), now=clock)
    clock.advance(100)  # would refill 1000 tokens, but burst caps at 3
    assert [gate.allow("p") for _ in range(4)] == [True, True, True, False]


def test_gate_for_provider_reads_settings():
    settings = {"aia_rate_kisski_per_sec": "5", "aia_rate_kisski_burst": "7"}
    gate = gate_for_provider(
        "kisski",
        store=InMemoryStore(),
        get_setting=lambda k, d="": settings.get(k, d),
        now=FakeClock(),
    )
    assert gate.rate == 5.0
    assert gate.burst == 7.0


def test_gate_for_provider_defaults_to_two():
    gate = gate_for_provider(
        "thl",
        store=InMemoryStore(),
        get_setting=lambda k, d="": d,
        now=FakeClock(),
    )
    assert gate.rate == 2.0
    assert gate.burst == 2.0
