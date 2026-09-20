"""The preview follows the same path as the screencast, a single slide becomes a one-slide file."""

from pathlib import Path

from src.features.praesentation import vorschau
from src.features.praesentation.schemas import Slide
from src.features.praesentation.vorlage import Analyse


def _fake_render(monkeypatch, gesehen):
    def pptx_to_images(pptx_path: Path, output_dir: Path, dpi: int = 100):
        gesehen.append((pptx_path.read_bytes(), dpi))
        output_dir.mkdir(parents=True, exist_ok=True)
        pfade = []
        for i in range(2):
            p = output_dir / f"slide-{i + 1}.png"
            p.write_bytes(f"png{i}".encode())
            pfade.append(p)
        return pfade

    monkeypatch.setattr(vorschau, "pptx_to_images", pptx_to_images)


def test_render_liefert_die_bilder_in_reihenfolge(monkeypatch):
    gesehen = []
    _fake_render(monkeypatch, gesehen)
    assert vorschau.render(b"deck", dpi=50) == [b"png0", b"png1"]
    assert gesehen == [(b"deck", 50)]


def test_einzeln_baut_eine_folie_und_nimmt_das_erste_bild(monkeypatch):
    gesehen = []
    _fake_render(monkeypatch, gesehen)
    monkeypatch.setattr(vorschau.bau, "baue", lambda *a, **k: b"eine-folie")
    a = Analyse(breite=1, hoehe=1, typeface="Arial")
    assert vorschau.einzeln(b"vorlage", a, Slide(id="s2", role="text", title="T"), {}, "Deck", False) == b"png0"
    assert gesehen[0][0] == b"eine-folie"
