"""FFmpeg-Helpers: Audio-Dauer, Slide-Clip-Erzeugung, Concat, Faststart."""

import subprocess
from pathlib import Path

from loguru import logger

from src.services.screencast.outro import KI_HINWEIS
from src.services.screencast.process import run_proc

# Padding on the image length so the audio and not the image decides the end.
_BILD_RESERVE = 2.0

# Frames per second for the still, at 1 a slide under a second gets no frame at all.
_BILDRATE = 5


def get_audio_duration(audio_path: Path | None) -> float:
    """Audio length in seconds from the counted packets, 3.0 for silent slides."""
    if audio_path is None:
        return 3.0
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "packet=duration_time",
        "-of", "csv=p=0",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe fehlgeschlagen: {result.stderr[:200]}")
    total = 0.0
    for line in result.stdout.splitlines():
        try:
            total += float(line.strip().rstrip(","))
        except ValueError:
            continue
    if total <= 0:
        raise RuntimeError(f"Tonlänge nicht messbar: {audio_path}")
    return total


def get_video_duration(video_path: Path) -> float:
    """Length of a finished clip in seconds, it gives the offset of the next slide."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe fehlgeschlagen: {result.stderr[:200]}")
    try:
        return float(result.stdout.strip().rstrip(","))
    except ValueError:
        raise RuntimeError(f"Cliplaenge nicht messbar: {video_path}")


def _tempo_anpassen(audio_path: Path, output_path: Path, speed: float, job_uuid: str | None) -> Path:
    """Slow down locally so the pitch stays."""
    gedehnt = output_path.with_suffix(".tempo.mp3")
    cmd = [
        "ffmpeg", "-y", "-i", str(audio_path),
        "-filter:a", f"atempo={speed}",
        "-c:a", "libmp3lame", "-q:a", "2", str(gedehnt),
    ]
    result = run_proc(cmd, timeout=120, job_uuid=job_uuid)
    if result.returncode != 0:
        logger.warning("Tempo {} nicht anwendbar, nehme den Ton wie er ist: {}", speed, result.stderr[-200:])
        return audio_path
    return gedehnt


def create_slide_video(image_path: Path, audio_path: Path | None, output_path: Path, pause: float = 0.0, crf: int = 23, job_uuid: str | None = None, silent_duration: float = 3.0, speed: float = 1.0) -> None:
    """Assembles a slide image with its audio into a clip."""
    # Normalise: treat missing or empty audio files the same as None (silent slide)
    if audio_path is not None and (not audio_path.exists() or audio_path.stat().st_size == 0):
        logger.warning("Audio file is empty/missing ({}), falling back to silent slide", audio_path)
        audio_path = None

    logger.info(
        "Creating clip {}: image={} ({}b), audio={} ({}b)",
        output_path.name,
        image_path,
        image_path.stat().st_size if image_path.exists() else "MISSING",
        audio_path,
        audio_path.stat().st_size if audio_path and audio_path.exists() else "MISSING/None",
    )
    if audio_path is None:
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", str(_BILDRATE), "-i", str(image_path),
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(silent_duration),
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast",
            "-crf", str(crf), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-ar", "44100",
            "-shortest",
            str(output_path),
        ]
        result = run_proc(cmd, timeout=300, job_uuid=job_uuid)
        if result.returncode != 0:
            logger.error("Slide video creation failed (rc={}):\nSTDOUT: {}\nSTDERR: {}", result.returncode, result.stdout[-500:], result.stderr[-500:])
            raise RuntimeError(f"Video-Erstellung fehlgeschlagen (kein Audio): {result.stderr[-300:]}")
        return

    # The provider lowers the pitch when slowing down, which sounds hollow.
    if speed and abs(speed - 1.0) > 0.001:
        audio_path = _tempo_anpassen(audio_path, output_path, speed, job_uuid)

    duration = get_audio_duration(audio_path)

    if pause > 0:
        # Create silent audio segment
        silence_path = output_path.with_suffix(".silence.mp3")
        cmd_silence = [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            "anullsrc=r=44100:cl=stereo",
            "-t", str(pause),
            "-ac", "2", "-ar", "44100",
            "-c:a", "libmp3lame", str(silence_path),
        ]
        run_proc(cmd_silence, timeout=30, job_uuid=job_uuid)

        # Concatenate TTS audio + silence
        audio_with_pause_path = output_path.with_suffix(".paused.mp3")
        concat_audio_file = output_path.with_suffix(".audiolist.txt")
        with open(concat_audio_file, "w") as f:
            f.write(f"file '{audio_path}'\n")
            f.write(f"file '{silence_path}'\n")
        cmd_concat = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_audio_file),
            "-c", "copy", str(audio_with_pause_path),
        ]
        run_proc(cmd_concat, timeout=30, job_uuid=job_uuid)
        final_audio = audio_with_pause_path
        bild_dauer = duration + pause + _BILD_RESERVE
    else:
        final_audio = audio_path
        bild_dauer = duration + _BILD_RESERVE

    # -t only bounds the image, -shortest ends the clip at the end of the audio.
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", str(_BILDRATE), "-t", str(bild_dauer), "-i", str(image_path),
        "-i", str(final_audio),
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", "libx264", "-tune", "stillimage", "-preset", "ultrafast",
        "-crf", str(crf), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-ar", "44100",
        "-shortest",
        str(output_path),
    ]
    result = run_proc(cmd, timeout=300, job_uuid=job_uuid)
    if result.returncode != 0:
        logger.error("Slide video creation failed (rc={}):\nSTDOUT: {}\nSTDERR: {}", result.returncode, result.stdout[-500:], result.stderr[-500:])
        raise RuntimeError(f"Video-Erstellung fehlgeschlagen: {result.stderr[-300:]}")


def concatenate_videos(video_paths: list[Path], output_path: Path) -> None:
    """Concatenate multiple video clips into one MP4."""
    concat_file = output_path.parent / "concat_list.txt"
    with open(concat_file, "w") as f:
        for vp in video_paths:
            f.write(f"file '{vp}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        logger.error("Video concatenation failed: {}", result.stderr[:300])
        raise RuntimeError(f"Video concatenation failed: {result.stderr[:200]}")


def apply_faststart(input_path: Path, output_path: Path, subtitle_path: Path | None = None, subtitle_lang: str = "") -> bytes:
    """Faststart for the network, the subtitle track comes in without re-encoding."""
    cmd = ["ffmpeg", "-y", "-i", str(input_path)]
    if subtitle_path is not None:
        cmd += ["-i", str(subtitle_path)]
    cmd += ["-map", "0"]
    if subtitle_path is not None:
        cmd += ["-map", "1:0", "-c:s", "mov_text"]
        if subtitle_lang:
            cmd += ["-metadata:s:s:0", f"language={subtitle_lang}"]
    # A mark on the file so it can be read without watching the video.
    cmd += ["-metadata", f"comment={KI_HINWEIS}"]
    cmd += ["-c:v", "copy", "-c:a", "copy", "-movflags", "+faststart", str(output_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        logger.warning("faststart fix failed (rc={}): {}", result.returncode, result.stderr[:300])
        return input_path.read_bytes()
    return output_path.read_bytes()
