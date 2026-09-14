"""Der versteckte Vorrat: verdraengen, Doppel erkennen, Grenze halten."""

import pytest
from fastapi import HTTPException

from src.features.podcast import source_store
from src.limits import PODCAST_STORE_MAX_SOURCES


class FakeDb:
    """Genug Datenbank fuer den Vorrat, ohne Datenbank."""

    def __init__(self, store=None, sources=None):
        self.store = store
        self.sources = list(sources or [])
        self.created = []
        self.deleted = []
        self.touched = []
        self.store_calls = 0

    def get_podcast_store_workspace(self, user_id):
        return self.store

    def create_podcast_store_workspace(self, user_id, title):
        self.store_calls += 1
        self.store = {"id": 42, "uuid": "store-uuid", "user_id": user_id, "title": title}
        return self.store

    def get_aia_source_by_content_hash(self, workspace_id, digest):
        for s in self.sources:
            if s["workspace_id"] == workspace_id and s.get("content_hash") == digest:
                return s
        return None

    def get_aia_sources_by_last_used(self, workspace_id):
        rows = [s for s in self.sources if s["workspace_id"] == workspace_id]
        return sorted(rows, key=lambda s: (s["last_used_at"], s["id"]))

    def delete_aia_source(self, uuid):
        self.deleted.append(uuid)
        self.sources = [s for s in self.sources if s["uuid"] != uuid]

    def create_aia_source(self, **kwargs):
        self.created.append(kwargs)
        self.sources.append({
            "id": 1000 + len(self.sources),
            "workspace_id": kwargs["workspace_id"],
            "uuid": kwargs["uuid"],
            "filename": kwargs["filename"],
            "file_path": kwargs["file_path"],
            "content_hash": kwargs["content_hash"],
            "last_used_at": 999,
        })
        return self.sources[-1]["id"]

    def touch_aia_sources_used(self, uuids):
        self.touched.extend(uuids)


def _quelle(i, last_used, workspace_id=42):
    return {
        "id": i,
        "workspace_id": workspace_id,
        "uuid": f"s{i}",
        "filename": f"{i}.pdf",
        "file_path": f"p/{i}.pdf",
        "content_hash": f"h{i}",
        "last_used_at": last_used,
    }


def _verdrahte(monkeypatch, fake):
    """Kein Speicher, kein Celery, keine Datenbank."""
    monkeypatch.setattr(source_store, "db", fake)
    monkeypatch.setattr(source_store, "_remove_files", lambda pfad: None)
    monkeypatch.setattr(source_store, "_index", lambda u, uid, loc: None)
    monkeypatch.setattr(
        source_store, "_save_file",
        lambda user_id, ws, su, ext, pfad: f"gespeichert/{su}{ext}",
    )


class TestInhaltsHash:
    def test_gleicher_inhalt_gleicher_hash(self, tmp_path):
        a, b = tmp_path / "a.txt", tmp_path / "anders.txt"
        a.write_text("Hallo Welt", encoding="utf-8")
        b.write_text("Hallo Welt", encoding="utf-8")
        assert source_store.content_hash(str(a)) == source_store.content_hash(str(b))

    def test_anderer_inhalt_anderer_hash(self, tmp_path):
        a, b = tmp_path / "a.txt", tmp_path / "b.txt"
        a.write_text("Hallo", encoding="utf-8")
        b.write_text("Tschuess", encoding="utf-8")
        assert source_store.content_hash(str(a)) != source_store.content_hash(str(b))


class TestModulHolen:
    def test_legt_den_vorrat_beim_ersten_mal_an(self, monkeypatch):
        fake = FakeDb(store=None)
        _verdrahte(monkeypatch, fake)
        store = source_store.store_for_user(7)
        assert fake.store_calls == 1
        assert store["title"] == source_store.STORE_TITLE

    def test_legt_ihn_kein_zweites_mal_an(self, monkeypatch):
        fake = FakeDb(store={"id": 42, "uuid": "store-uuid", "user_id": 7})
        _verdrahte(monkeypatch, fake)
        source_store.store_for_user(7)
        assert fake.store_calls == 0

    def test_nachschauen_legt_nie_einen_an(self, monkeypatch):
        """start.py fragt nur nach, sonst entstuende der Vorrat auch ohne eine Datei."""
        fake = FakeDb(store=None)
        _verdrahte(monkeypatch, fake)
        assert source_store.store_of(7) is None
        assert fake.store_calls == 0


class TestVerdraengen:
    def test_unter_der_grenze_geht_nichts_weg(self, monkeypatch):
        fake = FakeDb(sources=[_quelle(i, i) for i in range(5)])
        _verdrahte(monkeypatch, fake)
        assert source_store.make_room(42) == 0
        assert fake.deleted == []

    def test_bei_voller_grenze_geht_genau_eine_weg(self, monkeypatch):
        fake = FakeDb(sources=[_quelle(i, i) for i in range(PODCAST_STORE_MAX_SOURCES)])
        _verdrahte(monkeypatch, fake)
        assert source_store.make_room(42) == 1
        assert len(fake.sources) == PODCAST_STORE_MAX_SOURCES - 1

    def test_die_am_laengsten_ungenutzte_geht_nicht_die_aelteste(self, monkeypatch):
        quellen = [_quelle(i, last_used=100 - i) for i in range(PODCAST_STORE_MAX_SOURCES)]
        # s0 ist die aelteste Zeile, wurde aber zuletzt benutzt. s19 liegt am laengsten brach.
        fake = FakeDb(sources=quellen)
        _verdrahte(monkeypatch, fake)
        source_store.make_room(42)
        assert fake.deleted == [f"s{PODCAST_STORE_MAX_SOURCES - 1}"]

    def test_ueber_der_grenze_raeumt_es_bis_wieder_platz_ist(self, monkeypatch):
        fake = FakeDb(sources=[_quelle(i, i) for i in range(PODCAST_STORE_MAX_SOURCES + 4)])
        _verdrahte(monkeypatch, fake)
        assert source_store.make_room(42) == 5
        assert len(fake.sources) == PODCAST_STORE_MAX_SOURCES - 1

    def test_ein_fehlendes_file_haelt_die_zeile_nicht_am_leben(self, monkeypatch):
        fake = FakeDb(sources=[_quelle(i, i) for i in range(PODCAST_STORE_MAX_SOURCES)])
        _verdrahte(monkeypatch, fake)

        def _kaputt(pfad):
            raise OSError("weg")

        monkeypatch.setattr(source_store, "_remove_files", _kaputt)
        assert source_store.make_room(42) == 1
        assert fake.deleted == ["s0"]


class TestUnsichtbar:
    """Der Vorrat ist kein Modul, keine Modul-Route darf ihn oeffnen."""

    def _tuer(self, monkeypatch, workspace):
        import src.features.ai_assistant.routes._workspace_access as zugang
        monkeypatch.setattr(zugang.db, "get_aia_workspace", lambda uuid: workspace)
        return zugang

    def test_vorrat_antwortet_wie_ein_fehlendes_modul(self, monkeypatch):
        store = {"id": 42, "uuid": "store-uuid", "user_id": 7, "is_podcast_store": True}
        zugang = self._tuer(monkeypatch, store)
        for tuer in (zugang._require_workspace_access,
                     zugang._require_workspace_manage,
                     zugang._require_workspace_owner):
            with pytest.raises(HTTPException) as fehler:
                tuer("store-uuid", 7)
            assert fehler.value.status_code == 404, tuer.__name__

    def test_ein_echtes_modul_geht_weiter_auf(self, monkeypatch):
        modul = {"id": 1, "uuid": "m", "user_id": 7, "is_podcast_store": False}
        zugang = self._tuer(monkeypatch, modul)
        assert zugang._require_workspace_access("m", 7)["id"] == 1


class TestEinlagern:
    def test_legt_eine_neue_datei_an_und_startet_das_indexieren(self, monkeypatch, tmp_path):
        fake = FakeDb(store={"id": 42, "uuid": "store-uuid", "user_id": 7})
        _verdrahte(monkeypatch, fake)
        indexiert = []
        monkeypatch.setattr(source_store, "_index", lambda u, uid, loc: indexiert.append(u))

        pfad = tmp_path / "vortrag.pdf"
        pfad.write_bytes(b"inhalt")
        uuid = source_store.put(7, "vortrag.pdf", str(pfad), ".pdf")

        assert len(fake.created) == 1
        assert fake.created[0]["filename"] == "vortrag.pdf"
        assert fake.created[0]["file_type"] == "pdf"
        assert fake.created[0]["content_hash"]
        assert indexiert == [uuid]

    def test_dieselbe_datei_zweimal_legt_keine_zweite_zeile_an(self, monkeypatch, tmp_path):
        fake = FakeDb(store={"id": 42, "uuid": "store-uuid", "user_id": 7})
        _verdrahte(monkeypatch, fake)
        pfad = tmp_path / "vortrag.pdf"
        pfad.write_bytes(b"inhalt")

        erste = source_store.put(7, "vortrag.pdf", str(pfad), ".pdf")
        zweite = source_store.put(7, "anders benannt.pdf", str(pfad), ".pdf")

        assert erste == zweite
        assert len(fake.created) == 1
        assert fake.touched == [erste]

    def test_bekanntes_doppel_wird_nicht_neu_indexiert(self, monkeypatch, tmp_path):
        fake = FakeDb(store={"id": 42, "uuid": "store-uuid", "user_id": 7})
        _verdrahte(monkeypatch, fake)
        indexiert = []
        monkeypatch.setattr(source_store, "_index", lambda u, uid, loc: indexiert.append(u))
        pfad = tmp_path / "vortrag.pdf"
        pfad.write_bytes(b"inhalt")

        source_store.put(7, "vortrag.pdf", str(pfad), ".pdf")
        source_store.put(7, "vortrag.pdf", str(pfad), ".pdf")

        assert len(indexiert) == 1
