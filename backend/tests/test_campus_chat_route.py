"""Der Chat-Stream: Titel, Absage-Marker, Quellen und Orte, volle Chats."""
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.features.campus.routes import chat as chat_route
from src.features.campus.routes._title import make_title
from src.features.campus.services.retrieval import Context


class _Delta:
    def __init__(self, content):
        self.delta = SimpleNamespace(content=content)


class _Chunk:
    def __init__(self, content, usage=None):
        self.choices = [_Delta(content)] if content is not None else []
        self.usage = usage


class _Stream:
    def __init__(self, pieces):
        self._pieces = list(pieces)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._pieces:
            raise StopAsyncIteration
        return self._pieces.pop(0)


class _SyncClient:
    """The pre-call runs on the sync client and answers with a small JSON."""

    def __init__(self, lang):
        self.lang = lang
        self.calls = []

    def with_options(self, **kw):
        return self

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kw):
        self.calls.append(kw)
        content = json.dumps({"query": "Wo ist die Mensa (Gebäude)?", "lang": self.lang})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class _FakeLLM:
    def __init__(self, pieces, lang="German"):
        self._model = "test-model"
        self._provider = "test"
        self._extra_body = None
        self._pieces = pieces
        self._async_client = self
        self._client = _SyncClient(lang)
        self.messages = None

    def sampling(self, standard):
        return {"temperature": standard}

    def with_options(self, **kw):
        return self

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    async def create(self, **kw):
        self.messages = kw["messages"]
        return _Stream(self._pieces)


class _Request:
    async def is_disconnected(self):
        return False


class _Chats:
    def __init__(self):
        self.messages = []
        self.created = []
        self.chat = None

    def get_chat(self, chat_id, user_id):
        return self.chat

    def last_round(self, chat_id):
        return None

    def create_chat(self, user_id, title):
        self.created.append(title)
        return 42

    def enforce_chat_cap(self, user_id, cap):
        return 0

    def add_message(self, chat_id, role, content, sources=None, places=None, no_source=False):
        self.messages.append({"role": role, "content": content, "sources": sources, "places": places, "no_source": no_source})
        return len(self.messages)

    def count_question(self, chat_id):
        return 1

    def drop_oldest_round(self, chat_id):
        self.dropped = chat_id


@pytest.fixture
def umgebung(monkeypatch):
    chats = _Chats()
    monkeypatch.setattr(chat_route, "chat_repo", chats)
    monkeypatch.setattr(chat_route, "enforce_burst", lambda uid, loc: None)
    monkeypatch.setattr(chat_route.provider_transport, "exempt_this_request", lambda: None)
    monkeypatch.setattr(chat_route, "_embed_one", lambda text: [0.0])
    monkeypatch.setattr(chat_route, "log_request", lambda *a, **k: None)
    monkeypatch.setattr(chat_route.chunk_repo, "hybrid_search", lambda q, v, n: [])
    monkeypatch.setattr(chat_route.chunk_repo, "neighbors", lambda p, pos, span: [])
    quelle = {"page_id": 1, "kind": "page", "url": "https://x.test/mensa/", "title": "Mensa", "filename": None, "fetched_at": "2026-10-03", "fragment": "Die Mensa"}
    monkeypatch.setattr(chat_route.retrieval, "build_context", lambda *a, **k: Context(text="<documents/>", sources=[quelle]))
    monkeypatch.setattr(chat_route.place_repo, "all_places", lambda: [{"id": "Mensa_B_59", "code": "B.59", "title": {"de": "Mensa B.59", "en": "Mensa B.59"}}])
    return chats


async def _events(response):
    out = []
    async for raw in response.body_iterator:
        for line in raw.split("\n"):
            if line.startswith("data: "):
                out.append(json.loads(line[6:]))
    return out


async def _frage(llm, chat_id=None, question="Wo ist die Mensa?"):
    body = chat_route.ChatBody(question=question, chat_id=chat_id)
    resp = await chat_route.campus_chat(body, _Request(), current_user={"user_id": 7}, llm=llm, locale="de")
    return await _events(resp)


async def test_antwort_mit_quellen_und_ort(umgebung):
    llm = _FakeLLM([_Chunk("Die Mensa "), _Chunk("ist in B.59."), _Chunk(None, usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5))])
    events = await _frage(llm)
    assert events[0]["meta"] == {"chat_id": 42, "title": "Wo ist die Mensa?"}
    tokens = "".join(e["token"] for e in events if "token" in e)
    assert tokens == "Die Mensa ist in B.59."
    done = events[-1]
    assert done["done"] and done["answer"] == "Die Mensa ist in B.59." and done["no_source"] is False
    assert done["sources"][0]["url"] == "https://x.test/mensa/"
    assert [p["id"] for p in done["places"]] == ["Mensa_B_59"]
    assert umgebung.messages[0]["role"] == "user" and umgebung.messages[1]["places"][0]["show"] == "B.59"
    # The pre-call ran once and its language reached both prompts.
    assert len(llm._client.calls) == 1
    assert "German" in llm.messages[0]["content"] and "REMINDER: write the whole answer in German" in llm.messages[1]["content"]


async def test_kaputter_vor_call_stoert_nicht(umgebung):
    llm = _FakeLLM([_Chunk("Antwort.")])
    llm._client.create = lambda **kw: (_ for _ in ()).throw(RuntimeError("weg"))
    events = await _frage(llm)
    assert events[-1]["answer"] == "Antwort."
    assert "REMINDER" not in llm.messages[1]["content"]


async def test_absage_marker_wird_entfernt_und_quellen_bleiben_leer(umgebung):
    llm = _FakeLLM([_Chunk("NO_SO"), _Chunk("URCE: Dazu steht nichts in den Quellen. Frag beim Service-Point.")])
    events = await _frage(llm)
    tokens = "".join(e["token"] for e in events if "token" in e)
    assert tokens == "Dazu steht nichts in den Quellen. Frag beim Service-Point."
    done = events[-1]
    assert done["no_source"] is True and done["sources"] == [] and done["places"] == []


async def test_normale_antwort_ohne_marker_kommt_sofort(umgebung):
    llm = _FakeLLM([_Chunk("Ja, "), _Chunk("das geht.")])
    events = await _frage(llm)
    assert [e["token"] for e in events if "token" in e] == ["Ja, ", "das geht."]


async def test_voller_chat_wirft_die_aelteste_runde_weg(umgebung):
    umgebung.chat = {"id": 5, "title": "Alt", "question_count": chat_route.CAMPUS_MAX_QUESTIONS_PER_CHAT}
    await _frage(_FakeLLM([_Chunk("Ja.")]), chat_id=5)
    assert umgebung.dropped == 5


async def test_fremder_chat_ist_unbekannt(umgebung):
    umgebung.chat = None
    with pytest.raises(HTTPException) as info:
        await _frage(_FakeLLM([]), chat_id=99)
    assert info.value.status_code == 404


async def test_leere_antwort_meldet_fehler(umgebung):
    events = await _frage(_FakeLLM([_Chunk("")]))
    assert events[-1]["code"] == "empty_answer"


def test_titel_wird_am_wort_gekuerzt():
    assert make_title("Wann ist die Rückmeldefrist?") == "Wann ist die Rückmeldefrist?"
    lang = make_title("Wie beantrage ich eine Verlängerung der Abgabefrist für meine Bachelorarbeit im Sommersemester?")
    assert lang.endswith("…") and len(lang) <= 61 and " " in lang and not lang.endswith(" …")


def test_ortsseiten_treten_hinter_die_ortskarte():
    seiten = [{"kind": "place", "title": "Mensa"}, {"kind": "page", "title": "Wohnen"}, {"kind": "place", "title": "Cafeteria"}]
    assert chat_route.pick_sources(seiten, [{"id": "Mensa_B_59"}]) == [{"kind": "page", "title": "Wohnen"}]
    assert chat_route.pick_sources(seiten, []) == seiten
    viele = [{"kind": "page", "title": str(i)} for i in range(9)]
    assert len(chat_route.pick_sources(viele, [])) == chat_route.CAMPUS_SOURCE_CARDS_MAX


def test_marker_trennung():
    assert chat_route.split_marker("NO_SOURCE: nix") == (True, "nix")
    assert chat_route.split_marker("  NO_SOURCE:nix") == (True, "nix")
    assert chat_route.split_marker("Hallo") == (False, "Hallo")


async def test_abbruch_waehrend_der_suche_schreibt_nichts(umgebung):
    class _Weg:
        async def is_disconnected(self):
            return True

    body = chat_route.ChatBody(question="Wo ist die Mensa?")
    resp = await chat_route.campus_chat(body, _Weg(), current_user={"user_id": 7}, llm=_FakeLLM([]), locale="de")
    assert resp.status_code == 204
    assert umgebung.created == [] and umgebung.messages == []
