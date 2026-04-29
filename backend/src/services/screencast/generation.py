"""Async-Generierung: Skripte (KISSKI-Batch), TTS (ElevenLabs parallel), Bildkonvertierung."""

import asyncio
import json
from collections.abc import Callable
from pathlib import Path

from fastapi import HTTPException
from loguru import logger

from src.services.elevenlabs_client import ElevenLabsClient
from src.services.kisski_client import KisskiClient
from src.services.screencast.pptx import pptx_to_images
from src.storage import get_job_file, save_job_file


async def generate_all_scripts(
    slide_texts: list[str],
    kisski_client: KisskiClient,
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
            kisski_client.generate_scripts_batch, slide_texts, glossary, add_greeting, add_closing,
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


async def generate_all_tts(
    slide_scripts: list[str],
    tts_client: ElevenLabsClient,
    tmp: Path,
    speed: float,
    voice_id: str = "",
    on_slide_done: Callable[[int, int], None] | None = None,
    job_uuid: str | None = None,
    user_id: int | None = None,
) -> list[tuple[Path, dict | None]]:
    """Generate TTS audio for all slides in parallel via ElevenLabs.

    Returns a list of (audio_path, alignment_or_None) tuples.
    on_slide_done(current, total) is called after each slide completes.
    Each slide's audio is saved to persistent storage immediately after synthesis
    so a crash can be recovered without re-paying for completed slides.
    """
    sem = asyncio.Semaphore(10)
    lock = asyncio.Lock()
    counter = 0
    total = len(slide_scripts)
    audio_paths: list[Path | None] = [tmp / f"slide_{i:03d}.mp3" for i in range(total)]
    alignments: list[dict | None] = [None] * total

    async def _tts(i: int, script_text: str) -> None:
        nonlocal counter
        if not script_text.strip():
            # Empty slide: no audio file — create_slide_video handles None as video-only
            audio_paths[i] = None
            logger.info("Slide {}/{}: empty script, audio_path set to None", i + 1, total)
        else:
            # Recovery: check if this slide was already synthesized in a previous (crashed) run
            if job_uuid and user_id is not None:
                try:
                    audio_data = get_job_file(user_id, job_uuid, f"render_cache/slide_{i:03d}.mp3")
                    audio_paths[i].write_bytes(audio_data)
                    try:
                        align_data = get_job_file(user_id, job_uuid, f"render_cache/slide_{i:03d}_align.json")
                        alignments[i] = json.loads(align_data)
                    except Exception:
                        pass
                    logger.info("Slide {}/{}: loaded from storage (recovery)", i + 1, total)
                    async with lock:
                        counter += 1
                        if on_slide_done:
                            on_slide_done(counter, total)
                    return
                except Exception:
                    pass  # Not saved yet — synthesize normally

            async with sem:
                # Retry transient server errors (5xx) with exponential backoff.
                # myLab/ElevenLabs occasionally return 500s that recover within seconds.
                retry_delays = (2.0, 5.0, 10.0)
                last_error: Exception | None = None
                for attempt in range(len(retry_delays) + 1):
                    try:
                        result = await asyncio.to_thread(
                            tts_client.synthesize_with_timestamps,
                            script_text, "EN", voice_id=voice_id, speed=speed,
                        )
                        audio_bytes = result["audio_bytes"]
                        alignment = result["alignment"]
                        audio_paths[i].write_bytes(audio_bytes)
                        alignments[i] = alignment

                        # Save immediately to persistent storage for crash recovery
                        if job_uuid and user_id is not None:
                            save_job_file(user_id, job_uuid, f"render_cache/slide_{i:03d}.mp3", audio_bytes)
                            if alignment:
                                save_job_file(user_id, job_uuid, f"render_cache/slide_{i:03d}_align.json",
                                              json.dumps(alignment).encode())

                        logger.info("TTS for slide {}/{} done (attempt {})", i + 1, total, attempt + 1)
                        last_error = None
                        break
                    except Exception as e:
                        last_error = e
                        err_str = str(e)
                        is_transient = any(f"({code})" in err_str for code in ("500", "502", "503", "504", "429"))
                        if attempt < len(retry_delays) and is_transient:
                            delay = retry_delays[attempt]
                            logger.warning(
                                "TTS failed for slide {} (attempt {}/{}): {} — retrying in {}s",
                                i + 1, attempt + 1, len(retry_delays) + 1, e, delay,
                            )
                            await asyncio.sleep(delay)
                            continue
                        break

                if last_error is not None:
                    logger.error("TTS failed for slide {} (gave up): {}", i + 1, last_error)
                    raise HTTPException(
                        status_code=502,
                        detail=f"TTS-Fehler bei Folie {i + 1}: {last_error}",
                    )
        async with lock:
            counter += 1
            if on_slide_done:
                on_slide_done(counter, total)

    await asyncio.gather(*[_tts(i, t) for i, t in enumerate(slide_scripts)])
    return list(zip(audio_paths, alignments))


async def convert_slides_to_images_async(
    pptx_path: Path, img_dir: Path, dpi: int = 100
) -> list[Path]:
    """Run LibreOffice image conversion in a thread."""
    return await asyncio.to_thread(pptx_to_images, pptx_path, img_dir, dpi)
