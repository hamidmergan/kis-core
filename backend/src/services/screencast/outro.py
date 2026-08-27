"""The AI notice as a slide at the beginning and at the end."""

from pathlib import Path

from PIL import Image

ASSETS_DIR = Path(__file__).parent / "assets"
OUTRO_SOURCE = ASSETS_DIR / "screencast-outro.png"


def create_outro_image(width: int, height: int, output_path: Path) -> None:
    """Puts the notice slide at exactly this size, with a white border."""
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
    """Puts the notice clip before and after the slides, counting it as silent."""
    if hinweis is None:
        return list(clips), list(hat_sprache)
    return [hinweis, *clips, hinweis], [False, *hat_sprache, False]
