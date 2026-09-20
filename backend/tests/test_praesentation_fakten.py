"""Die Fakten-Seite der Praesentation: Raster, Anteil je Quelle, Leseaufruf, Vorrat."""

import pytest

from tests.facts_helpers import MemoryFactStore
from tests.podcast_helpers import Abgewiesen, FakeAsyncClient, fakten_antwort, quelle

from src.features.praesentation import fakten as fk
from src.features.praesentation import lesen as ls
from src.limits import (
    PRAESENTATION_FACTS_MAX_CHARS,
    PRAESENTATION_FACTS_MIN_CHARS,
    PRAESENTATION_READ_MAX_FACTS,
)
from src.services.facts import RateLimited


@pytest.fixture(autouse=True)
def _kein_budget_aus_der_datenbank(monkeypatch):
    monkeypatch.setattr(fk, "material_budget", lambda: 120_000)
    monkeypatch.setattr(ls, "PRAESENTATION_RETRY_DELAY_SECONDS", 0)
    ls._schema_mode_supported = True


async def _vorrat(client, quellen, speicher=None, sprache="de"):
    speicher = speicher if speicher is not None else MemoryFactStore()
    pool = await fk.build_pool(client, "m", sources=quellen, language=sprache, store=speicher)
    return pool, speicher


class TestRaster:
    """Das Raster sucht das, woraus eine Folie entstehen kann."""

    def test_deutsch_und_englisch_haben_gleich_viele_felder(self):
        assert len(ls.CATEGORIES_DE) == len(ls.CATEGORIES_EN)

    def test_deutsch_bekommt_das_deutsche_raster(self):
        assert ls.categories("de") == ls.CATEGORIES_DE
        assert "These" in ls.categories("de")

    def test_alles_andere_bekommt_das_englische(self):
        assert ls.categories("en") == ls.CATEGORIES_EN

    def test_zahlen_und_ablaeufe_stehen_im_raster(self):
        """Aus Zahlen entstehen Tabellen und Diagramme, aus Ablaeufen Schrittfolgen."""
        assert "Zahl" in ls.CATEGORIES_DE
        assert "Ablauf" in ls.CATEGORIES_DE

    def test_beleg_ist_keine_kategorie(self):
        """Jeder Fakt traegt seinen Beleg schon als eigenes Feld, eine Kategorie doppelte ihn."""
        assert not any("Beleg" in k for k in ls.CATEGORIES_DE)
        felder = ls.FACTS_SCHEMA["json_schema"]["schema"]["properties"]["facts"]["items"]
        assert "citation" in felder["properties"]

    def test_das_raster_steht_im_prompt(self):
        prompt = ls.system_prompt("de", ls.CATEGORIES_DE, 20)
        assert all(f"- {k}" in prompt for k in ls.CATEGORIES_DE)

    def test_der_prompt_nennt_die_ausgabesprache(self):
        assert "in German" in ls.system_prompt("de", ls.CATEGORIES_DE, 20)
        assert "in English" in ls.system_prompt("en", ls.CATEGORIES_EN, 20)

    def test_der_prompt_nennt_den_deckel(self):
        assert "at most 7 statements" in ls.system_prompt("de", ls.CATEGORIES_DE, 7)

    def test_der_prompt_verraet_nichts_ueber_folien_bauteile(self):
        """Gelesen wird die Quelle, nicht schon die Folie. Der Bauplan gehoert in den Folienaufruf."""
        prompt = ls.system_prompt("de", ls.CATEGORIES_DE, 20).casefold()
        assert "bullet" not in prompt and "layout" not in prompt


class TestAnteilJeQuelle:
    """Der Anteil haengt an der Zahl der Quellen, nie an ihrem Platz in der Liste."""

    def test_eine_quelle_bekommt_den_hoechstwert(self):
        assert fk.facts_per_source(1) == PRAESENTATION_FACTS_MAX_CHARS

    def test_mehr_quellen_lassen_jeder_einzelnen_weniger(self):
        assert fk.facts_per_source(12) > fk.facts_per_source(20) > fk.facts_per_source(30)

    def test_sehr_viele_quellen_gehen_nie_unter_den_mindestwert(self):
        assert fk.facts_per_source(1000) == PRAESENTATION_FACTS_MIN_CHARS

    def test_null_quellen_stuerzen_nicht(self):
        assert fk.facts_per_source(0) == PRAESENTATION_FACTS_MAX_CHARS

    def test_der_deckel_begrenzt_ein_grosses_budget(self, monkeypatch):
        monkeypatch.setattr(fk, "facts_per_source", lambda n: 90_000)
        assert fk.read_max_facts(1) == PRAESENTATION_READ_MAX_FACTS

    def test_wenige_zeichen_lassen_wenigstens_fuenf_fakten(self, monkeypatch):
        monkeypatch.setattr(fk, "facts_per_source", lambda n: 100)
        assert fk.read_max_facts(50) == 5


class TestLeseaufruf:
    """Ein Aufruf je Quelle, und was eine Absage daraus macht."""

    async def test_die_quelle_steht_im_aufruf(self):
        client = FakeAsyncClient({"1.pdf": [fakten_antwort("Der Regelkreis regelt.")]})
        gelesen = await ls.read_source(client, "m", source=quelle(1, "Text der Quelle."),
                                       language="de", grid=ls.CATEGORIES_DE,
                                       max_chars=9_000, max_facts=20)
        assert gelesen[0]["fact"] == "Der Regelkreis regelt."
        assert "Text der Quelle." in client.user_prompts()[0]

    async def test_eine_absage_wird_dem_dienst_gemeldet(self):
        """Das Tempo gehoert dem Dienst, hier wird nur weitergereicht."""
        client = FakeAsyncClient({"1.pdf": [Abgewiesen(429)]})
        with pytest.raises(RateLimited):
            await ls.read_source(client, "m", source=quelle(1), language="de",
                                 grid=ls.CATEGORIES_DE, max_chars=9_000, max_facts=20)

    async def test_eine_kaputte_quelle_gibt_nichts_zurueck(self):
        client = FakeAsyncClient({"1.pdf": [RuntimeError("kaputt")] * ls.PRAESENTATION_READ_MAX_ATTEMPTS})
        assert await ls.read_source(client, "m", source=quelle(1), language="de",
                                    grid=ls.CATEGORIES_DE, max_chars=9_000, max_facts=20) is None

    async def test_mehr_fakten_als_erlaubt_werden_abgeschnitten(self):
        client = FakeAsyncClient({"1.pdf": [fakten_antwort(*[f"Aussage {i}" for i in range(20)])]})
        gelesen = await ls.read_source(client, "m", source=quelle(1), language="de",
                                       grid=ls.CATEGORIES_DE, max_chars=1_500, max_facts=40)
        assert len(gelesen) == 5

    async def test_eine_zu_lange_quelle_wird_vorn_gelesen(self):
        lang = "A" * (ls.PRAESENTATION_READ_MAX_SOURCE_CHARS + 5_000)
        client = FakeAsyncClient({"1.pdf": [fakten_antwort("Kurz.")]})
        await ls.read_source(client, "m", source=quelle(1, lang), language="de",
                             grid=ls.CATEGORIES_DE, max_chars=9_000, max_facts=20)
        assert len(client.user_prompts()[0]) < ls.PRAESENTATION_READ_MAX_SOURCE_CHARS + 1_000


class TestVorrat:
    """Der Vorrat ist durchnummeriert, das ist es, worauf eine Gliederung zeigen kann."""

    async def test_jede_quelle_wird_gelesen_und_der_vorrat_ist_nummeriert(self):
        client = FakeAsyncClient({
            "1.pdf": [fakten_antwort("Aus der ersten.")],
            "2.pdf": [fakten_antwort("Aus der zweiten.", "Noch eine.")],
        })
        pool, _ = await _vorrat(client, [quelle(1), quelle(2)])
        assert [f.fact_id for f in pool] == [1, 2, 3]
        assert [f.source_name for f in pool] == ["1.pdf", "2.pdf", "2.pdf"]

    async def test_eine_ausgefallene_quelle_kostet_die_anderen_nicht(self):
        client = FakeAsyncClient({
            "1.pdf": [RuntimeError("kaputt")] * ls.PRAESENTATION_READ_MAX_ATTEMPTS,
            "2.pdf": [fakten_antwort("Aus der zweiten.")],
        })
        pool, _ = await _vorrat(client, [quelle(1), quelle(2)])
        assert [f.fact for f in pool] == ["Aus der zweiten."]

    async def test_ohne_einen_einzigen_fakt_bleibt_der_vorrat_leer(self):
        """Dann nimmt der Aufrufer den aelteren Weg, das entscheidet nicht dieser Baustein."""
        client = FakeAsyncClient({"1.pdf": [RuntimeError("kaputt")] * ls.PRAESENTATION_READ_MAX_ATTEMPTS})
        pool, _ = await _vorrat(client, [quelle(1)])
        assert pool == []

    async def test_eine_bereits_gelesene_quelle_wird_nicht_noch_einmal_gefragt(self):
        """Das traegt einen Lauf ueber eine abgebrochene Etappe."""
        speicher = MemoryFactStore({"doc_01": [
            {"category": "These", "fact": "Schon gelesen.", "citation": "Beleg", "reference": ""}]})
        client = FakeAsyncClient({"2.pdf": [fakten_antwort("Neu gelesen.")]})
        pool, _ = await _vorrat(client, [quelle(1), quelle(2)], speicher)
        assert [f.fact for f in pool] == ["Schon gelesen.", "Neu gelesen."]
        assert len(client.gesendet) == 1


class TestVorratSichern:
    """Der Vorrat ueberlebt den Auftrag als Liste, die Rohquellen tun das nicht."""

    def _pool(self):
        from src.services.facts import Fact
        return [Fact(fact_id=1, category="Zahl", fact="Es sind 40 Grad.", citation="Beleg",
                     source_id="doc_01", source_name="1.pdf", reference="Kapitel 3")]

    def test_hin_und_zurueck_bleibt_gleich(self):
        pool = self._pool()
        assert fk.pool_aus_liste(fk.pool_als_liste(pool)) == pool

    def test_beschaedigte_eintraege_fallen_weg_statt_zu_stuerzen(self):
        assert fk.pool_aus_liste([{"fact_id": 1}, "kaputt", None]) == []


class TestDerGrundDesUmbaus:
    """Der Punkt der ganzen Uebung: keine Quelle faellt mehr hinten herunter."""

    async def test_jede_quelle_kommt_in_den_vorrat_egal_wie_gross_die_vorherigen_sind(self):
        """fit_to_budget fuellte von vorn auf. Die hinteren Dateien sahen nie ein Modell."""
        quellen = [quelle(n, "X" * 200_000) for n in range(1, 11)]
        client = FakeAsyncClient({f"{n}.pdf": [fakten_antwort(f"Aus Quelle {n}.")]
                                  for n in range(1, 11)})
        pool, _ = await _vorrat(client, quellen)
        assert {f.source_name for f in pool} == {f"{n}.pdf" for n in range(1, 11)}

    async def test_der_anteil_je_quelle_haelt_den_vorrat_im_budget(self, monkeypatch):
        """Zehn Quellen teilen sich das Budget, keine nimmt es allein ein."""
        monkeypatch.setattr(fk, "material_budget", lambda: 60_000)
        quellen = [quelle(n) for n in range(1, 11)]
        lang = "Eine sehr ausfuehrliche Aussage. " * 10
        client = FakeAsyncClient({f"{n}.pdf": [fakten_antwort(*[lang] * 40)]
                                  for n in range(1, 11)})
        pool, _ = await _vorrat(client, quellen)
        from src.services.facts import pool as fc
        assert len(fc.pool_block(pool, 10_000_000)) <= 60_000
