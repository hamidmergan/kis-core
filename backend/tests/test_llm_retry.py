"""Wiederholung gestörter Modell-Aufrufe.

Ein Übungs-Set starb heute an einem einzelnen "Connection error" nach 23 Sekunden,
obwohl der erste Lauf schon 14 fertige Aufgaben geliefert hatte. Zwei Dinge müssen
deshalb stimmen: ein gestörter Aufruf wird wiederholt, und eine Absage wegen
Überlastung wird NICHT wiederholt, weil das Kontingent hochschulweit geteilt ist.

Kein Netzzugriff, die Wartezeit wird hineingereicht.
"""

import httpx
import openai
import pytest

from src.features.ai_assistant.tasks._retry import (
    ATTEMPTS,
    RetryingClient,
    is_retryable,
)


_REQ = httpx.Request("POST", "http://example.invalid")


def _status_error(cls, code):
    return cls("x", response=httpx.Response(code, request=_REQ), body=None)


# ─── Welche Störung darf wiederholt werden ───────────────────────────────────

@pytest.mark.parametrize("exc", [
    openai.APIConnectionError(request=_REQ),
    openai.APITimeoutError(request=_REQ),
])
def test_a_broken_connection_is_worth_another_try(exc):
    # Kostet kein Kontingent: die Anfrage kam nie an.
    assert is_retryable(exc)


def test_a_server_fault_is_worth_another_try():
    assert is_retryable(_status_error(openai.InternalServerError, 500))


def test_an_overload_refusal_is_never_repeated():
    """Der wichtigste Fall. Das Anfragen-Kontingent teilt sich die ganze Hochschule.
    Ein sofortiger zweiter Versuch nimmt jemand anderem den Platz weg und verschärft
    genau die Überlastung, die zur Absage geführt hat."""
    assert not is_retryable(_status_error(openai.RateLimitError, 429))


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
def test_a_faulty_request_is_never_repeated(code):
    # Derselbe Aufruf scheitert beim zweiten Mal genauso, nur später.
    assert not is_retryable(_status_error(openai.BadRequestError, code))


def test_an_unknown_error_is_not_repeated():
    # Im Zweifel nicht wiederholen: ein Programmierfehler wiederholt sich nur.
    assert not is_retryable(ValueError("kaputt"))


# ─── Der Client ──────────────────────────────────────────────────────────────

class _Inner:
    """Mindest-Client: zählt Aufrufe und wirft die vorgegebenen Fehler der Reihe nach."""

    def __init__(self, *errors, result="ok"):
        self.calls = 0
        self._errors = list(errors)
        self._result = result
        self.chat = type("C", (), {"completions": self})()

    def create(self, **kwargs):
        self.calls += 1
        if self._errors:
            raise self._errors.pop(0)
        return self._result


def _client(*errors, waits=None):
    inner = _Inner(*errors)
    return inner, RetryingClient(inner, sleep_fn=(waits.append if waits is not None else lambda s: None))


def test_a_disturbed_call_succeeds_on_the_second_try():
    inner, client = _client(openai.APIConnectionError(request=_REQ))
    assert client.chat.completions.create(model="m", messages=[]) == "ok"
    assert inner.calls == 2


def test_it_gives_up_after_three_attempts_and_reraises():
    """Drei Versuche, dann steht der Fehlschlag. Der Aufrufer muss ihn sehen, damit er
    retten kann, was schon fertig ist."""
    errors = [openai.APIConnectionError(request=_REQ) for _ in range(ATTEMPTS)]
    inner, client = _client(*errors)
    with pytest.raises(openai.APIConnectionError):
        client.chat.completions.create(model="m", messages=[])
    assert inner.calls == ATTEMPTS == 3


def test_an_overload_refusal_fails_on_the_first_attempt():
    inner, client = _client(_status_error(openai.RateLimitError, 429))
    with pytest.raises(openai.RateLimitError):
        client.chat.completions.create(model="m", messages=[])
    assert inner.calls == 1


def test_it_waits_longer_before_each_further_attempt():
    # Sofort nochmal fragen trifft dieselbe Störung. Die Pause wächst.
    waits: list = []
    _inner, client = _client(openai.APIConnectionError(request=_REQ),
                             openai.APIConnectionError(request=_REQ), waits=waits)
    client.chat.completions.create(model="m", messages=[])
    assert len(waits) == 2
    assert waits[0] > 0
    assert waits[1] > waits[0]


def test_a_healthy_call_is_made_exactly_once():
    inner, client = _client()
    assert client.chat.completions.create(model="m", messages=[]) == "ok"
    assert inner.calls == 1


def test_everything_else_reaches_the_real_client_untouched():
    # Der Wrapper darf nicht die halbe Schnittstelle verschlucken.
    inner = _Inner()
    inner.embeddings = "E"
    client = RetryingClient(inner, sleep_fn=lambda s: None)
    assert client.embeddings == "E"
