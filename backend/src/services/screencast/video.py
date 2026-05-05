"""FFmpeg-Helpers: Audio-Dauer, Slide-Clip-Erzeugung, Concat, Faststart."""

import subprocess
from pathlib import Path

from loguru import logger

from src.services.screencast.process import run_proc


def get_audio_duration(audio_path: Path | None) -> float:
    """Get the exact duration of an audio file in seconds using ffprobe.

    Returns 3.0 for silent slides (audio_path is None).
    """
    if audio_path is None:
        return 3.0
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe fehlgeschlagen: {result.stderr[:200]}")
    return float(result.stdout.strip())


def create_slide_video(image_path: Path, audio_path: Path | None, output_path: Path, pause: float = 0.0, crf: int = 23, job_uuid: str | None = None, silent_duration: float = 3.0) -> None:
    """Combine a single slide image with its audio into a video clip.

    If audio_path is None (silent/empty slide), produces a clip with silent
    audio whose length is ``silent_duration`` seconds (default 3s).
    """
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
            "-loop", "1", "-framerate", "1", "-i", str(image_path),
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
        total_duration = duration + pause
    else:
        final_audio = audio_path
        total_duration = duration

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-framerate", "1", "-i", str(image_path),
        "-i", str(final_audio),
        "-t", str(total_duration),
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


def apply_faststart(input_path: Path, output_path: Path) -> bytes:
    """Apply faststart to MP4 for web streaming."""
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-map", "0",
        "-c", "copy", "-movflags", "+faststart",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        logger.warning("faststart fix failed (rc={}): {}", result.returncode, result.stderr[:300])
        return input_path.read_bytes()
    return output_path.read_bytes()
