"""Async generation: scripts (LLM batch), TTS parallel synthesis, image conversion."""

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from loguru import logger

from src.limits import SCREENCAST_TTS_PARALLELISM
from src.services.openai_compat_llm import OpenAICompatLLMClient
from src.services.openai_compat_tts import _split_text
from src.services.screencast.pptx import pptx_to_images
from src.storage import get_job_file, save_job_file


def resolve_tts_parallelism() -> int:
    """How many text pieces are voiced at once."""
    return SCREENCAST_TTS_PARALLELISM


async def generate_all_scripts(
    slide_texts: list[str],
    llm_client: OpenAICompatLLMClient,
    glossary: dict | None = None,
    add_greeting: bool = True,
    add_closing: bool = True,
    min_chars: int = 1500,
    max_chars: int = 2000,
    source_lang: str = "DE",
    target_lang: str = "EN-US",
) -> list[str]:
    try:
        scripts = await asyncio.to_thread(
            llm_client.generate_scripts_batch, slide_texts, glossary, add_greeting, add_closing,
            min_chars=min_chars, max_chars=max_chars, source_lang=source_lang, target_lang=target_lang,
        )
        logger.info("Batch script generation completed for {} slides", len(slide_texts))
        return scripts
    except RuntimeError as e:
        logger.error("Batch script generation failed: {}", e)
        raise HTTPException(
            status_code=502,
            detail=f"Skript-Generierung fehlgeschlagen: {e}",
        )


def _lies_ton(user_id: int, job_uuid: str, name: str) -> bytes | None:
    """Empty files count as missing, they are not a valid MP3."""
    try:
        daten = get_job_file(user_id, job_uuid, name)
    except Exception:
        return None
    return daten or None


async def generate_all_tts(
    slide_scripts: list[str],
    tts_client: Any,
    tmp: Path,
    speed: float,
    voice_id: str = "",
    on_slide_done: Callable[[int, int, int], None] | None = None,
    job_uuid: str | None = None,
    user_id: int | None = None,
    provider_id: int = 0,
    target_lang: str = "",
    zaehler: dict | None = None,
    ausgeschlossen: set[int] | None = None,
    alter_ton_erlaubt: set[int] | None = None,
) -> list[tuple[Path, dict | None]]:
    """Voices all slides, the pieces run concurrently, reporting in slide order."""
    parallelism = resolve_tts_parallelism()
    logger.info("TTS provider_id={}: parallelism={}", provider_id, parallelism)
    total = len(slide_scripts)
    audio_paths: list[Path | None] = [tmp / f"slide_{i:03d}.mp3" for i in range(total)]
    alignments: list[dict | None] = [None] * total
    aus_zwischenspeicher = 0
    aus_altem_ton = 0
    ausgeschlossen = ausgeschlossen or set()
    alter_ton_erlaubt = alter_ton_erlaubt or set()

    fertige: set[int] = set()
    freigegeben = 0
    melde_lock = asyncio.Lock()

    async def _melde(i: int) -> None:
        """Releases the slide only when all before it are released."""
        nonlocal freigegeben
        async with melde_lock:
            fertige.add(i)
            while freigegeben in fertige:
                if on_slide_done:
                    on_slide_done(len(fertige), total, freigegeben)
                freigegeben += 1

    async def _zerlegen(i: int, script_text: str) -> list[str]:
        """Whatever need not be spoken is dropped here."""
        nonlocal aus_zwischenspeicher, aus_altem_ton
        if i in ausgeschlossen:
            audio_paths[i] = None
            logger.info("Slide {}/{}: nicht im Screencast", i + 1, total)
            await _melde(i)
            return []
        if not script_text.strip():
            # Empty slide: no audio file - create_slide_video handles None as video-only
            audio_paths[i] = None
            logger.info("Slide {}/{}: empty script, audio_path set to None", i + 1, total)
            await _melde(i)
            return []
        if job_uuid and user_id is not None:
            # The pool of the running job has to come first.
            ton = _lies_ton(user_id, job_uuid, f"render_cache/slide_{i:03d}.mp3")
            if ton is not None:
                audio_paths[i].write_bytes(ton)
                try:
                    align_data = get_job_file(user_id, job_uuid, f"render_cache/slide_{i:03d}_align.json")
                    alignments[i] = json.loads(align_data)
                except Exception:
                    pass
                logger.info("Slide {}/{}: loaded from storage (recovery)", i + 1, total)
                aus_zwischenspeicher += 1
                await _melde(i)
                return []
            if i in alter_ton_erlaubt:
                ton = _lies_ton(user_id, job_uuid, f"audio/slide_{i:03d}.mp3")
                if ton is not None:
                    audio_paths[i].write_bytes(ton)
                    logger.info("Slide {}/{}: Ton aus dem letzten Lauf", i + 1, total)
                    aus_altem_ton += 1
                    await _melde(i)
                    return []
        return _split_text(script_text)

    async def _hole_stueck(i: int, k: int, chunk: str, anzahl: int) -> bytes:
        # Retry temporary server errors with growing waits.
        retry_delays = (2.0, 5.0, 10.0)
        last_error: Exception | None = None
        for attempt in range(len(retry_delays) + 1):
            try:
                # Always 1.0: the provider lowers the pitch when slowing down.
                result = await asyncio.to_thread(
                    tts_client.synthesize_with_timestamps,
                    chunk, target_lang, voice_id=voice_id, speed=1.0,
                )
                # Timestamps of a piece do not apply to the whole slide.
                if anzahl == 1:
                    alignments[i] = result["alignment"]
                return result["audio_bytes"]
            except Exception as e:
                last_error = e
                err_str = str(e)
                is_transient = any(f"({code})" in err_str for code in ("500", "502", "503", "504", "429"))
                if attempt < len(retry_delays) and is_transient:
                    delay = retry_delays[attempt]
                    logger.warning(
                        "TTS failed for slide {} chunk {}/{} (attempt {}/{}): {} - retrying in {}s",
                        i + 1, k + 1, anzahl, attempt + 1, len(retry_delays) + 1, e, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                break
        logger.error("TTS failed for slide {} chunk {}/{} (gave up): {}", i + 1, k + 1, anzahl, last_error)
        raise HTTPException(
            status_code=502,
            detail=f"TTS-Fehler bei Folie {i + 1}: {last_error}",
        )

    def _sichern(i: int, audio_bytes: bytes) -> None:
        audio_paths[i].write_bytes(audio_bytes)
        # Save immediately to persistent storage for crash recovery
        if job_uuid and user_id is not None:
            save_job_file(user_id, job_uuid, f"render_cache/slide_{i:03d}.mp3", audio_bytes)
            if alignments[i]:
                save_job_file(user_id, job_uuid, f"render_cache/slide_{i:03d}_align.json",
                              json.dumps(alignments[i]).encode())
        logger.info("TTS for slide {}/{} done", i + 1, total)

    try:
        zerlegt = await asyncio.gather(*[_zerlegen(i, t) for i, t in enumerate(slide_scripts)])

        # Job list in slide order so slide 1 finishes first.
        auftraege: list[tuple[int, int]] = []
        stuecke: dict[int, list[bytes | None]] = {}
        for i, chunks in enumerate(zerlegt):
            if not chunks:
                continue
            stuecke[i] = [None] * len(chunks)
            auftraege.extend((i, k) for k in range(len(chunks)))

        naechster = 0
        pos_lock = asyncio.Lock()

        async def _arbeiter() -> None:
            nonlocal naechster
            while True:
                async with pos_lock:
                    if naechster >= len(auftraege):
                        return
                    i, k = auftraege[naechster]
                    naechster += 1
                stuecke[i][k] = await _hole_stueck(i, k, zerlegt[i][k], len(zerlegt[i]))
                # No await between storing and checking, so exactly one worker reports.
                if all(teil is not None for teil in stuecke[i]):
                    _sichern(i, b"".join(stuecke[i]))
                    await _melde(i)

        await asyncio.gather(*[_arbeiter() for _ in range(min(parallelism, len(auftraege)))])
    finally:
        if zaehler is not None:
            zaehler["aus_zwischenspeicher"] = aus_zwischenspeicher
            zaehler["aus_altem_ton"] = aus_altem_ton
    return list(zip(audio_paths, alignments))


async def convert_slides_to_images_async(
    pptx_path: Path, img_dir: Path, dpi: int = 100
) -> list[Path]:
    """Run LibreOffice image conversion in a thread."""
    return await asyncio.to_thread(pptx_to_images, pptx_path, img_dir, dpi)
