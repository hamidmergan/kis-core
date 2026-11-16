"""The language sample is taken from the body of a document, not from its edges."""

from src.services.text_language import language_sample


COVER = (
    "Technische Hochschule Luebeck\n"
    "Fachbereich Elektrotechnik und Informatik\n"
    "Vorlesungsskript zum Modul Verteilte Systeme\n"
    "Sommersemester 2026\n"
)
BODY = (
    "A distributed system is a collection of independent computers that appears "
    "to its users as a single coherent system. The machines communicate only by "
    "passing messages over a network. There is no shared memory and no global "
    "clock. Concurrency is the first challenge, because multiple components "
    "execute at the same time and may access the same resources. Partial failure "
    "is the second challenge, because one node may fail while the others keep "
    "running. Consistency is the third challenge, because replicas can diverge "
    "when data is spread over several nodes. Replication improves availability "
    "and read throughput, consensus protocols let a group of nodes agree on a "
    "single value, and sharding splits a large dataset across many nodes. "
) * 3
FOOTER = "\nSeite 1 von 12\nTechnische Hochschule Luebeck, Moenkhofer Weg 239\n"
MIXED_DOC = COVER + BODY + FOOTER


# -- language sampling --------------------------------------------------------


def test_language_sample_skips_cover_page_and_footer():
    """The probe must not see the edges, that is where the boilerplate lives."""
    sample = language_sample(MIXED_DOC)

    assert "Vorlesungsskript" not in sample
    assert "Moenkhofer Weg" not in sample
    assert "distributed system" in sample


def test_language_sample_returns_short_text_unchanged():
    short = "A very short document about nothing in particular."
    assert language_sample(short) == short
