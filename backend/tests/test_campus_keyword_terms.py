"""Keyword search takes rare words of the question, without word lists."""
from src.features.campus.repository.chunks import pick_rare, query_words


def test_woerter_der_frage():
    assert query_words("Wie viel Pfand kostet die Schlüsselkarte? Die Karte!") == ["wie", "viel", "pfand", "kostet", "die", "schlüsselkarte", "karte"]
    assert query_words("a ? !") == []


def test_haeufige_und_fehlende_woerter_fallen_weg():
    counts = {"die": 9000, "wie": 3000, "pfand": 4, "schlüsselkarte": 1, "testhaus": 0, "kostet": 120}
    assert pick_rare(counts, total=30000) == ["schlüsselkarte", "pfand", "kostet"]


def test_hoechstens_sechs():
    counts = {f"w{i}": i + 1 for i in range(10)}
    assert len(pick_rare(counts, total=100000)) == 6
