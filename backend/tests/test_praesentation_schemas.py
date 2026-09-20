"""The shapes the presentation tool passes between route, task and job folder."""

from src.features.praesentation.schemas import (
    FOLIEN_GRENZEN, Body, ImageSpec, Outline, OutlineRow, PraesentationParams, Slide,
    WAEHLBARE_ROLLEN, bildstellen,
)


def test_params_haben_sichere_vorgaben():
    """Default parameters are secure and sensible."""
    p = PraesentationParams()
    assert (p.language, p.notes, p.template_id) == ("de", False, "thl")


def test_grenzen_und_rollen():
    """Slide count and role constants are as specified."""
    assert FOLIEN_GRENZEN == (3, 30)
    assert "deckblatt" not in WAEHLBARE_ROLLEN and "abschluss" not in WAEHLBARE_ROLLEN


def test_folie_rundreise_als_json():
    """Slide round-trips through JSON."""
    s = Slide(id="s3", role="text", title="T", body=Body(kind="bullets", items=["a", "b"]), layout=2)
    assert Slide.model_validate_json(s.model_dump_json()) == s


def test_gliederung_traegt_titel_und_zeilen():
    """Outline carries title and rows."""
    o = Outline(title="Deck", rows=[OutlineRow(id="s1", role="deckblatt", title="Deck")])
    assert o.rows[0].gist == ""


def test_bildstellen_zaehlt_die_bildfelder_vor_dem_koerper():
    """The order the dialog shows: the image fields first, a body picture last."""
    s = Slide(id="s1", images=[ImageSpec(prompt="eins"), ImageSpec(prompt="zwei")],
              body=Body(kind="image", prompt="drei"))
    assert [z.prompt for z in bildstellen(s)] == ["eins", "zwei", "drei"]
    assert bildstellen(Slide(id="s2", body=Body(kind="bullets", items=["a"]))) == []


def test_notizen_werden_ohne_zutun_uebernommen():
    """Whoever asked for notes in step one gets them in the file until they say otherwise."""
    from src.features.praesentation.schemas import PraesentationParams
    p = PraesentationParams(notes=True)
    assert p.notes_include is True and p.notes_in_deck is True
    assert PraesentationParams(notes=True, notes_include=False).notes_in_deck is False
    # Nobody asked for notes, so there is nothing to carry over either way.
    assert PraesentationParams(notes=False).notes_in_deck is False
