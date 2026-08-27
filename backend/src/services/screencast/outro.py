"""KI-Hinweis für Screencasts: gleiche Folie am Anfang und am Ende (Transparenzpflicht).

Lädt ein statisches Bild aus ``assets/screencast-outro.png`` und passt es
passend zur Slide-Auflösung (weisses Padding) an, damit ffmpeg-Concat per
``-c copy`` funktioniert. Zum Anpassen einfach das PNG austauschen.
"""

from pathlib import Path

from PIL import Image

ASSETS_DIR = Path(__file__).parent / "assets"
OUTRO_SOURCE = ASSETS_DIR / "screencast-outro.png"


def create_outro_image(width: int, height: int, output_path: Path) -> None:
    """Render outro slide at exactly (width, height) by fitting OUTRO_SOURCE
    onto a white canvas. Aspect ratio is preserved; remaining space stays white.

    Raises FileNotFoundError if assets/outro.png is missing.
    """
    if not OUTRO_SOURCE.exists():
        raise FileNotFoundError(f"Outro source missing: {OUTRO_SOURCE}. Drop a PNG there to enable the outro.")

    canvas = Image.new("RGB", (width, height), "white")
    src = Image.open(OUTRO_SOURCE).convert("RGBA")

    scale = min(width / src.width, height / src.height)
    new_w, new_h = max(1, int(src.width * scale)), max(1, int(src.height * scale))
    resized = src.resize((new_w, new_h), Image.LANCZOS)

    offset = ((width - new_w) // 2, (height - new_h) // 2)
    canvas.paste(resized, offset, resized)
    canvas.save(output_path, "PNG")


def get_image_dimensions(image_path: Path) -> tuple[int, int]:
    """Return (width, height) of the given image."""
    with Image.open(image_path) as img:
        return img.size


KI_HINWEIS = "Dieses Video wurde mithilfe von KI erstellt. This video was created with AI assistance."


def rahme_clips(
    clips: list[Path], hat_sprache: list[bool], hinweis: Path | None
) -> tuple[list[Path], list[bool]]:
    """Setzt den Hinweis-Clip vor und hinter die Folien, er gilt dabei als stumm."""
    if hinweis is None:
        return list(clips), list(hat_sprache)
    return [hinweis, *clips, hinweis], [False, *hat_sprache, False]
