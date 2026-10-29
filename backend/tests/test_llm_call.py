"""The tool call passes through and is written to the usage log, nothing else."""

import pytest

from src.services import llm_call


_ABSAGE = ("This model's maximum context length is 131072 tokens. However, your request "
           "has 205000 input tokens. Please reduce the length of the input messages.")


class _Anbieter:
    """Rejects overlong messages exactly as vLLM does."""

    def __init__(self, grenze_zeichen: int):
        self.grenze = grenze_zeichen
        self.laengen: list[int] = []
        self.kwargs: list[dict] = []

    def create(self, *, model, messages, **kwargs):
        self.laengen.append(sum(len(m.get("content") or "") for m in messages))
        self.kwargs.append(kwargs)
        if self.laengen[-1] > self.grenze:
            raise RuntimeError(_ABSAGE)
        return "ok"


class _Client:
    def __init__(self, anbieter):
        self.chat = type("_", (), {"completions": anbieter})()


def _nachrichten(zeichen: int) -> list[dict]:
    return [{"role": "system", "content": "S" * 500}, {"role": "user", "content": "K" * zeichen}]


@pytest.fixture(autouse=True)
def _ohne_protokoll(monkeypatch):
    monkeypatch.setattr(llm_call, "_mitschreiben", lambda *a, **k: None)


def test_ein_passender_aufruf_geht_durch():
    anbieter = _Anbieter(10_000)
    antwort = llm_call.create_logged(_Client(anbieter), model="m", messages=_nachrichten(1000))
    assert antwort == "ok"
    assert len(anbieter.laengen) == 1


def test_eine_absage_bleibt_eine_absage():
    """No trimming, no second attempt: the admin sets the size."""
    anbieter = _Anbieter(1_000)
    with pytest.raises(RuntimeError):
        llm_call.create_logged(_Client(anbieter), model="m", messages=_nachrichten(5000))
    assert len(anbieter.laengen) == 1, "es darf keinen zweiten Versuch geben"


def test_reicht_die_uebrigen_angaben_unveraendert_weiter():
    anbieter = _Anbieter(10_000)
    llm_call.create_logged(_Client(anbieter), model="m", messages=_nachrichten(100),
                           temperature=0.2, max_tokens=64)
    assert anbieter.kwargs[0] == {"temperature": 0.2, "max_tokens": 64}
