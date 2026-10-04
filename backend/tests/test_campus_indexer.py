"""Der Indexer bettet nur ein, was sich geändert hat."""
from src.features.campus.services import indexer


class _Pages:
    def __init__(self, page):
        self.page = page
        self.indexed = []
        self.status = []

    def get_page(self, page_id):
        return self.page

    def set_page_indexed(self, page_id, content_hash, title, chunk_count):
        self.indexed.append((page_id, content_hash, title, chunk_count))

    def set_page_status(self, page_id, status, error_message=None):
        self.status.append((status, error_message))


class _Chunks:
    def __init__(self):
        self.replaced = []
        self.embedded = []

    def replace_chunks(self, page_id, pieces):
        self.replaced.append(pieces)
        return list(range(1, len(pieces) + 1))

    def set_embeddings(self, pairs):
        self.embedded.extend(pairs)


def _embed(texts):
    return [[0.1] * 3 for _ in texts]


def test_unveraenderte_seite_wird_nicht_neu_eingebettet(monkeypatch):
    md = "# Titel\n\nEin Absatz."
    seiten = _Pages({"id": 1, "content_hash": indexer.content_hash(md), "status": "ready"})
    monkeypatch.setattr(indexer, "page_repo", seiten)
    monkeypatch.setattr(indexer, "chunk_repo", _Chunks())
    aufrufe = []
    assert indexer.index_markdown(1, "Titel", md, lambda t: aufrufe.append(t) or _embed(t)) == 0
    assert aufrufe == [] and seiten.indexed == []


def test_geaenderte_seite_bekommt_neue_chunks_und_einbettungen(monkeypatch):
    md = "# Titel\n\nEin Absatz mit Inhalt."
    seiten = _Pages({"id": 1, "content_hash": "alt", "status": "ready"})
    stuecke = _Chunks()
    monkeypatch.setattr(indexer, "page_repo", seiten)
    monkeypatch.setattr(indexer, "chunk_repo", stuecke)
    n = indexer.index_markdown(1, "Titel", md, _embed)
    assert n == 1
    assert stuecke.replaced[0][0]["content"].startswith("Titel\n")
    assert [cid for cid, _ in stuecke.embedded] == [1]
    assert seiten.indexed[0][1] == indexer.content_hash(md) and seiten.indexed[0][3] == 1


def test_seite_ohne_text_wird_als_fehler_markiert(monkeypatch):
    seiten = _Pages({"id": 1, "content_hash": None, "status": "pending"})
    monkeypatch.setattr(indexer, "page_repo", seiten)
    monkeypatch.setattr(indexer, "chunk_repo", _Chunks())
    assert indexer.index_markdown(1, None, "   ", _embed) == 0
    assert seiten.status == [("failed", "no text")]


def test_ueberlange_seite_bringt_hoechstens_max_chunks(monkeypatch):
    md = "# Titel\n\n" + "\n\n".join(f"## Abschnitt {i}\n\n" + "Ein Satz mit genug Woertern fuer einen eigenen Abschnitt im Index. " * 3 for i in range(10))
    seiten = _Pages({"id": 1, "content_hash": "alt", "status": "ready"})
    stuecke = _Chunks()
    monkeypatch.setattr(indexer, "page_repo", seiten)
    monkeypatch.setattr(indexer, "chunk_repo", stuecke)
    assert indexer.index_markdown(1, "Titel", md, _embed, max_chunks=3) == 3
    assert len(stuecke.replaced[0]) == 3 and seiten.indexed[0][3] == 3
