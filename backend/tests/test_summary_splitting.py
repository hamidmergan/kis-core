"""Cutting long files: where the cut lands and what the parts are called."""

from src.features.summary import splitting as sp


def _paragraf(nummer, laenge):
    return f"§ {nummer} Vorschrift\n" + ("Wort " * (laenge // 5))


class TestSchwelle:
    def test_ein_kurzes_dokument_bleibt_ein_stueck(self):
        text = "A" * 1000
        assert sp.split_text(text, maximum=500, threshold=5000) == [text]

    def test_ein_zeichen_darueber_wird_geteilt(self):
        assert len(sp.split_text("A" * 5001, maximum=5000, threshold=5000)) == 2


class TestSchnitt:
    def test_geschnitten_wird_vor_dem_paragrafenzeichen(self):
        text = "\n".join(_paragraf(n, 2000) for n in range(1, 11))
        teile = sp.split_text(text, maximum=9000, threshold=9000)
        assert len(teile) > 1
        assert all(t.startswith("§ ") for t in teile[1:])
        assert "".join(teile) == text

    def test_ohne_paragrafen_an_der_ueberschrift(self):
        text = "\n".join(f"## Kapitel {n}\n" + ("Wort " * 400) for n in range(1, 11))
        teile = sp.split_text(text, maximum=9000, threshold=9000)
        assert all(t.startswith("## Kapitel ") for t in teile[1:])

    def test_ohne_ueberschriften_am_leeren_absatz(self):
        text = "\n\n".join("Wort " * 400 for _ in range(10))
        teile = sp.split_text(text, maximum=9000, threshold=9000)
        assert all(t.startswith("Wort") for t in teile[1:])

    def test_ohne_absaetze_am_satzende(self):
        text = " ".join(f"Das ist Satz Nummer {n}." for n in range(400))
        teile = sp.split_text(text, maximum=3000, threshold=3000)
        assert all(t.startswith("Das ist Satz") for t in teile[1:])
        assert "".join(teile) == text

    def test_ein_block_ohne_grenze_wird_hart_geschnitten(self):
        teile = sp.split_text("A" * 1000, maximum=300, threshold=300)
        assert "".join(teile) == "A" * 1000
        assert all(len(t) <= 300 for t in teile)


class TestGroesse:
    def test_die_teile_sind_ausgeglichen_statt_randvoll(self):
        text = "\n".join(_paragraf(n, 1000) for n in range(1, 418))
        teile = sp.split_text(text, maximum=150_000, threshold=150_000)
        assert len(teile) == 3
        assert min(map(len, teile)) > 0.7 * max(map(len, teile))

    def test_kein_teil_ueber_dem_maximum(self):
        text = "\n".join(_paragraf(n, 3000) for n in range(1, 40))
        assert all(len(t) <= 20000 for t in sp.split_text(text, maximum=20000, threshold=20000))


class TestEinheiten:
    def test_ein_kurzes_dokument_behaelt_seine_kennung(self):
        e = sp.split_sources([{"source_id": "q1", "filename": "a.pdf", "content": "A" * 100}],
                             maximum=5000, threshold=5000)
        assert e[0]["source_id"] == "q1" and e[0]["parts"] == 1 and e[0]["label"] == "a.pdf"

    def test_ein_langes_dokument_wird_zu_durchnummerierten_teilen(self):
        text = "\n".join(_paragraf(n, 1000) for n in range(1, 418))
        e = sp.split_sources([{"source_id": "q1", "filename": "AMG74.pdf", "content": text}],
                             maximum=150_000, threshold=150_000)
        assert [x["source_id"] for x in e] == ["q1t1", "q1t2", "q1t3"]
        assert e[1]["label"] == "AMG74.pdf (Teil 2 von 3)"
        assert {x["filename"] for x in e} == {"AMG74.pdf"}
        assert {x["origin"] for x in e} == {"q1"}


class TestHinweisUndNamen:
    def test_der_hinweis_nennt_die_kennungen_je_datei(self):
        e = [{"source_id": "q1t1", "filename": "AMG.pdf", "parts": 2},
             {"source_id": "q1t2", "filename": "AMG.pdf", "parts": 2},
             {"source_id": "q2", "filename": "b.pdf", "parts": 1}]
        assert sp.part_note(e) == "- AMG.pdf: q1t1, q1t2"
        assert sp.part_note(e, keep={"q1t1"}) == "- AMG.pdf: q1t1"
        assert sp.part_note(e[2:]) == ""

    def test_geteilte_teile_zaehlen_als_eine_datei(self):
        e = [{"source_id": "q1t1", "filename": "AMG.pdf", "origin": "q1"},
             {"source_id": "q1t2", "filename": "AMG.pdf", "origin": "q1"},
             {"source_id": "q2", "filename": "AMG.pdf", "origin": "q2"}]
        assert sp.original_names(e) == ["AMG.pdf", "AMG.pdf"]


class TestTeilgroesse:
    def test_ein_gemessenes_fenster_bestimmt_die_teilgroesse(self, monkeypatch):
        from src.limits import SUMMARY_PART_MIN_CHARS
        monkeypatch.setattr(sp, "cap_for_model", lambda budget, share, feature: 45_000)
        assert sp.part_size_for_chat() == max(SUMMARY_PART_MIN_CHARS, 45_000)

    def test_ohne_messung_gilt_der_rueckfall(self, monkeypatch):
        from src.limits import SUMMARY_PART_FALLBACK_CHARS
        monkeypatch.setattr(sp, "cap_for_model", lambda budget, share, feature: budget)
        assert sp.part_size_for_chat() == SUMMARY_PART_FALLBACK_CHARS

    def test_ein_winziges_fenster_faellt_nie_unter_das_minimum(self, monkeypatch):
        from src.limits import SUMMARY_PART_MIN_CHARS
        monkeypatch.setattr(sp, "cap_for_model", lambda budget, share, feature: 1_000)
        assert sp.part_size_for_chat() == SUMMARY_PART_MIN_CHARS


class TestQuerverweise:
    def test_ein_querverweis_am_zeilenanfang_ist_keine_schnittstelle(self):
        verweise = ("§ 21 zugelassen", "§ 25 Absatz 2", "Artikel 34 der Richtlinie")
        fueller = "Weiterer Text ohne besondere Bedeutung für den Schnitt. " * 2
        block = (fueller + "Arzneimittel, die nach\n§ 21 zugelassen oder nach § 21a genehmigt sind, "
                 "dürfen abgegeben werden. "
                 + fueller + "Die Behörde entscheidet gemäß\n§ 25 Absatz 2 über den Antrag. "
                 + fueller + "Das Verfahren richtet sich nach\nArtikel 34 der Richtlinie 2001/83/EG. ")
        text = "§ 1 Vorschrift\n" + block * 30
        teile = sp.split_text(text, maximum=3000, threshold=3000)
        assert len(teile) > 1
        assert not any(t.startswith(v) for t in teile[1:] for v in verweise)
        assert "".join(teile) == text


class TestVerlustfrei:
    def test_die_teile_ergeben_zusammen_immer_den_ausgangstext(self):
        faelle = [
            "Wort " * 20 + "\n" * 10,
            " " * 100,
            "A" * 50 + "\n" * 100 + "B" * 50,
            "\n".join(_paragraf(n, 700) for n in range(1, 30)),
        ]
        for text in faelle:
            for maximum in (30, 105, 400):
                assert "".join(sp.split_text(text, maximum=maximum)) == text
