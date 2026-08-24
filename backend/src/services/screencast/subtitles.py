"""Untertitel-Spur fuer den Screencast: je Folie erkennen, versetzen, zusammenfuegen."""

import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from loguru import logger

from src.services.subtitle_converter import segments_to_vtt, split_long_segments

# Kennung der Untertitel-Spur im MP4, ISO 639-2.
_SPRACHKENNUNG = {
    "DE": "deu", "EN": "eng", "FR": "fra", "ES": "spa",
    "IT": "ita", "TR": "tur", "AR": "ara", "RU": "rus",
}

# Gleichzeitige Anfragen an den Spracherkenner.
_PARALLEL = 4


def vtt_sprachkennung(target_lang: str) -> str:
    """Dreibuchstabige Kennung fuer die Spur, leer wenn die Sprache unbekannt ist."""
    return _SPRACHKENNUNG.get((target_lang or "").split("-")[0].upper(), "")


def transcribe_slides(audio_paths: list[Path | None], client) -> list[list[dict]]:
    """Je Folie die Segmente mit Zeitmarken holen, ein Fehler gibt eine leere Liste.

    Ueber verbose_json, weil myLab die Formate vtt und srt nicht annimmt.
    """
    def _eine(pfad: Path | None) -> list[dict]:
        if pfad is None or not pfad.exists() or pfad.stat().st_size == 0:
            return []
        try:
            segmente, _ = client.transcribe_verbose(str(pfad))
            return segmente or []
        except Exception as e:
            logger.warning("Untertitel fuer {} nicht erkannt: {}", pfad.name, e)
            return []

    with ThreadPoolExecutor(max_workers=_PARALLEL) as pool:
        return list(pool.map(_eine, audio_paths))


def build_subtitle_vtt(slide_segments: list[list[dict]], clip_durations: list[float]) -> str:
    """Segmente verschieben, zu kurzen Einblendungen zerlegen und als eine VTT ausgeben."""
    verschoben: list[dict] = []
    versatz = 0.0
    for i, segmente in enumerate(slide_segments):
        for seg in segmente or []:
            if not str(seg.get("text", "")).strip():
                continue
            verschoben.append({
                "start": seg["start"] + versatz,
                "end": seg["end"] + versatz,
                "text": str(seg["text"]).strip(),
            })
        versatz += clip_durations[i] if i < len(clip_durations) else 0.0
    if not verschoben:
        return ""
    return segments_to_vtt(split_long_segments(verschoben))


def _spracherkenner():
    """Standard-Route fuer Spracherkennung aus dem Admin."""
    from src.dependencies import resolve_whisper_client
    return resolve_whisper_client(None)


def _ton_aus_clip(clip: Path, ziel: Path) -> Path | None:
    """Die Tonspur des fertigen Clips herausziehen, ohne sie neu zu kodieren."""
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(clip), "-vn", "-c:a", "copy", str(ziel)]
    ergebnis = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if ergebnis.returncode != 0 or not ziel.exists():
        logger.warning("Ton aus {} nicht lesbar: {}", clip.name, ergebnis.stderr[-200:])
        return None
    return ziel


def create_subtitle_track(clip_paths: list[Path], tmp: Path, hat_sprache: list[bool] | None = None) -> Path | None:
    """Untertitel je Clip erkennen und als VTT ablegen, None wenn nichts zustande kommt.

    Der Ton kommt aus dem fertigen Clip, damit Geschwindigkeit und Folienpause
    schon drin sind und die Zeitmarken zur Zeitachse des Videos passen. Stumme
    Folien bleiben aussen vor, auf Stille erfindet der Erkenner sonst Text.
    """
    from src.services.screencast.video import get_video_duration

    try:
        client = _spracherkenner()
        toene = [
            _ton_aus_clip(c, tmp / f"stt_{i:03d}.m4a")
            if hat_sprache is None or (i < len(hat_sprache) and hat_sprache[i])
            else None
            for i, c in enumerate(clip_paths)
        ]
        slide_segmente = transcribe_slides(toene, client)
        dauern = [get_video_duration(p) for p in clip_paths]
        spur_text = build_subtitle_vtt(slide_segmente, dauern)
    except Exception as e:
        logger.warning("Untertitel konnten nicht erzeugt werden: {}", e)
        return None
    if not spur_text:
        logger.warning("Untertitel: der Spracherkenner hat nichts geliefert")
        return None
    spur = tmp / "untertitel.vtt"
    spur.write_text(spur_text, encoding="utf-8")
    return spur
