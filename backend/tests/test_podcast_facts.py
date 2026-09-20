"""Die Fakten-Seite des Podcasts: Anteil je Quelle, Leseaufruf, Vorrat als Material."""

import pytest

from tests.facts_helpers import MemoryFactStore
from tests.podcast_helpers import Abgewiesen, FakeAsyncClient, fakten_antwort, quelle

from src.features.podcast import facts as fk
from src.features.podcast import reading as rd
from src.limits import (
    PODCAST_FACTS_MAX_CHARS,
    PODCAST_FACTS_MIN_CHARS,
    PODCAST_READ_MAX_FACTS,
)
from src.services.facts import RateLimited


@pytest.fixture(autouse=True)
def _kein_budget_aus_der_datenbank(monkeypatch):
    monkeypatch.setattr(fk, "material_budget", lambda: 120_000)
    monkeypatch.setattr(rd, "PODCAST_RETRY_DELAY_SECONDS", 0)
    rd._schema_mode_supported = True


async def _vorrat(client, quellen, speicher=None, sprache="de"):
    speicher = speicher if speicher is not None else MemoryFactStore()
    text = await fk.build_pool_text(client, "m", sources=quellen, language=sprache,
                                    store=speicher)
    return text, speicher


class TestAnteilJeQuelle:
    """Der Anteil haengt an der Zahl der Quellen, nie an ihrem Platz in der Liste."""

    def test_eine_quelle_bekommt_den_hoechstwert(self):
        assert fk.facts_per_source(1) == PODCAST_FACTS_MAX_CHARS

    def test_zehn_quellen_teilen_sich_das_budget(self):
        assert fk.facts_per_source(10) == 12_000

    def test_der_anteil_haengt_nur_an_der_zahl_der_quellen(self):
        """Weniger Quellen, mehr Platz je Quelle. Der Platz in der Liste spielt keine Rolle."""
        # Zwischen Mindest- und Hoechstwert teilt sich das Budget wirklich auf.
        assert fk.facts_per_source(12) > fk.facts_per_source(20) > fk.facts_per_source(30)

    def test_sehr_viele_quellen_gehen_nie_unter_den_mindestwert(self):
        assert fk.facts_per_source(1000) == PODCAST_FACTS_MIN_CHARS

    def test_null_quellen_stuerzen_nicht(self):
        assert fk.facts_per_source(0) == PODCAST_FACTS_MAX_CHARS

    def test_der_deckel_begrenzt_ein_grosses_budget(self, monkeypatch):
        monkeypatch.setattr(fk, "facts_per_source", lambda n: 90_000)
        assert fk.read_max_facts(1) == PODCAST_READ_MAX_FACTS

    def test_wenige_zeichen_lassen_wenigstens_fuenf_fakten(self, monkeypatch):
        monkeypatch.setattr(fk, "facts_per_source", lambda n: 100)
        assert fk.read_max_facts(50) == 5


class TestRaster:
    def test_deutsch_bekommt_das_deutsche_raster(self):
        assert rd.categories("de") == rd.CATEGORIES_DE
        assert "Streitpunkt" in rd.categories("de")

    def test_alles_andere_bekommt_das_englische(self):
        assert rd.categories("en") == rd.CATEGORIES_EN

    def test_das_raster_steht_im_prompt(self):
        prompt = rd.system_prompt("de", rd.CATEGORIES_DE, 20)
        assert all(f"- {k}" in prompt for k in rd.CATEGORIES_DE)

    def test_der_prompt_nennt_die_ausgabesprache(self):
        assert "in German" in rd.system_prompt("de", rd.CATEGORIES_DE, 20)
        assert "in English" in rd.system_prompt("en", rd.CATEGORIES_EN, 20)

    def test_der_prompt_nennt_den_deckel(self):
        assert "at most 7 statements" in rd.system_prompt("de", rd.CATEGORIES_DE, 7)

    def test_kein_bauplan_mehr_im_prompt(self):
        """Der Bauplan gehoert dem Dossier, eine Folge hat keinen."""
        assert "BUILD PLAN" not in rd.system_prompt("de", rd.CATEGORIES_DE, 20)


class TestLeseaufruf:
    async def test_eine_quelle_wird_zu_fakten(self):
        client = FakeAsyncClient({"1.pdf": [fakten_antwort("A", "B")]})
        fakten = await rd.read_source(client, "m", source=quelle(1), language="de",
                                      grid=rd.CATEGORIES_DE, max_chars=9000, max_facts=20)
        assert [f["fact"] for f in fakten] == ["A", "B"]

    async def test_der_dateiname_steht_im_aufruf(self):
        client = FakeAsyncClient({"1.pdf": [fakten_antwort("A")]})
        await rd.read_source(client, "m", source=quelle(1), language="de",
                             grid=rd.CATEGORIES_DE, max_chars=9000, max_facts=20)
        assert "(1.pdf)" in client.user_prompts()[0]

    async def test_eine_absage_wird_zur_bremse_des_dienstes(self):
        """Der Leser staffelt nicht selbst, das macht der Dienst."""
        client = FakeAsyncClient({"1.pdf": [Abgewiesen(429)]})
        with pytest.raises(RateLimited):
            await rd.read_source(client, "m", source=quelle(1), language="de",
                                 grid=rd.CATEGORIES_DE, max_chars=9000, max_facts=20)

    async def test_ein_anderer_fehler_wird_im_leser_wiederholt(self):
        from src.limits import PODCAST_READ_MAX_ATTEMPTS

        client = FakeAsyncClient({"1.pdf": [RuntimeError("weg")] * PODCAST_READ_MAX_ATTEMPTS})
        assert await rd.read_source(client, "m", source=quelle(1), language="de",
                                    grid=rd.CATEGORIES_DE, max_chars=9000,
                                    max_facts=20) is None
        assert len(client.gesendet) == PODCAST_READ_MAX_ATTEMPTS

    async def test_der_verbrauch_wird_gebucht(self):
        gebucht = []
        client = FakeAsyncClient({"1.pdf": [fakten_antwort("A")]})
        await rd.read_source(client, "m", source=quelle(1), language="de",
                             grid=rd.CATEGORIES_DE, max_chars=9000, max_facts=20,
                             book=gebucht.append)
        assert gebucht and gebucht[0].usage.completion_tokens == 20


class TestVorratAlsMaterial:
    async def test_jede_quelle_kommt_im_vorrat_vor(self):
        """Der ganze Zweck: zehn Quellen, zehn Aufrufe, zehn Quellen im Material."""
        quellen = [quelle(i) for i in range(1, 11)]
        client = FakeAsyncClient({f"{i}.pdf": [fakten_antwort(f"Fakt {i}")] for i in range(1, 11)})
        text, speicher = await _vorrat(client, quellen)
        assert len(speicher.extractions) == 10
        assert all(f"[{i}.pdf]" in text for i in range(1, 11))

    async def test_die_fakten_sind_numeriert(self):
        client = FakeAsyncClient({"1.pdf": [fakten_antwort("A")], "2.pdf": [fakten_antwort("B")]})
        text, _ = await _vorrat(client, [quelle(1), quelle(2)])
        assert "#1 (Kernaussage) [1.pdf] A" in text and "#2 (Kernaussage) [2.pdf] B" in text

    async def test_die_belege_bleiben_draussen(self):
        """Der Beleg verankert den Leseaufruf, im Skriptaufruf kostet er nur Platz."""
        client = FakeAsyncClient({"1.pdf": [fakten_antwort("A")]})
        text, _ = await _vorrat(client, [quelle(1)])
        assert "Beleg A" not in text

    async def test_eine_ausgefallene_quelle_verhindert_die_folge_nicht(self):
        from src.limits import PODCAST_READ_MAX_ATTEMPTS

        client = FakeAsyncClient({"1.pdf": [RuntimeError("weg")] * PODCAST_READ_MAX_ATTEMPTS,
                                  "2.pdf": [fakten_antwort("B")]})
        text, speicher = await _vorrat(client, [quelle(1), quelle(2)])
        assert list(speicher.extractions) == ["doc_02"] and "[2.pdf]" in text

    async def test_ohne_einen_einzigen_fakt_bleibt_das_material_leer(self):
        """Leer heisst fuer den Aufrufer: nimm einen der aelteren Wege."""
        from src.limits import PODCAST_READ_MAX_ATTEMPTS

        client = FakeAsyncClient({"1.pdf": [RuntimeError("weg")] * PODCAST_READ_MAX_ATTEMPTS})
        text, _ = await _vorrat(client, [quelle(1)])
        assert text == ""

    async def test_wiederholungen_ueber_quellen_hinweg_fallen_weg(self):
        gleich = "Die Frist betraegt zehn Jahre und gilt fuer alle Aufzeichnungen."
        client = FakeAsyncClient({"1.pdf": [fakten_antwort(gleich)],
                                  "2.pdf": [fakten_antwort(gleich)]})
        text, _ = await _vorrat(client, [quelle(1), quelle(2)])
        assert text.count(gleich) == 1

    async def test_das_material_bleibt_im_budget(self, monkeypatch):
        monkeypatch.setattr(fk, "material_budget", lambda: 200)
        client = FakeAsyncClient({"1.pdf": [fakten_antwort("A" * 500)]})
        text, _ = await _vorrat(client, [quelle(1)])
        assert len(text) == 200

    async def test_eine_zweite_etappe_liest_nur_die_uebrigen(self):
        speicher = MemoryFactStore({"doc_01": [{"category": "Kernaussage", "fact": "alt",
                                                "citation": "b", "reference": ""}]})
        client = FakeAsyncClient({"2.pdf": [fakten_antwort("B")]})
        text, _ = await _vorrat(client, [quelle(1), quelle(2)], speicher)
        assert len(client.gesendet) == 1 and "alt" in text and "B" in text

    async def test_drei_aufrufe_sind_zugleich_unterwegs(self):
        quellen = [quelle(i) for i in range(1, 8)]
        client = FakeAsyncClient({f"{i}.pdf": [fakten_antwort("A")] for i in range(1, 8)},
                                 dauer=0.01)
        await _vorrat(client, quellen)
        assert client.hoechststand == 3


class TestQuellenDeckel:
    """Was ein einzelner Leseaufruf hoechstens bekommt."""

    def test_eine_normale_quelle_geht_ungekuerzt_hinein(self):
        text = rd.user_prompt(quelle(1, "Kurzer Text."))
        assert text.endswith("Kurzer Text.")

    def test_eine_riesige_quelle_wird_am_deckel_geschnitten(self):
        from src.limits import PODCAST_READ_MAX_SOURCE_CHARS

        riesig = quelle(1, "y" * (PODCAST_READ_MAX_SOURCE_CHARS + 50_000))
        kopf = rd.user_prompt(quelle(1, ""))
        assert len(rd.user_prompt(riesig)) == len(kopf) + PODCAST_READ_MAX_SOURCE_CHARS
