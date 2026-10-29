"""Pages, chunks, places and chats of the campus assistant against the real schema."""
import os
import uuid

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from src.features.campus.repository import chats, chunks, pages, places  # noqa: E402


@pytest.fixture(scope="module")
def verbindung():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("kein DATABASE_URL gesetzt (Test braucht echtes Postgres)")
    from src.core.db.pool import get_connection
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception as fehler:  # pragma: no cover
        pytest.skip(f"Datenbank nicht erreichbar: {fehler}")
    return get_connection


@pytest.fixture
def nutzer_id(verbindung):
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users ORDER BY id LIMIT 1")
            row = cur.fetchone()
    if not row:
        pytest.skip("kein Nutzer in der Datenbank")
    return row[0]


@pytest.fixture
def seite(verbindung):
    url = f"https://example.test/{uuid.uuid4().hex}/"
    page_id = pages.upsert_page(pages.KIND_PAGE, url, title="Testseite")
    yield page_id, url
    pages.delete_page(page_id)


def test_seite_anlegen_ist_idempotent(seite):
    page_id, url = seite
    assert pages.upsert_page(pages.KIND_PAGE, url) == page_id
    assert pages.get_page_by_url(url)["title"] == "Testseite"


def test_chunks_ersetzen_und_per_stichwort_finden(seite):
    page_id, url = seite
    kennwort = "Zxqwortmarke" + uuid.uuid4().hex[:6]
    ids = chunks.replace_chunks(page_id, [
        {"position": 0, "heading": "Eins", "content": f"Erster Abschnitt mit {kennwort} drin."},
        {"position": 1, "heading": "Zwei", "content": "Zweiter Abschnitt ohne das Wort."},
    ])
    assert len(ids) == 2
    treffer = chunks.hybrid_search(kennwort, None, limit=5)
    assert [t["id"] for t in treffer] == [ids[0]]
    assert treffer[0]["url"] == url and treffer[0]["kw_hit"] is True
    nachbarn = chunks.neighbors(page_id, 0)
    assert [n["position"] for n in nachbarn] == [1]
    # Replacing again leaves exactly the new chunks.
    chunks.replace_chunks(page_id, [{"position": 0, "heading": None, "content": "nur noch einer"}])
    assert chunks.neighbors(page_id, 0) == []


def test_orte_werden_als_ganzes_ersetzt(verbindung):
    vorher = places.all_places()
    try:
        places.replace_places([{"id": "T_1", "code": "T.1", "kind": "building", "title": {"de": "Test", "en": "Test"}}])
        alle = places.all_places()
        assert [p["id"] for p in alle] == ["T_1"]
        assert alle[0]["title"]["de"] == "Test"
    finally:
        places.replace_places(vorher)


def test_chats_kappung_und_aufraeumen(nutzer_id, verbindung):
    angelegt = [chats.create_chat(nutzer_id, f"Chat {i}") for i in range(3)]
    try:
        chats.touch_chat(angelegt[0])
        # Only the two most recently used chats of this person survive a cap of two.
        meine = [c["id"] for c in chats.list_chats(nutzer_id)]
        assert meine[0] == angelegt[0]
        weg = chats.enforce_chat_cap(nutzer_id, 2)
        assert weg == len(meine) - 2
        assert chats.get_chat(angelegt[1], nutzer_id) is None
        assert chats.get_chat(angelegt[0], nutzer_id) is not None
        chat_id = angelegt[0]
        assert chats.count_question(chat_id) == 1
        chats.add_message(chat_id, "user", "Wo ist die Mensa?")
        antwort = chats.add_message(chat_id, "assistant", "In B.59.", sources=[{"url": "u"}], places=[{"id": "Mensa_B_59"}])
        assert chats.last_rounds(chat_id, 1) == [("Wo ist die Mensa?", "In B.59.")]
        gelesen = chats.list_messages(chat_id)
        assert gelesen[-1]["places"] == [{"id": "Mensa_B_59"}]
        assert chats.rename_chat(chat_id, nutzer_id, "Neu") and chats.get_chat(chat_id, nutzer_id)["title"] == "Neu"
        assert chats.prune_chats(0) == 0
        # A chat idle for a year goes, the one touched today stays.
        alt = chats.create_chat(nutzer_id, "Alt")
        angelegt.append(alt)
        with verbindung() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE campus_chats SET updated_at = NOW() - interval '400 days' WHERE id = %s", (alt,))
            conn.commit()
        assert chats.prune_chats(365) >= 1
        assert chats.get_chat(alt, nutzer_id) is None
        assert chats.get_chat(chat_id, nutzer_id) is not None
    finally:
        for cid in angelegt:
            chats.delete_chat(cid, nutzer_id)
