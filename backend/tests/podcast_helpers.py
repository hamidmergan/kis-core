"""Fakes fuer die Fakten-Wege des Podcasts, kein Modell und kein Auftragsordner noetig."""

import asyncio
import json


class FakeAntwort:
    def __init__(self, text, finish_reason="stop"):
        self.choices = [type("C", (), {
            "message": type("M", (), {"content": text})(),
            "finish_reason": finish_reason,
        })()]
        self.usage = type("U", (), {"prompt_tokens": 10, "completion_tokens": 20})()


class FakeAsyncClient:
    """Die asynchrone Tuer des Chat-Clients, sie antwortet je Datei statt der Reihe nach."""

    def __init__(self, je_datei: dict, dauer: float = 0.0) -> None:
        self._je_datei = {name: list(werte) for name, werte in je_datei.items()}
        self._dauer = dauer
        self.gesendet: list[list[dict]] = []
        self.optionen: list[dict] = []
        self.gleichzeitig = 0
        self.hoechststand = 0
        self.chat = type("Chat", (), {"completions": self})()

    def with_options(self, **_):
        return self

    async def create(self, *, model, messages, **kwargs):
        self.gesendet.append(messages)
        self.optionen.append(kwargs)
        self.gleichzeitig += 1
        self.hoechststand = max(self.hoechststand, self.gleichzeitig)
        try:
            await asyncio.sleep(self._dauer)
            datei = next((n for n in self._je_datei if f"({n})" in messages[-1]["content"]), None)
            if datei is None:
                raise AssertionError(
                    f"Keine Antwort hinterlegt fuer {messages[-1]['content'][:80]}")
            naechste = self._je_datei[datei].pop(0)
            if isinstance(naechste, Exception):
                raise naechste
            return FakeAntwort(naechste)
        finally:
            self.gleichzeitig -= 1

    def system_prompts(self) -> list[str]:
        return [m[0]["content"] for m in self.gesendet]

    def user_prompts(self) -> list[str]:
        return [m[1]["content"] for m in self.gesendet]


class Abgewiesen(Exception):
    def __init__(self, status: int = 429) -> None:
        super().__init__("zu viel")
        self.status_code = status


def quelle(nr: int, text: str = "Inhalt der Quelle.") -> dict:
    return {"source_id": f"doc_{nr:02d}", "filename": f"{nr}.pdf", "content": text}


def fakten_antwort(*aussagen: str) -> str:
    return json.dumps({"facts": [
        {"category": "Kernaussage", "fact": a, "citation": f"Beleg {a}", "reference": ""}
        for a in aussagen]})
