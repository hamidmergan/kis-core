"""Putting the voiced contributions together into one file to listen to."""

import tempfile
from pathlib import Path

from loguru import logger

from src.services.ai_hinweis import ffmpeg_metadata_args
from src.services.screencast.process import run_proc
from src.services.screencast.video import get_audio_duration


def _stille(pfad: Path, sekunden: float, job_uuid: str | None) -> None:
    run_proc(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-t", f"{sekunden:.2f}", "-ac", "2", "-ar", "44100",
         "-c:a", "libmp3lame", "-q:a", "4", str(pfad)],
        timeout=60, job_uuid=job_uuid,
    )


def kleben(stuecke: list[bytes], pause: float, job_uuid: str | None = None) -> tuple[bytes, float]:
    """One MP3 out of many, with a breath between the contributions.

    Re-encoded on purpose: the pieces come from different voices and may carry
    different bitrates, and only a fresh encode gives a correct running time.
    """
    brauchbar = [s for s in stuecke if s]
    if not brauchbar:
        raise RuntimeError("Kein vertonter Beitrag vorhanden")

    with tempfile.TemporaryDirectory(prefix="podcast_") as tmpdir:
        ordner = Path(tmpdir)
        liste = ordner / "teile.txt"
        pausendatei = ordner / "pause.mp3"
        if pause > 0:
            _stille(pausendatei, pause, job_uuid)

        zeilen: list[str] = []
        for i, stueck in enumerate(brauchbar):
            teil = ordner / f"teil_{i:03d}.mp3"
            teil.write_bytes(stueck)
            zeilen.append(f"file '{teil}'")
            if pause > 0 and i < len(brauchbar) - 1:
                zeilen.append(f"file '{pausendatei}'")
        liste.write_text("\n".join(zeilen) + "\n")

        ziel = ordner / "podcast.mp3"
        ergebnis = run_proc(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(liste),
             "-ac", "2", "-ar", "44100", "-c:a", "libmp3lame", "-q:a", "4",
             *ffmpeg_metadata_args(), str(ziel)],
            timeout=900, job_uuid=job_uuid,
        )
        if ergebnis.returncode != 0 or not ziel.exists():
            logger.error("Podcast-Montage fehlgeschlagen (rc={}): {}",
                         ergebnis.returncode, ergebnis.stderr[-400:])
            raise RuntimeError(f"Montage fehlgeschlagen: {ergebnis.stderr[-200:]}")
        return ziel.read_bytes(), get_audio_duration(ziel)
