"""Context keeps the budget, one source per page, text fragment from the best chunk."""
from datetime import datetime

from src.features.campus.services import retrieval


def _hit(cid, pid, pos, content, kind="page", url=None, fname=None, heading=None):
    return {"id": cid, "page_id": pid, "position": pos, "content": content, "kind": kind,
            "url": url or f"https://x.test/{pid}/", "title": f"Seite {pid}", "filename": fname,
            "fetched_at": datetime(2026, 10, 3, 12, 0), "heading": heading, "score": 1.0}


def test_quellen_je_seite_in_rangfolge_mit_nachbarn():
    hits = [
        _hit(1, 10, 2, "Treffer A auf Seite zehn.", heading="Rückmeldung"),
        _hit(2, 20, 0, "Treffer B auf Seite zwanzig."),
        _hit(3, 10, 5, "Zweiter Treffer Seite zehn."),
    ]
    nachbarn = {(10, 2): [_hit(4, 10, 1, "Davor."), _hit(5, 10, 3, "Danach.")], (20, 0): [], (10, 5): []}
    ctx = retrieval.build_context("frage", lambda q: [0.0] * 3, lambda q, v, n: hits, lambda p, pos, span: nachbarn[(p, pos)])
    assert [s["page_id"] for s in ctx.sources] == [10, 20]
    assert ctx.sources[0]["fetched_at"] == "2026-10-03" and ctx.sources[0]["url"] == "https://x.test/10/"
    assert ctx.text.index("Davor.") < ctx.text.index("Treffer A") < ctx.text.index("Danach.") < ctx.text.index("Zweiter Treffer")
    assert '<document index="1">' in ctx.text and "Stand: 2026-10-03" in ctx.text
    assert ctx.chunk_ids == [4, 1, 5, 3, 2]


def test_budget_wird_gehalten_und_erster_treffer_bleibt():
    hits = [_hit(i, i, 0, "x" * 500) for i in range(1, 6)]
    ctx = retrieval.build_context("f", lambda q: [0.0], lambda q, v, n: hits, lambda p, pos, span: [], budget=1200)
    assert [s["page_id"] for s in ctx.sources] == [1, 2]
    winzig = retrieval.build_context("f", lambda q: [0.0], lambda q, v, n: hits, lambda p, pos, span: [], budget=10)
    assert [s["page_id"] for s in winzig.sources] == [1]


def test_dokument_zeigt_dateinamen_statt_url_und_einbettung_darf_scheitern():
    hits = [_hit(1, 7, 0, "Inhalt aus dem PDF.", kind="document", fname="ordnung.pdf")]

    def kaputt(q):
        raise RuntimeError("kein Anbieter")

    gesehen = {}

    def suche(q, v, n):
        gesehen["vektor"] = v
        return hits

    ctx = retrieval.build_context("f", kaputt, suche, lambda p, pos, span: [])
    assert gesehen["vektor"] is None
    assert ctx.sources[0]["url"] is None and ctx.sources[0]["filename"] == "ordnung.pdf"
    assert "ordnung.pdf" in ctx.text


def test_fragment_laesst_ueberschrift_weg_und_kuerzt_am_wort():
    assert retrieval.fragment_for("Beratung\nDie Sprechzeiten sind dienstags von 14 bis 16 Uhr im Raum 36.", "Beratung") == "Die Sprechzeiten sind dienstags von 14 bis 16 Uhr im Raum 36."
    lang = "Wort " * 40
    frag = retrieval.fragment_for(lang, None)
    assert len(frag) <= 80 and not frag.endswith(" ")
    assert retrieval.fragment_for("- kurz", None) is None
    # Markup and a line of stars never stand on the page, the next real line is taken.
    assert retrieval.fragment_for("Hochschule.*******************\n- **Verpflichtender Upload:** Gültiger Personalausweis.", None) == "Verpflichtender Upload: Gültiger Personalausweis."
    assert retrieval.fragment_for("Titel\n| a | b |\nEin ganz normaler Satz mit Inhalt.", "Titel") == "Ein ganz normaler Satz mit Inhalt."


def test_ortsseite_ohne_karte_hat_keinen_link():
    hits = [_hit(1, 3, 0, "Mensa, Mo bis Fr.", kind="place", url="place:Mensa_B_59")]
    ctx = retrieval.build_context("f", lambda q: [0.0], lambda q, v, n: hits, lambda p, pos, span: [])
    assert ctx.sources[0]["url"] is None


def test_leere_suche_ergibt_leeren_kontext():
    ctx = retrieval.build_context("f", lambda q: [0.0], lambda q, v, n: [], lambda p, pos, span: [])
    assert ctx.text == "" and ctx.sources == []
