"""Whether a job is still at the broker: waiting in the queue or fetched and unacked."""

import json

from src.services import broker_state


def _nachricht(task_id):
    return json.dumps({"headers": {"id": task_id, "task": "summary.run"}, "body": "e30="})


class _Redis:
    def __init__(self, schlangen=None, unquittiert=None):
        self.schlangen = schlangen or {}
        self.unquittiert = unquittiert or {}

    def lrange(self, name, start, end):
        return [n.encode() for n in self.schlangen.get(name, [])]

    def hvals(self, name):
        if name != "unacked":
            return []
        return [json.dumps([json.loads(n), "", "general"]).encode() for n in self.unquittiert.values()]


def test_ein_auftrag_in_der_schlange_wartet():
    r = _Redis(schlangen={"general": [_nachricht("t-1"), _nachricht("t-2")]})
    stand = broker_state.snapshot(r)
    assert stand.waiting >= {"t-1", "t-2"}
    assert stand.taken == set()


def test_ein_abgeholter_auftrag_ist_genommen_und_wartet_nicht():
    r = _Redis(unquittiert={"tag-1": _nachricht("t-9")})
    stand = broker_state.snapshot(r)
    assert "t-9" in stand.taken
    assert "t-9" not in stand.waiting
    assert stand.holds("t-9")


def test_ein_verlorener_auftrag_fehlt():
    r = _Redis(schlangen={"general": [_nachricht("t-1")]})
    assert not broker_state.snapshot(r).holds("t-weg")


def test_ein_auftrag_ohne_nummer_gilt_als_nicht_gehalten():
    r = _Redis(schlangen={"general": [_nachricht("t-1")]})
    assert not broker_state.snapshot(r).holds(None)


def test_kaputte_nachrichten_stoeren_nicht():
    r = _Redis(schlangen={"general": ["kein json", _nachricht("t-1")]})
    assert "t-1" in broker_state.snapshot(r).waiting


def test_ohne_broker_gibt_es_keine_antwort_statt_einer_leeren_menge():
    class _Kaputt:
        def lrange(self, *a):
            raise ConnectionError("weg")

    # None means "unknown", then nobody may declare a job lost.
    assert broker_state.snapshot(_Kaputt()) is None


def test_ein_auftrag_mit_niedrigem_vorrang_wartet_auch():
    """The summary sits in a side list of its queue, the watchdog must not consider it lost."""
    r = _Redis(schlangen={"general\x06\x169": [_nachricht("t-7")]})
    assert "t-7" in broker_state.snapshot(r).waiting
