"""Fakes fuer die Tests des Fakten-Dienstes, kein Modell und kein Auftragsordner noetig."""

import asyncio


class MemoryFactStore:
    """Ein FactStore im Arbeitsspeicher, er merkt sich auch die Reihenfolge der Schreibvorgaenge."""

    def __init__(self, vorhanden: dict | None = None) -> None:
        self.extractions = dict(vorhanden or {})
        self.geschrieben: list[str] = []
        self.schritte: list[tuple] = []
        self.pulse = 0

    def load_extractions(self) -> dict[str, list[dict]]:
        return dict(self.extractions)

    def save_extraction(self, source_id: str, facts: list[dict]) -> None:
        self.extractions[source_id] = facts
        self.geschrieben.append(source_id)

    def progress(self, step: str, part=None, total=None) -> None:
        self.schritte.append((step, part, total))

    def heartbeat(self) -> None:
        self.pulse += 1


class Leser:
    """Ein Lesevorgang je Quelle, er zaehlt nebenbei, wie viele zugleich unterwegs sind."""

    def __init__(self, je_quelle: dict, dauer: float = 0.01) -> None:
        self._je_quelle = {sid: list(werte) for sid, werte in je_quelle.items()}
        self._dauer = dauer
        self.gefragt: list[str] = []
        self.gleichzeitig = 0
        self.hoechststand = 0

    async def __call__(self, quelle: dict):
        sid = quelle["source_id"]
        self.gefragt.append(sid)
        self.gleichzeitig += 1
        self.hoechststand = max(self.hoechststand, self.gleichzeitig)
        try:
            await asyncio.sleep(self._dauer)
            naechste = self._je_quelle[sid].pop(0)
            if isinstance(naechste, Exception):
                raise naechste
            return naechste
        finally:
            self.gleichzeitig -= 1


class Abgewiesen(Exception):
    """Eine Absage des Anbieters, so wie sie beim echten Aufruf ankommt."""

    def __init__(self, status: int = 429) -> None:
        super().__init__("zu viel")
        self.status_code = status


def quelle(nr: int) -> dict:
    return {"source_id": f"doc_{nr:02d}", "filename": f"{nr}.pdf"}


def fakten(*aussagen: str) -> list[dict]:
    return [{"category": "figure", "fact": a, "citation": f"Beleg {a}"} for a in aussagen]
