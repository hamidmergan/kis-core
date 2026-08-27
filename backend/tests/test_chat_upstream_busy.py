"""The chat says when the provider was the problem, via the same list as the jobs."""
import pytest

from src.services.upstream_errors import is_upstream_busy, upstream_error_code


@pytest.mark.parametrize("meldung", [
    "Error code: 502 - Bad Gateway",
    "Error code: 429 - Too Many Requests",
    "TTS API error (500): Internal Server Error",
    "Request timed out.",
    "Service Unavailable",
])
def test_anbieterprobleme_bekommen_den_schluessel(meldung):
    assert upstream_error_code(RuntimeError(meldung)) == "upstream_busy"


@pytest.mark.parametrize("meldung", [
    "Kein Embedding-Anbieter aktiv. Bitte im Admin-Bereich setzen.",
    "list index out of range",
    "Error code: 401 - Unauthorized",
])
def test_alles_andere_bekommt_keinen_schluessel(meldung):
    """Without this bound every bug would be a 'try again later'."""
    assert upstream_error_code(RuntimeError(meldung)) is None


def test_die_auftraege_benutzen_dieselbe_pruefung():
    """One list for both paths, otherwise they drift apart."""
    from src.tasks._errors import is_upstream_busy as auftrag_pruefung

    assert auftrag_pruefung is is_upstream_busy
