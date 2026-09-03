"""The demo module's chapters: which file lands where, and that a second run changes nothing."""
from unittest.mock import patch

import pytest

from scripts import demo_kapitel_anlegen as skript


@pytest.mark.parametrize("datei, kapitel", [
    ("DEMO_Vorlesung_01_Grundlagen.mp4", "Einheit 1: Grundlagen"),
    ("DEMO_Folien_01_Grundlagen.pdf", "Einheit 1: Grundlagen"),
    ("DEMO_Skript_Kapitel_1_Grundlagen.pdf", "Einheit 1: Grundlagen"),
    ("DEMO_Folien_06_Team_und_Methoden.pdf", "Einheit 6: Team und Methoden"),
    ("DEMO_Podcast_Aus_dem_Projektalltag.mp3", "Begleitmaterial"),
    ("DEMO_Modulhandbuch_Projektmanagement.pdf", "Begleitmaterial"),
    ("Eigene_Datei.pdf", None),
])
def test_jede_demo_datei_kennt_ihr_kapitel(datei, kapitel):
    assert skript.kapitel_fuer(datei) == kapitel


def test_die_kapitel_stehen_in_der_reihenfolge_der_liste():
    namen = skript.kapitelnamen()
    assert len(namen) == 7
    assert namen[0] == "Einheit 1: Grundlagen"
    assert namen[-1] == "Begleitmaterial"


def test_ein_zweiter_lauf_legt_nichts_neues_an():
    vorhanden = [{"id": i, "uuid": f"k{i}", "name": n} for i, n in enumerate(skript.kapitelnamen())]
    quellen = [
        {"uuid": "q1", "filename": "DEMO_Folien_06_Team_und_Methoden.pdf", "chapter_id": 5},
        {"uuid": "q2", "filename": "DEMO_Semesterplan_WS_2026_27.pdf", "chapter_id": None},
        {"uuid": "q3", "filename": "Eigene_Datei.pdf", "chapter_id": None},
    ]
    with patch.object(skript.db, "get_aia_workspace", return_value={"id": 1}), \
         patch.object(skript.db, "get_aia_chapters_by_workspace", return_value=vorhanden), \
         patch.object(skript.db, "create_aia_chapter") as anlegen, \
         patch.object(skript.db, "get_aia_sources_by_workspace", return_value=quellen), \
         patch.object(skript.db, "set_aia_source_chapter") as zuordnen:
        zaehler = skript.kapitel_anlegen("egal")
    anlegen.assert_not_called()
    # Only the file that sat outside its chapter moves, foreign files stay put.
    zuordnen.assert_called_once_with("q2", 6)
    assert zaehler["Einheit 6: Team und Methoden"] == 1
    assert zaehler["Begleitmaterial"] == 1


def test_fehlende_kapitel_entstehen_in_listenreihenfolge():
    angelegt: list[str] = []

    def anlegen(workspace_id, uuid, name):
        angelegt.append(name)
        return {"id": len(angelegt), "uuid": uuid, "name": name}

    with patch.object(skript.db, "get_aia_workspace", return_value={"id": 1}), \
         patch.object(skript.db, "get_aia_chapters_by_workspace", return_value=[]), \
         patch.object(skript.db, "create_aia_chapter", side_effect=anlegen), \
         patch.object(skript.db, "get_aia_sources_by_workspace", return_value=[]), \
         patch.object(skript.db, "set_aia_source_chapter"):
        skript.kapitel_anlegen("egal")
    assert angelegt == skript.kapitelnamen()


def test_ein_unbekanntes_modul_bricht_ab():
    with patch.object(skript.db, "get_aia_workspace", return_value=None):
        with pytest.raises(SystemExit):
            skript.kapitel_anlegen("gibt-es-nicht")
