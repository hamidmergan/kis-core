"""Quellenchip der Grammatik-Übung: gestaffelte Herkunft statt reiner Rücksuche.

Die Sätze werden neu erfunden, deshalb findet die nachträgliche pgvector-Suche sie
oft nicht wieder und ein Set kam mit Chips bei der Hälfte der Sätze heraus. Hier
zählt die Reihenfolge: was das Modell selbst nennt schlägt die Suche, und die
Sektion fängt den Rest ab.

Kein DB- und kein Netzzugriff: Embedding, Suche und die Whisper-Segmente werden
hineingereicht.
"""

import pytest

from src.features.ai_assistant.tasks.language_training._attribution import attach_chips_cited
from src.features.ai_assistant.tasks.language_training._context import QuelleContext


def _boom(*args, **kwargs):
    raise AssertionError("attribution must not search here")


def _one_source_ctx():
    return QuelleContext(
        context="",
        first_label="A.pdf",
        multi_label="A.pdf",
        source_hint="x",
        sections={1: "A.pdf"},
        source_by_name={"A.pdf": {"id": 1, "workspace_id": 7}},
        seen_pages_by_source={1: {4, 5, 9}},
    )


def _two_source_ctx():
    return QuelleContext(
        context="",
        first_label="A.pdf",
        multi_label="2 Sources",
        source_hint="x",
        sections={1: "A.pdf", 2: "B.pdf"},
        source_by_name={
            "A.pdf": {"id": 1, "workspace_id": 7},
            "B.pdf": {"id": 2, "workspace_id": 7},
        },
        seen_pages_by_source={1: {4, 5}, 2: {7, 8}},
    )


def _media_ctx():
    return QuelleContext(
        context="",
        first_label="V.mp4",
        multi_label="V.mp4",
        source_hint="x",
        sections={1: "V.mp4"},
        source_by_name={"V.mp4": {"id": 3, "workspace_id": 7}},
        seen_pages_by_source={3: {7, 8}},
        media_start_by_page={3: {7: 91.5, 8: 140.0}},
    )


def _embed(texts):
    return [[1.0, 0.0] for _ in texts]


def _no_segments(source_id):
    """Keine Whisper-Segmente bekannt, also bleibt die Zeitmarke am Chunk-Anfang.

    Ein Medien-Treffer holt sich sonst die Segmente der Quelle aus der Datenbank, um die
    Zeitmarke auf den zitierten Satz zu ruecken. Ohne diesen Ersatz haengen die Tests
    unten an DATABASE_URL, was hier nichts zu suchen hat."""
    return []


def _hit(source_id, page, distance=0.2, start_time=None):
    return {"source_id": source_id, "page_number": page, "content": "lorem ipsum " * 20,
            "vec_distance": distance, "start_time": start_time}


# ─── Stufe 1: die Seite, die das Modell selbst nennt ──────────────────────────

def test_the_page_the_model_cited_becomes_the_chip_without_any_search():
    """Der eigentliche Punkt der Umstellung: das Modell weiß beim Schreiben, aus
    welcher Passage der Satz stammt. Die Suche läuft dann gar nicht erst."""
    items = [{"front": "S", "back": "T", "_page": 5}]
    out = attach_chips_cited(items, ["T"], _one_source_ctx(),
                             embed_fn=_boom, search_fn=_boom)
    assert out[0]["sources"] == [{"source_label": "A.pdf", "page_number": 5, "start_time": None}]
    assert out[0]["source_label"] == "A.pdf"
    assert out[0]["page_number"] == 5


def test_a_cited_page_is_matched_to_the_source_that_actually_has_it():
    # Zwei Quellen, das Modell nennt nur die Seite. Nur B.pdf hat Seite 8 gezeigt.
    items = [{"front": "S", "back": "T", "_page": 8}]
    out = attach_chips_cited(items, ["T"], _two_source_ctx(),
                             embed_fn=_boom, search_fn=_boom)
    assert out[0]["source_label"] == "B.pdf"
    assert out[0]["page_number"] == 8


def test_the_named_section_decides_when_two_sources_share_a_page_number():
    # Beide Quellen hätten Seite 4, die Sektion löst es auf.
    ctx = _two_source_ctx()
    ctx.seen_pages_by_source = {1: {4}, 2: {4}}
    items = [{"front": "S", "back": "T", "_page": 4, "_section": 2}]
    out = attach_chips_cited(items, ["T"], ctx, embed_fn=_boom, search_fn=_boom)
    assert out[0]["source_label"] == "B.pdf"
    assert out[0]["page_number"] == 4


def test_a_page_the_model_never_saw_is_not_trusted():
    """Sonst wäre die Angabe eine erfundene Seite. Seite 42 stand nie im Kontext,
    also greift die Suche und deren Treffer gewinnt."""
    items = [{"front": "S", "back": "T", "_page": 42}]
    out = attach_chips_cited(items, ["T"], _one_source_ctx(),
                             embed_fn=_embed, search_fn=lambda t, v: [_hit(1, 4)])
    assert out[0]["page_number"] == 4


@pytest.mark.parametrize("cited", ["Seite 4", None, "", -1, 0, True])
def test_a_page_that_is_not_a_plain_number_falls_through(cited):
    items = [{"front": "S", "back": "T", "_page": cited}]
    out = attach_chips_cited(items, ["T"], _one_source_ctx(),
                             embed_fn=_embed, search_fn=lambda t, v: [_hit(1, 9)])
    assert out[0]["page_number"] == 9


def test_a_page_written_as_a_string_of_digits_still_counts():
    # Modelle liefern Zahlen im JSON regelmässig als Text zurück.
    items = [{"front": "S", "back": "T", "_page": "5"}]
    out = attach_chips_cited(items, ["T"], _one_source_ctx(),
                             embed_fn=_boom, search_fn=_boom)
    assert out[0]["page_number"] == 5


# ─── Stufe 2: die alte Rücksuche ──────────────────────────────────────────────

def test_search_runs_only_for_the_items_the_model_could_not_place():
    """Die Suche kostet einen Embedding-Call plus eine Vektorsuche pro Satz. Sie
    darf nur die Sätze sehen, die Stufe 1 offen gelassen hat."""
    embedded, searched = [], []

    def embed_fn(texts):
        embedded.extend(texts)
        return [[1.0, 0.0] for _ in texts]

    def search_fn(text, vec):
        searched.append(text)
        return [_hit(1, 4)]

    items = [
        {"front": "a", "back": "A", "_page": 5},
        {"front": "b", "back": "B"},
        {"front": "c", "back": "C", "_page": 9},
    ]
    out = attach_chips_cited(items, ["A", "B", "C"], _one_source_ctx(),
                             embed_fn=embed_fn, search_fn=search_fn)
    assert embedded == ["B"]
    assert searched == ["B"]
    assert [i["page_number"] for i in out] == [5, 4, 9]


# ─── Stufe 3: die Sektion als Auffangnetz ─────────────────────────────────────

def test_without_a_page_and_without_a_search_hit_the_chip_points_at_the_source():
    """Kein Satz ohne Chip: die Datei steht bei einer Quelle immer fest, also
    zeigt der Chip auf deren erste gezeigte Seite."""
    items = [{"front": "S", "back": "T"}]
    out = attach_chips_cited(items, ["T"], _one_source_ctx(),
                             embed_fn=_embed, search_fn=lambda t, v: [])
    assert out[0]["source_label"] == "A.pdf"
    assert out[0]["page_number"] == 4


def test_the_named_section_carries_the_chip_when_everything_else_fails():
    items = [{"front": "S", "back": "T", "_section": 2}]
    out = attach_chips_cited(items, ["T"], _two_source_ctx(),
                             embed_fn=_embed, search_fn=lambda t, v: [])
    assert out[0]["source_label"] == "B.pdf"
    assert out[0]["page_number"] == 7


def test_a_multi_source_item_with_no_signal_at_all_stays_without_a_chip():
    """Die eine verbleibende Lücke, bewusst offen gelassen: mehrere Quellen, das
    Modell nennt weder Seite noch Sektion, die Suche findet nichts. Eine Quelle zu
    raten wäre schlimmer als kein Chip."""
    items = [{"front": "S", "back": "T"}]
    out = attach_chips_cited(items, ["T"], _two_source_ctx(),
                             embed_fn=_embed, search_fn=lambda t, v: [])
    assert "sources" not in out[0]
    assert out[0]["source_label"] is None
    assert out[0]["page_number"] is None


# ─── Ton und Video ────────────────────────────────────────────────────────────

def test_a_cited_segment_number_is_not_trusted_for_media():
    """An echten Sets gemessen: für ein Video schreibt das Modell irgendeine
    Abschnitts-Nummer hin, dreimal dieselbe für drei verschiedene Sätze, und der
    Inhalt dort passt nicht. Bei einer Folienseite stimmt es, bei 105 gleich
    aussehenden 30-Sekunden-Blöcken nicht. Also zählt hier nur die Suche, die
    echten Transkript-Text vergleicht."""
    items = [{"front": "S", "back": "T", "_page": 7}]
    out = attach_chips_cited(items, ["T"], _media_ctx(),
                             embed_fn=_embed,
                             search_fn=lambda t, v: [_hit(3, 8, start_time=140.0)],
                             segments_fn=_no_segments)
    assert out[0]["start_time"] == 140.0
    assert out[0]["page_number"] is None


def test_a_search_hit_still_cites_media_by_timestamp():
    items = [{"front": "S", "back": "T"}]
    out = attach_chips_cited(items, ["T"], _media_ctx(),
                             embed_fn=_embed,
                             search_fn=lambda t, v: [_hit(3, 7, start_time=91.5)],
                             segments_fn=_no_segments)
    assert out[0]["sources"] == [
        {"source_label": "V.mp4", "page_number": None, "start_time": 91.5}]


def test_media_without_a_search_hit_cites_the_file_and_no_time():
    """Eine falsche Minute in einer 45-Minuten-Aufnahme ist schlimmer als keine.
    Der Chip sagt dann nur noch, aus welcher Datei der Stoff kommt."""
    items = [{"front": "S", "back": "T"}]
    out = attach_chips_cited(items, ["T"], _media_ctx(),
                             embed_fn=_embed, search_fn=lambda t, v: [])
    assert out[0]["sources"] == [
        {"source_label": "V.mp4", "page_number": None, "start_time": None}]
    assert out[0]["source_label"] == "V.mp4"
    assert out[0]["start_time"] is None
    assert out[0]["page_number"] is None


def test_a_pdf_in_the_same_set_keeps_the_cited_page():
    # Die Trennung läuft pro Quelle, nicht pro Set: das Handout behält seine Seite,
    # auch wenn im selben Set ein Video hängt.
    ctx = _media_ctx()
    ctx.sections = {1: "V.mp4", 2: "A.pdf"}
    ctx.source_by_name["A.pdf"] = {"id": 1, "workspace_id": 7}
    ctx.seen_pages_by_source[1] = {4, 5}
    items = [{"front": "S", "back": "T", "_page": 5}]
    out = attach_chips_cited(items, ["T"], ctx, embed_fn=_boom, search_fn=_boom)
    assert out[0]["source_label"] == "A.pdf"
    assert out[0]["page_number"] == 5


# ─── Aufräumen ────────────────────────────────────────────────────────────────

def test_the_cited_page_never_reaches_the_database_row():
    # finalize_exercise_set liest nur bekannte Schlüssel, aber die Hilfsfelder
    # sollen den Aufrufer gar nicht erst erreichen.
    items = [{"front": "S", "back": "T", "_page": 5, "_section": 1}]
    out = attach_chips_cited(items, ["T"], _one_source_ctx(),
                             embed_fn=_boom, search_fn=_boom)
    assert "_page" not in out[0]


def test_a_failing_embedding_call_still_leaves_every_item_with_a_chip():
    """Das geteilte Anbieter-Limit wirft regelmässig 429. Vorher war dann das ganze
    Set chiplos, jetzt fängt die Sektion es ab."""
    def embed_fn(texts):
        raise RuntimeError("429 rate limit")

    items = [{"front": "S", "back": "T"}]
    out = attach_chips_cited(items, ["T"], _one_source_ctx(),
                             embed_fn=embed_fn, search_fn=_boom)
    assert out[0]["source_label"] == "A.pdf"
    assert out[0]["page_number"] == 4
