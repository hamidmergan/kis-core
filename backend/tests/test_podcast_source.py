"""Where the material comes from and how it is cut to size."""

import pytest

from src.features.podcast import source_text


class TestKuerzen:
    def test_laesst_kurzes_material_unberuehrt(self):
        assert source_text.shorten("kurz", 100) == "kurz"

    def test_schneidet_an_einem_absatz(self):
        text = "Erster Absatz.\n\n" + "x" * 50 + "\n\nZweiter Absatz."
        gekuerzt = source_text.shorten(text, 60)
        assert gekuerzt.endswith("x") and "Zweiter" not in gekuerzt

    def test_schneidet_hart_wenn_kein_absatz_passt(self):
        assert len(source_text.shorten("y" * 200, 50)) == 50


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
