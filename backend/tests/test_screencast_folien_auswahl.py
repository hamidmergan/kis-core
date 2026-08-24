"""Die Auswahl darf die Foliennummern nie verschieben."""

from src.services.screencast.auswahl import folien_auswahl


def test_ohne_angabe_sind_alle_folien_dabei():
    a = folien_auswahl(4, None, None)
    assert a.clip_folien == [0, 1, 2, 3]
    assert a.ausgeschlossen == set()
    assert a.alter_ton_erlaubt == {0, 1, 2, 3}


def test_der_rest_ist_ausgeschlossen():
    a = folien_auswahl(4, [0, 3], [])
    assert a.clip_folien == [0, 3]
    assert a.ausgeschlossen == {1, 2}


def test_clip_folien_sind_aufsteigend():
    assert folien_auswahl(4, [3, 0, 2], []).clip_folien == [0, 2, 3]


def test_neu_vertonte_folien_duerfen_den_alten_ton_nicht_nehmen():
    a = folien_auswahl(4, None, [1])
    assert a.alter_ton_erlaubt == {0, 2, 3}


def test_neu_vertonen_ausserhalb_der_auswahl_aendert_nichts():
    a = folien_auswahl(4, [0, 1], [3])
    assert a.alter_ton_erlaubt == {0, 1}
    assert a.ausgeschlossen == {2, 3}


def test_nummern_ausserhalb_des_bereichs_fallen_weg():
    a = folien_auswahl(3, [0, 7, -1], [9])
    assert a.clip_folien == [0]
    assert a.ausgeschlossen == {1, 2}


def test_doppelte_nummern_zaehlen_einmal():
    assert folien_auswahl(3, [1, 1, 1], []).clip_folien == [1]


def test_leere_auswahl_ergibt_keine_clips():
    a = folien_auswahl(3, [], [])
    assert a.clip_folien == []
    assert a.ausgeschlossen == {0, 1, 2}


def test_keine_folien():
    a = folien_auswahl(0, None, None)
    assert a.clip_folien == []
    assert a.ausgeschlossen == set()


def test_die_bauposition_traegt_die_richtige_foliennummer():
    """Bei ausgeschlossener Folie 2 muss Clip 1 zu Folie 3 gehoeren, nicht zu Folie 2."""
    from src.services.screencast.auswahl import clip_paare
    assert clip_paare([0, 2, 3], 4) == [(0, 0), (1, 2), (2, 3)]


def test_mehr_folien_als_bilder_werden_abgeschnitten():
    from src.services.screencast.auswahl import clip_paare
    assert clip_paare([0, 1, 2, 3], 2) == [(0, 0), (1, 1)]


def test_ausgeschlossene_folien_bekommen_keinen_platz_fuer_neuen_ton():
    """False heisst, der alte Ton dieser Folie bleibt liegen."""
    from src.services.screencast.auswahl import ton_plaetze
    assert ton_plaetze(4, [0, 2, 3]) == [True, False, True, True]


def test_ohne_auswahl_bekommt_keine_folie_neuen_ton():
    from src.services.screencast.auswahl import ton_plaetze
    assert ton_plaetze(3, []) == [False, False, False]
