"""The caller is the one place a model call gets its timeout and its booking."""

from tests.summary_helpers import FakeClient

from src.features.summary.models import GROUND_RULES, Caller, Outline, Section
from src.limits import SUMMARY_CALL_TIMEOUT_SECONDS


async def test_der_aufrufer_setzt_modell_und_zeitgrenze():
    client = FakeClient(["ok"])
    caller = Caller(client, "m")

    antwort = await caller.create(messages=[{"role": "user", "content": "x"}], temperature=0.1)

    assert antwort.choices[0].message.content == "ok"
    assert client.optionen[0]["timeout"] == SUMMARY_CALL_TIMEOUT_SECONDS
    assert client.optionen[0]["temperature"] == 0.1


async def test_der_aufrufer_bucht_jede_antwort():
    gebucht = []
    caller = Caller(FakeClient(["a", "b"]), "m", book=gebucht.append)

    await caller.create(messages=[])
    await caller.create(messages=[])

    assert len(gebucht) == 2


def test_die_grundregeln_nennen_die_sprache():
    assert "Write in German." in GROUND_RULES.format(language="German")


def test_eine_leere_gliederung_hat_keine_abschnitte():
    assert Outline().sections == []
    assert Section(title="A").scope == ""
