"""Fakes for the summary tests, so conftest stays small."""

import asyncio


class FakeAntwort:
    def __init__(self, text, finish_reason="stop"):
        self.choices = [type("C", (), {
            "message": type("M", (), {"content": text})(),
            "finish_reason": finish_reason,
        })()]


class FakeClient:
    """A queue of canned answers or exceptions, and every call actually made."""

    def __init__(self, antworten):
        self._antworten = list(antworten)
        self.gesendet = []
        self.optionen = []
        self.chat = type("Chat", (), {"completions": self})()

    async def create(self, *, model, messages, **kwargs):
        await asyncio.sleep(0)
        self.gesendet.append(messages)
        self.optionen.append(kwargs)
        naechste = self._antworten.pop(0)
        if isinstance(naechste, Exception):
            raise naechste
        if isinstance(naechste, tuple):
            return FakeAntwort(*naechste)
        return FakeAntwort(naechste)

    def system_prompts(self):
        return [m[0]["content"] for m in self.gesendet]

    def user_prompts(self):
        return [m[1]["content"] for m in self.gesendet]


class MemoryStore:
    """A RunStore that keeps everything in memory."""

    def __init__(self):
        self.language = None
        self.extractions = {}
        self.outline = None
        self.sections = {}
        self.schritte = []
        self.pulse = 0

    def load_language(self):
        return self.language

    def save_language(self, language):
        self.language = language

    def load_extractions(self):
        return dict(self.extractions)

    def save_extraction(self, source_id, text):
        self.extractions[source_id] = text

    def load_outline(self):
        return self.outline

    def save_outline(self, outline):
        self.outline = outline

    def load_sections(self):
        return dict(self.sections)

    def save_section(self, index, text):
        self.sections[index] = text

    def progress(self, step, part=None, total=None):
        self.schritte.append((step, part, total))

    def heartbeat(self):
        self.pulse += 1
