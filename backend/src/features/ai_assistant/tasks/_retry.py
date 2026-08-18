"""Wiederholt einen gestörten Modell-Aufruf, ohne den Anbieter zusätzlich zu belasten.

Am 2026-08-05 ist ein Übungs-Set nach 23 Sekunden an einem einzelnen "Connection error"
gestorben, obwohl der erste Lauf schon 14 fertige Aufgaben geliefert hatte. Ein solcher
Aussetzer ist kein Grund, die Arbeit wegzuwerfen.

Zwei Entscheidungen tragen dieses Modul:

* **Wiederholt wird nur, was ohne Zutun des Aufrufs schiefging**, also eine abgerissene
  Verbindung, eine Zeitüberschreitung oder ein Fehler des Anbieters. Ein fehlerhafter
  Aufruf (400er) scheitert beim zweiten Mal genauso, nur später.
* **Eine Absage wegen Überlastung (429) wird NIE wiederholt.** Ein sofortiger zweiter
  Versuch verschärft genau den Engpass, der zur Absage geführt hat. Deshalb
  steht der Client auch weiterhin auf ``max_retries=0``: die eingebaute Wiederholung des
  SDK macht diese Unterscheidung nicht.

Die Wiederholung hängt am Client und nicht an den dreizehn Aufrufstellen. So bekommt
jedes Werkzeug sie, ohne dass eine Stelle vergessen werden kann.

Bewusst NICHT für den Chat: dort läuft die Antwort im Strom zum Browser, und eine
stille Pause von Sekunden mitten im Satz ist etwas anderes als in einem Hintergrund-
Auftrag. ``_get_llm_client`` bedient nur die Aufträge.
"""

import time

from loguru import logger


# Drei Versuche. Danach steht der Fehlschlag und der Aufrufer muss retten, was fertig ist.
# Mehr Versuche helfen nicht: hält die Störung drei Anläufe durch, ist sie keine Störung
# mehr, sondern ein Ausfall.
ATTEMPTS = 3

# Pause vor dem zweiten und dem dritten Versuch. Sofort nochmal zu fragen trifft dieselbe
# Störung, und die Pausen zusammen (8 s) passen bequem in das Zeitlimit der Werkzeuge.
BACKOFF_SECONDS = (2, 6)


def is_retryable(exc: Exception) -> bool:
    """Ob ein zweiter Versuch überhaupt eine Chance hat.

    Im Zweifel nein: ein unbekannter Fehler ist eher ein Programmierfehler, und der
    wiederholt sich nur.
    """
    status = getattr(exc, "status_code", None)
    if status is not None:
        # 429 ist hier der eigentliche Grund für die Fallunterscheidung, siehe Modulkopf.
        return status >= 500
    try:
        import openai
    except ImportError:  # pragma: no cover - openai gehört zu den Abhängigkeiten
        return False
    return isinstance(exc, openai.APIConnectionError)


def call_with_retry(func, *args, sleep_fn=time.sleep, **kwargs):
    """Ruft ``func`` auf und wiederholt bei einer Störung bis zu :data:`ATTEMPTS` Mal.

    Der letzte Fehler wird weitergereicht, damit der Aufrufer ihn sieht und retten kann,
    was bis dahin fertig ist.
    """
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == ATTEMPTS or not is_retryable(e):
                raise
            wait = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS)) - 1]
            logger.warning(
                "KI Tutor: Modell-Aufruf gestört ({}), Versuch {} von {} in {} s: {}",
                type(e).__name__, attempt + 1, ATTEMPTS, wait, e,
            )
            sleep_fn(wait)


class _Completions:
    """Nur ``create`` wird abgefangen, alles andere geht durch."""

    def __init__(self, inner, sleep_fn):
        self._inner = inner
        self._sleep_fn = sleep_fn

    def create(self, *args, **kwargs):
        return call_with_retry(self._inner.create, *args, sleep_fn=self._sleep_fn, **kwargs)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _Chat:
    def __init__(self, inner, sleep_fn):
        self._inner = inner
        self.completions = _Completions(inner.completions, sleep_fn)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class RetryingClient:
    """Reicht alles an den echten Client durch, nur der Modell-Aufruf wird wiederholt.

    Ein Hüllobjekt statt eines Eingriffs am Client selbst: der OpenAI-Client ist nicht
    dafür gebaut, dass man ihm Methoden austauscht, und die Langfuse-Fassung darum herum
    erst recht nicht.
    """

    def __init__(self, inner, sleep_fn=time.sleep):
        self._inner = inner
        self.chat = _Chat(inner.chat, sleep_fn)

    def __getattr__(self, name):
        return getattr(self._inner, name)
