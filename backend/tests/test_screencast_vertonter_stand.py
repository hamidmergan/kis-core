"""After a run a snapshot exists that step 6 compares against later."""

import json
from unittest.mock import patch

from src.tasks.screencast_tasks._render import _merke_vertonten_stand

UUID = "d" * 32


def _dateien(vorhanden: dict):
    def hole(user_id, job_uuid, name):
        if name not in vorhanden:
            raise FileNotFoundError(name)
        return vorhanden[name]
    return hole


def _gespeichert(aufrufe):
    return json.loads(aufrufe[0][0][3].decode())


def test_der_abzug_haelt_skripte_und_folientexte():
    folientexte = json.dumps(["Folie eins", "Folie zwei"]).encode()
    with patch("src.tasks.screencast_tasks._render.get_job_file",
               side_effect=_dateien({"scripts.txt": folientexte})), \
         patch("src.tasks.screencast_tasks._render.load_result_meta",
               return_value={"target_lang": "ES"}), \
         patch("src.tasks.screencast_tasks._render.save_job_file") as sichern:
        _merke_vertonten_stand(
            1, UUID, ["Skript eins", "Skript zwei"], "de-anna", 2,
            0.9, 1.0, False, [0, 1],
        )
    stand = _gespeichert(sichern.call_args_list)
    assert stand["scripts"] == ["Skript eins", "Skript zwei"]
    assert stand["folientexte"] == ["Folie eins", "Folie zwei"]
    assert stand["voice_id"] == "de-anna"
    assert stand["provider_id"] == 2
    assert stand["target_lang"] == "ES"


def test_der_abzug_traegt_tempo_pause_untertitel_und_auswahl():
    with patch("src.tasks.screencast_tasks._render.get_job_file", side_effect=_dateien({})), \
         patch("src.tasks.screencast_tasks._render.load_result_meta", return_value=None), \
         patch("src.tasks.screencast_tasks._render.save_job_file") as sichern:
        _merke_vertonten_stand(
            1, UUID, ["Skript eins", "Skript zwei", "Skript drei"], "de-anna", 2,
            1.1, 2.5, True, [2, 0],
        )
    stand = _gespeichert(sichern.call_args_list)
    assert stand["speed"] == 1.1
    assert stand["slide_pause"] == 2.5
    assert stand["subtitles"] is True
    assert stand["video_folien"] == [0, 2]


def test_ohne_folienauswahl_steht_die_volle_liste():
    with patch("src.tasks.screencast_tasks._render.get_job_file", side_effect=_dateien({})), \
         patch("src.tasks.screencast_tasks._render.load_result_meta", return_value=None), \
         patch("src.tasks.screencast_tasks._render.save_job_file") as sichern:
        _merke_vertonten_stand(
            1, UUID, ["Skript eins", "Skript zwei", "Skript drei"], "de-anna", 2,
            0.9, 1.0, False, None,
        )
    stand = _gespeichert(sichern.call_args_list)
    assert stand["video_folien"] == [0, 1, 2]


def test_ohne_folientexte_bleibt_die_liste_leer():
    """An old job without scripts.txt must not fail the run."""
    with patch("src.tasks.screencast_tasks._render.get_job_file", side_effect=_dateien({})), \
         patch("src.tasks.screencast_tasks._render.load_result_meta", return_value=None), \
         patch("src.tasks.screencast_tasks._render.save_job_file") as sichern:
        _merke_vertonten_stand(1, UUID, ["Skript"], "de-anna", 2, 0.9, 1.0, False, None)
    stand = _gespeichert(sichern.call_args_list)
    assert stand["folientexte"] == []
    assert stand["target_lang"] == ""


def test_der_dateiname_stimmt():
    with patch("src.tasks.screencast_tasks._render.get_job_file", side_effect=_dateien({})), \
         patch("src.tasks.screencast_tasks._render.load_result_meta", return_value=None), \
         patch("src.tasks.screencast_tasks._render.save_job_file") as sichern:
        _merke_vertonten_stand(1, UUID, [], "", 0, 0.9, 1.0, False, None)
    assert sichern.call_args_list[0][0][2] == "vertonter_stand.json"


def test_der_wiederholen_knopf_nimmt_die_auswahl_mit():
    from src.routes.jobs._retry import _queue_params_from_render
    params = _queue_params_from_render({
        "voice_id": "de-anna", "speed": 0.9, "slide_pause": 1.0, "dpi": 96,
        "provider_id": 2, "video_folien": [0, 2], "neu_vertonen": [2],
    })
    assert params["video_folien"] == [0, 2]
    assert params["neu_vertonen"] == [2]


def test_ein_alter_auftrag_ohne_auswahl_bleibt_gueltig():
    from src.routes.jobs._retry import _queue_params_from_render
    params = _queue_params_from_render({
        "voice_id": "de-anna", "speed": 0.9, "slide_pause": 1.0, "dpi": 96,
    })
    assert params["video_folien"] is None
    assert params["neu_vertonen"] == []
