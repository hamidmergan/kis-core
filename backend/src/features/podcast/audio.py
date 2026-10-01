"""Putting the voiced contributions together into one file to listen to."""

import tempfile
import wave
from pathlib import Path

from loguru import logger

from src.limits import PODCAST_PAUSES
from src.services.ai_hinweis import ffmpeg_metadata_args
from src.services.screencast.process import run_proc
from src.services.screencast.video import get_audio_duration

# The voice leaves silence around every piece, only a short breath of it stays.
_RAENDER = ("silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.03,areverse,"
            "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.08,areverse")
_WAV = ["-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le"]
# A piece shorter than this is a quick reaction, one longer than the other an explanation.
_REAKTION_S = 2.5
_ERKLAERUNG_S = 15.0


def pause_vor(vorher_s: float, nachher_s: float) -> float:
    """The gap between two pieces, a reaction comes quickly, a long explanation sinks in."""
    schnell, normal, lang = PODCAST_PAUSES
    if nachher_s < _REAKTION_S:
        return schnell
    if vorher_s > _ERKLAERUNG_S:
        return lang
    return normal


def _dauer(pfad: Path) -> float:
    with wave.open(str(pfad)) as w:
        return w.getnframes() / w.getframerate()


def _als_wav(roh: Path, ziel: Path, job_uuid: str | None) -> float:
    """One piece as WAV without its silent edges, a piece that is all silence stays whole."""
    for filter_ in (["-af", _RAENDER], []):
        ergebnis = run_proc(["ffmpeg", "-y", "-i", str(roh), *filter_, *_WAV, str(ziel)],
                            timeout=60, job_uuid=job_uuid)
        try:
            sekunden = _dauer(ziel) if ergebnis.returncode == 0 else 0.0
        except (wave.Error, OSError, EOFError):
            sekunden = 0.0
        if sekunden > 0.05:
            return sekunden
    raise RuntimeError(f"Beitrag nicht lesbar: {ergebnis.stderr[-200:]}")


def _stille(pfad: Path, sekunden: float, job_uuid: str | None) -> None:
    run_proc(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-t", f"{sekunden:.2f}", *_WAV, str(pfad)],
        timeout=60, job_uuid=job_uuid,
    )


def kleben(stuecke: list[bytes], job_uuid: str | None = None) -> tuple[bytes, float]:
    """One MP3 out of many, with a gap between the contributions that fits the moment.

    Re-encoded on purpose: the pieces come from different voices and may carry
    different bitrates, and only a fresh encode gives a correct running time.
    """
    brauchbar = [s for s in stuecke if s]
    if not brauchbar:
        raise RuntimeError("Kein vertonter Beitrag vorhanden")

    with tempfile.TemporaryDirectory(prefix="podcast_") as tmpdir:
        ordner = Path(tmpdir)
        teile: list[tuple[Path, float]] = []
        for i, stueck in enumerate(brauchbar):
            roh = ordner / f"roh_{i:03d}.mp3"
            roh.write_bytes(stueck)
            wav = ordner / f"teil_{i:03d}.wav"
            teile.append((wav, _als_wav(roh, wav, job_uuid)))

        pausen: dict[float, Path] = {}
        zeilen: list[str] = []
        for i, (wav, sekunden) in enumerate(teile):
            if i:
                pause = pause_vor(teile[i - 1][1], sekunden)
                if pause not in pausen:
                    pausen[pause] = ordner / f"pause_{len(pausen)}.wav"
                    _stille(pausen[pause], pause, job_uuid)
                zeilen.append(f"file '{pausen[pause]}'")
            zeilen.append(f"file '{wav}'")
        liste = ordner / "teile.txt"
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
