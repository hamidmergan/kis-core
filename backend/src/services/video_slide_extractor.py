"""Extract and describe slide frames from lecture videos.

Pipeline:
1. Extract candidate keyframes at scene changes (grouped by slide).
2. Ask a vision LLM to classify + describe: slide → describe, webcam → skip.
3. Merge descriptions into existing transcript chunks.
"""

import base64
import os
import re
import subprocess
import tempfile
from pathlib import Path

from loguru import logger
from openai import OpenAI

# ── Thresholds ────────────────────────────────────────────────────────────────

# Frame sampling interval for keyframe extraction (seconds)
_EXTRACT_INTERVAL_SEC = 2

# Scene change: any visual change (new bullet, minor animation)
_SCENE_THRESHOLD_MINOR = 0.03

# Scene change: big change (completely new slide)
_SCENE_THRESHOLD_MAJOR = 0.15

# Minimum seconds between two extracted frames
_MIN_FRAME_GAP_SEC = 5



# ── 1. Keyframe extraction ───────────────────────────────────────────────────

def extract_slide_frames(file_path: str) -> list[dict]:
    """Extract one image per distinct slide, using the most complete version.

    Two-pass approach:
    1. Extract ALL frames where any visual change occurs (minor threshold).
    2. Group frames: a major scene change starts a new group; minor changes
       within a group are treated as progressive reveal (new bullet points).
       Only the LAST frame of each group is kept (most complete slide state).

    Returns list of dicts: [{timestamp: float, image_path: str}, ...]
    Images are saved to a temporary directory (caller manages cleanup).
    """
    tmpdir = tempfile.mkdtemp(prefix="slides_")

    # Extract all frames with any visual change + their scene scores
    result = subprocess.run(
        [
            "ffmpeg", "-i", file_path,
            "-vf", (
                f"fps=1/{_EXTRACT_INTERVAL_SEC},"
                f"select='if(eq(n\\,0)\\,1\\,gt(scene\\,{_SCENE_THRESHOLD_MINOR}))',"
                "metadata=print,showinfo,scale=1280:-1"
            ),
            "-vsync", "vfr",
            "-q:v", "2",
            os.path.join(tmpdir, "slide_%06d.jpg"),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.warning("ffmpeg keyframe extraction failed: {}", result.stderr[:300])
        return []

    # Parse timestamps and scene scores from output
    timestamps: list[float] = []
    for match in re.finditer(r"pts_time:\s*([\d.]+)", result.stderr):
        timestamps.append(float(match.group(1)))

    scene_scores: list[float] = []
    for match in re.finditer(r"lavfi\.scene_score=([\d.]+)", result.stderr):
        scene_scores.append(float(match.group(1)))

    frames = sorted(Path(tmpdir).glob("slide_*.jpg"))
    if not frames:
        return []

    # Build list of all detected frames with metadata
    all_frames: list[dict] = []
    last_ts = -_MIN_FRAME_GAP_SEC - 1
    for i, frame in enumerate(frames):
        ts = timestamps[i] if i < len(timestamps) else i * _EXTRACT_INTERVAL_SEC
        score = scene_scores[i] if i < len(scene_scores) else 0.0
        if ts - last_ts >= _MIN_FRAME_GAP_SEC:
            all_frames.append({
                "timestamp": ts,
                "image_path": str(frame),
                "scene_score": score,
            })
            last_ts = ts

    if not all_frames:
        return []

    # Group frames: major scene change → new group, minor → same slide (progressive reveal)
    # Keep only the LAST frame per group (most complete version of that slide)
    groups: list[list[dict]] = [[all_frames[0]]]
    for frame in all_frames[1:]:
        if frame["scene_score"] >= _SCENE_THRESHOLD_MAJOR:
            # Big change → new slide group
            groups.append([frame])
        else:
            # Minor change → same slide, new bullet point etc.
            groups[-1].append(frame)

    # Take the last (most complete) frame from each group
    keyframes = [group[-1] for group in groups]

    logger.info(
        "Keyframe extraction: {} frames detected → {} groups → {} final slides",
        len(all_frames), len(groups), len(keyframes),
    )
    return keyframes


# ── 2. Vision-LLM: classify + describe ───────────────────────────────────────

_CLASSIFY_AND_DESCRIBE_PROMPT = (
    "Du analysierst Einzelbilder aus Vorlesungsvideos.\n\n"
    "Schritt 1 — Klassifikation:\n"
    "Ist auf dem Bild eine Vorlesungsfolie/Präsentation zu sehen? "
    "Oder ist es nur eine Webcam-Ansicht einer Person (kein Folieninhalt)?\n\n"
    "Schritt 2 — Wenn Folie:\n"
    "Gib den EXAKTEN Text wieder, der auf der Folie steht — Überschriften, Stichpunkte, Formeln, Beschriftungen. "
    "Ändere NICHTS am Wortlaut, interpretiere nicht, fasse nicht zusammen. "
    "Wenn Diagramme, Tabellen oder Abbildungen vorhanden sind, beschreibe diese kurz NACH dem Folientext. "
    "Ignoriere kleine Webcam-Fenster in den Ecken. "
    "Ignoriere UI-Elemente des Video-Players (Zeitanzeige, Buttons, Fortschrittsbalken).\n\n"
    "Antwortformat:\n"
    "- Wenn Folie: Beginne mit FOLIE: gefolgt vom exakten Folientext.\n"
    "- Wenn nur Webcam/Person: Antworte nur mit SKIP"
)


def classify_and_describe_slides(
    keyframes: list[dict],
    api_key: str,
    base_url: str,
    vision_model: str,
) -> list[dict]:
    """Classify each keyframe as slide or webcam, describe slides only.

    Frames classified as webcam-only are skipped.

    Returns list of dicts: [{timestamp: float, description: str}, ...]
    Only contains entries for frames that are actual slides.
    """
    client = OpenAI(api_key=api_key, base_url=base_url)
    results: list[dict] = []

    for i, kf in enumerate(keyframes):
        image_b64 = _encode_image_base64(kf["image_path"])
        if not image_b64:
            continue

        try:
            response = client.chat.completions.create(
                model=vision_model,
                messages=[
                    {"role": "system", "content": _CLASSIFY_AND_DESCRIBE_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                            },
                            {"type": "text", "text": "Klassifiziere und beschreibe dieses Bild."},
                        ],
                    },
                ],
                temperature=0.2,
                max_tokens=500,
            )
            answer = (response.choices[0].message.content or "").strip()

            if answer.upper().startswith("SKIP"):
                logger.info("Frame {}/{} at {:.0f}s → webcam, skipped", i + 1, len(keyframes), kf["timestamp"])
                continue

            # Strip "FOLIE:" prefix if present
            description = re.sub(r"^FOLIE:\s*", "", answer, flags=re.IGNORECASE).strip()
            if description:
                results.append({
                    "timestamp": kf["timestamp"],
                    "description": description,
                })
                logger.info(
                    "Frame {}/{} at {:.0f}s → slide ({} chars)",
                    i + 1, len(keyframes), kf["timestamp"], len(description),
                )
        except Exception as e:
            logger.warning("Failed to process frame {} at {:.0f}s: {}", i + 1, kf["timestamp"], e)

    logger.info("Slide extraction complete: {} slides described out of {} frames", len(results), len(keyframes))
    return results


def _encode_image_base64(image_path: str) -> str | None:
    """Read image file and return base64-encoded string."""
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None


# ── 3. Merge slide descriptions into transcript chunks ───────────────────────

def merge_slides_into_chunks(
    chunks: list[dict],
    slide_descriptions: list[dict],
) -> list[dict]:
    """Append matching slide descriptions to transcript chunk content.

    Each slide description is inserted into the chunk whose time range
    contains the slide's timestamp. If a slide falls between chunks,
    it's added to the nearest chunk.
    """
    if not slide_descriptions:
        return chunks

    for slide_num, slide in enumerate(slide_descriptions, start=1):
        ts = slide["timestamp"]
        desc = slide["description"]
        if not desc:
            continue

        best_idx = _find_best_chunk(chunks, ts)
        if best_idx is not None:
            chunks[best_idx]["content"] += f"\n\n[Folie {slide_num}]: {desc}"

    return chunks


def _find_best_chunk(chunks: list[dict], timestamp: float) -> int | None:
    """Find chunk index whose time range contains or is closest to timestamp."""
    if not chunks:
        return None

    # First: exact time range match
    for i, chunk in enumerate(chunks):
        start = chunk.get("start_time", 0)
        end = chunk.get("end_time", 0)
        if start <= timestamp <= end:
            return i

    # Fallback: nearest chunk by start_time
    best_idx = 0
    best_dist = float("inf")
    for i, chunk in enumerate(chunks):
        start = chunk.get("start_time", 0)
        dist = abs(start - timestamp)
        if dist < best_dist:
            best_dist = dist
            best_idx = i
    return best_idx
