"""Where the material comes from and how it is cut to size."""

import pytest

from src.features.podcast import source_text


def _budget(monkeypatch, chars: int) -> None:
    import src.features.ai_assistant.tasks._context_budget as budget
    monkeypatch.setattr(budget, "tool_context_budget", lambda tool="": chars)


class TestStuecke:
    def test_macht_aus_langem_text_mehrere_stuecke(self):
        stuecke = source_text.to_pieces("wort " * 2000)
        assert len(stuecke) > 1
        assert all(s["content"] for s in stuecke)

    def test_kurzer_text_bleibt_ein_stueck(self):
        assert len(source_text.to_pieces("Hallo Welt")) == 1

    def test_leerer_text_gibt_nichts(self):
        assert source_text.to_pieces("   ") == []


class TestBudget:
    def test_kleine_quelle_kommt_vollstaendig_mit(self, monkeypatch):
        _budget(monkeypatch, 100_000)
        text = source_text.fit_to_budget([("a.pdf", source_text.to_pieces("Kurzer Inhalt"))])
        assert "Kurzer Inhalt" in text
        assert "# a.pdf" in text

    def test_nimmt_von_vorne_und_laesst_den_rest_liegen(self, monkeypatch):
        _budget(monkeypatch, 5_000)
        stuecke = [{"content": f"Abschnitt {i} " + "f" * 900} for i in range(100)]
        text = source_text.fit_to_budget([("lang.pdf", stuecke)])
        assert "Abschnitt 0 " in text, "Anfang fehlt"
        assert "Abschnitt 50 " not in text, "Mitte darf nicht drin sein"
        assert "Abschnitt 99 " not in text, "Ende darf nicht drin sein"
        assert len(text) <= 5_000

    def test_zweite_quelle_bekommt_nur_was_die_erste_uebrig_laesst(self, monkeypatch):
        _budget(monkeypatch, 5_000)
        erste = [{"content": "a" * 900} for _ in range(100)]
        zweite = [{"content": "Zweite Quelle " + "b" * 900}]
        text = source_text.fit_to_budget([("voll.pdf", erste), ("rest.pdf", zweite)])
        assert "# voll.pdf" in text
        assert "Zweite Quelle" not in text, "die erste hat das Budget aufgebraucht"

    def test_reihenfolge_entscheidet(self, monkeypatch):
        _budget(monkeypatch, 3_000)
        a = [{"content": "Alpha " + "a" * 900} for _ in range(10)]
        b = [{"content": "Beta " + "b" * 900} for _ in range(10)]
        zuerst_a = source_text.fit_to_budget([("a", list(a)), ("b", list(b))])
        zuerst_b = source_text.fit_to_budget([("b", list(b)), ("a", list(a))])
        assert "Alpha" in zuerst_a and "Beta" not in zuerst_a
        assert "Beta" in zuerst_b and "Alpha" not in zuerst_b

    def test_kleine_quellen_passen_alle(self, monkeypatch):
        _budget(monkeypatch, 100_000)
        quellen = [(f"q{i}.pdf", [{"content": f"Inhalt {i}"}]) for i in range(5)]
        text = source_text.fit_to_budget(quellen)
        for i in range(5):
            assert f"Inhalt {i}" in text

    def test_ohne_quellen_bleibt_es_leer(self, monkeypatch):
        _budget(monkeypatch, 10_000)
        assert source_text.fit_to_budget([]) == ""


class TestDateien:
    def test_kennt_die_formate_des_werkzeugs(self):
        assert ".pdf" in source_text.PODCAST_EXTENSIONS
        assert ".docx" in source_text.PODCAST_EXTENSIONS

    def test_liest_eine_textdatei(self, tmp_path):
        pfad = tmp_path / "a.txt"
        pfad.write_text("Hallo Welt", encoding="utf-8")
        assert source_text.extract_file(str(pfad), ".txt").strip() == "Hallo Welt"

    def test_gibt_bei_unbekannter_endung_nichts_zurueck(self, tmp_path):
        pfad = tmp_path / "a.xyz"
        pfad.write_text("egal", encoding="utf-8")
        assert source_text.extract_file(str(pfad), ".xyz") == ""


class TestModulZugriff:
    """Ein fremdes Modul darf nicht zum Podcast werden, nur weil man die uuid kennt."""

    def test_fragt_dieselbe_tuer_wie_der_assistent(self, monkeypatch):
        import src.features.ai_assistant.routes._workspace_access as zugang
        from fastapi import HTTPException

        gefragt = {}

        def _abgelehnt(uuid, user_id, locale="de"):
            gefragt["uuid"], gefragt["user"] = uuid, user_id
            raise HTTPException(status_code=403, detail="nein")

        monkeypatch.setattr(zugang, "_require_workspace_access", _abgelehnt)
        with pytest.raises(HTTPException) as fehler:
            source_text.from_module("fremdes-modul", ["s1"], 7)
        assert fehler.value.status_code == 403
        assert gefragt == {"uuid": "fremdes-modul", "user": 7}
