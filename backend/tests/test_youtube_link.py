"""A YouTube link yields one video id, the title comes from oEmbed, nothing else is fetched."""
import httpx
import pytest

from src.services.web_page_fetch import LinkError
from src.services.youtube_link import (
    canonical_url, fallback_title, fetch_title, is_youtube_url, parse_youtube_url,
)

ID = "dQw4w9WgXcQ"
KANONISCH = f"https://www.youtube.com/watch?v={ID}"


@pytest.mark.parametrize("link", [
    f"https://www.youtube.com/watch?v={ID}",
    f"https://youtube.com/watch?v={ID}&t=42s",
    f"https://m.youtube.com/watch?feature=share&v={ID}",
    f"https://music.youtube.com/watch?v={ID}",
    f"https://youtu.be/{ID}",
    f"https://youtu.be/{ID}?si=abc",
    f"https://www.youtube.com/shorts/{ID}",
    f"https://www.youtube.com/live/{ID}?feature=share",
    f"https://www.youtube.com/embed/{ID}",
    f"https://www.youtube-nocookie.com/embed/{ID}",
    f"https://www.youtube.com/watch?v={ID}&list=PLabc&index=3",
    f"  https://www.youtube.com/watch?v={ID}  ",
    f"youtu.be/{ID}",
    f"www.youtube.com/watch?v={ID}",
    f"youtu.be/{ID}?redirect=http://evil.com",
])
def test_bekannte_formen_liefern_die_id_und_den_kanonischen_link(link):
    video = parse_youtube_url(link)
    assert video.video_id == ID
    assert video.canonical_url == KANONISCH


@pytest.mark.parametrize("link", [
    "",
    "https://vimeo.com/12345",
    "https://www.youtube.com/",
    "https://www.youtube.com/watch",
    "https://www.youtube.com/watch?v=kurz",
    "https://www.youtube.com/playlist?list=PLabc",
    "https://www.youtube.com/@kanal",
    "https://www.youtube.com/channel/UCabc",
    "https://youtube.com.evil.example/watch?v=" + ID,
    "javascript:alert(1)",
    "https://user:pw@www.youtube.com/watch?v=" + ID,
    "https://www.you\ttube.com/watch?v=" + ID,
    "ftp://www.youtube.com/watch?v=" + ID,
    "https://www.youtube.com/watch?v=" + "x" * 12,
    "https://[bad/watch?v=" + ID,
])
def test_alles_andere_ist_ungueltig(link):
    with pytest.raises(LinkError) as exc:
        parse_youtube_url(link)
    assert exc.value.key == "ai.youtube.invalid"
    assert exc.value.status == 400
    assert is_youtube_url(link) is False


def test_is_youtube_url_und_kanonischer_link():
    assert is_youtube_url(f"https://youtu.be/{ID}") is True
    assert canonical_url(ID) == KANONISCH
    assert fallback_title(ID) == f"YouTube {ID}"


def _antwort(status, body=None):
    def handler(request):
        assert request.url.host == "www.youtube.com"
        assert request.url.path == "/oembed"
        assert request.url.params["url"] == KANONISCH
        assert request.url.params["format"] == "json"
        return httpx.Response(status, json=body) if body is not None else httpx.Response(status)
    return httpx.MockTransport(handler)


def test_titel_kommt_aus_oembed():
    assert fetch_title(ID, transport=_antwort(200, {"title": "  Photosynthese erklärt  "})) == "Photosynthese erklärt"


@pytest.mark.parametrize("status, key", [
    (401, "ai.youtube.notEmbeddable"),
    (403, "ai.youtube.notEmbeddable"),
    (404, "ai.youtube.notFound"),
    (400, "ai.youtube.notFound"),
])
def test_gesperrte_oder_fehlende_videos_werden_abgewiesen(status, key):
    with pytest.raises(LinkError) as exc:
        fetch_title(ID, transport=_antwort(status))
    assert exc.value.key == key
    assert exc.value.status == 400


def test_leerer_titel_und_serverfehler_geben_den_ersatztitel():
    assert fetch_title(ID, transport=_antwort(200, {"title": ""})) == f"YouTube {ID}"
    assert fetch_title(ID, transport=_antwort(200, {})) == f"YouTube {ID}"
    assert fetch_title(ID, transport=_antwort(500)) == f"YouTube {ID}"


def test_netzfehler_gibt_den_ersatztitel():
    def handler(request):
        raise httpx.ConnectTimeout("langsam", request=request)
    assert fetch_title(ID, transport=httpx.MockTransport(handler)) == f"YouTube {ID}"
