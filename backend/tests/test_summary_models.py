"""The caller is the one place a model call gets its timeout and its booking."""

import pytest

from tests.summary_helpers import FakeClient

from src.features.summary.models import GROUND_RULES, Caller, Outline, Section
from src.limits import SUMMARY_CALL_TIMEOUT_SECONDS


@pytest.fixture(autouse=True)
def _leerer_adminbereich(monkeypatch):
    """Without an entry the value from limits.py applies, the shared database stays out of it."""
    monkeypatch.setattr("src.database.get_setting", lambda key, default="": default)


class _ClientDerOptionenMerkt(FakeClient):
    """Records what the caller asks of the client before the call."""

    def __init__(self, antworten):
        super().__init__(antworten)
        self.client_optionen = []

    def with_options(self, **optionen):
        self.client_optionen.append(optionen)
        return self


async def test_der_aufrufer_setzt_modell_und_zeitgrenze():
    client = FakeClient(["ok"])
    caller = Caller(client, "m")

    antwort = await caller.create(messages=[{"role": "user", "content": "x"}], temperature=0.1)

    assert antwort.choices[0].message.content == "ok"
    assert client.optionen[0]["timeout"] == SUMMARY_CALL_TIMEOUT_SECONDS
    assert client.optionen[0]["temperature"] == 0.1


async def test_die_zeitgrenze_kommt_aus_dem_adminbereich(monkeypatch):
    """A change in the admin panel takes effect on the next call, without restart."""
    monkeypatch.setattr("src.database.get_setting", lambda key, default="": "120")
    client = FakeClient(["ok"])

    await Caller(client, "m").create(messages=[])

    assert client.optionen[0]["timeout"] == 120


async def test_der_aufrufer_bucht_jede_antwort():
    gebucht = []
    caller = Caller(FakeClient(["a", "b"]), "m", book=gebucht.append)

    await caller.create(messages=[])
    await caller.create(messages=[])

    assert len(gebucht) == 2


async def test_der_aufrufer_wiederholt_nicht_selbsttaetig():
    client = _ClientDerOptionenMerkt(["ok"])
    caller = Caller(client, "m")

    await caller.create(messages=[])

    assert client.client_optionen == [{"max_retries": 0}]


async def test_ohne_auftrags_id_bleiben_langfuse_felder_weg():
    client = FakeClient(["ok"])
    await Caller(client, "m").create(messages=[])
    assert "session_id" not in client.optionen[0]
    assert "tags" not in client.optionen[0]


async def test_mit_auftrags_id_gruppiert_sich_jeder_aufruf_darunter():
    client = FakeClient(["ok", "ok"])
    caller = Caller(client, "m", job_uuid="job-abc")

    await caller.create(messages=[])
    await caller.create(messages=[], name="outline")

    assert [o["session_id"] for o in client.optionen] == ["job-abc", "job-abc"]
    assert all(o["tags"] == ["summary"] for o in client.optionen)
    assert client.optionen[1]["name"] == "outline"


def test_der_timeout_bleibt_unter_der_grenze_des_anbieters():
    """Measured 20.09.: myLab drops a call at about 300 s with a bare 500.

    Our own limit has to fire first, else every long call fails as a server error
    instead of a timeout we can retry deliberately.
    """
    assert SUMMARY_CALL_TIMEOUT_SECONDS < 300


def test_die_grundregeln_nennen_die_sprache():
    assert "Write in German." in GROUND_RULES.format(language="German")


def test_eine_leere_gliederung_hat_keine_abschnitte():
    assert Outline().sections == []
    assert Section(title="A").scope == ""
