"""The build plans live in code, the prompt table may override their text."""

from src.features.summary import templates as tp


def test_es_gibt_fuenf_vorlagen_mit_eindeutigen_kuerzeln():
    kuerzel = [t.slug for t in tp.TEMPLATES]
    assert len(kuerzel) == 5
    assert len(set(kuerzel)) == 5
    assert tp.default_template().slug == "fliesstext"


def test_eine_vorlage_wird_ueber_ihr_kuerzel_gefunden():
    assert tp.get_template("zeitstrahl").name_de == "Zeitstrahl"
    assert tp.get_template("gibt_es_nicht") is None


def test_nur_der_fliesstext_verzichtet_auf_ueberschriften():
    ohne = [t.slug for t in tp.TEMPLATES if not t.headings]
    assert ohne == ["fliesstext"]


def test_die_prompt_tabelle_kann_den_text_ersetzen(monkeypatch):
    monkeypatch.setattr(tp, "load_prompt", lambda key, default: f"aus der Tabelle für {key}")
    assert tp.template_body(tp.get_template("kurzbriefing")) == \
        "aus der Tabelle für summary_template_kurzbriefing"


def test_ohne_eintrag_gilt_der_text_aus_dem_code(monkeypatch):
    monkeypatch.setattr(tp, "load_prompt", lambda key, default: default)
    assert "briefing" in tp.template_body(tp.get_template("kurzbriefing")).lower()


def test_keine_vorlage_schreibt_eine_feste_deutsche_ueberschrift_vor():
    feste_titel = ("Fragen zur Selbstkontrolle", "Antworten", "Ohne Datum")
    for t in tp.TEMPLATES:
        for titel in feste_titel:
            assert titel not in t.body, f"{t.slug} schreibt '{titel}' fest vor"


def test_das_kurzbriefing_verlangt_zahlen_fristen_und_zustaendige():
    body = tp.get_template("kurzbriefing").body
    assert "Every figure, deadline and responsibility the material states appears" in body
    assert "always with what they refer to" not in body
