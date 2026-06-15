"""Normalise uploaded media containers for reliable native-browser playback.

A fragmented MP4 (fMP4/CMAF: a tiny init ``moov`` + ``sidx`` + many ``moof``/``mdat``
fragments) is built for MSE/HLS/DASH — NOT for direct ``<audio>``/``<video src>``
progressive playback. Browsers routinely skip a whole fragment mid-stream, which makes
the audio jump and desyncs the transcript highlight. The fix is a LOSSLESS remux
(``ffmpeg -c copy``) into a progressive MP4 with the ``moov`` atom up front
(``-movflags +faststart``). No re-encoding, no quality loss, ~I/O-bound.
"""

import os
import subprocess
import tempfile
from typing import Optional

from loguru import logger


# A reader is any ``read(offset, length) -> bytes`` callable (local file seek, or an S3
# byte-range fetch). The scan only ever reads 16-byte box *headers*, so it decides without
# touching the media body — a handful of tiny reads even for a multi-GB remote object.
_MAX_BOXES = 100_000  # safety bound against a malformed/looping file


def _scan_is_fragmented(read) -> bool:
    """Walk top-level ISO-BMFF boxes. Return True at the first ``moof`` (fragmented), False
    at the first top-level ``mdat`` (progressive: a fragmented file always has a ``moof``
    before its first ``mdat``), and False for non-ISO-BMFF / malformed / truncated input."""
    head = read(0, 8)
    if len(head) < 8 or head[4:8] != b"ftyp":
        return False  # not ISO-BMFF → not our case
    pos = 0
    for _ in range(_MAX_BOXES):
        hdr = read(pos, 16)
        if len(hdr) < 8:
            return False
        box_size = int.from_bytes(hdr[:4], "big")
        box_type = hdr[4:8]
        if box_type == b"moof":
            return True
        if box_type == b"mdat":
            return False
        if box_size == 1:               # 64-bit extended size follows the 8-byte header
            if len(hdr) < 16:
                return False
            box_size = int.from_bytes(hdr[8:16], "big")
        if box_size < 8:                # 0 (extends to EOF) or malformed → stop
            return False
        pos += box_size
    return False


def is_fragmented_mp4(path: str) -> bool:
    """True iff the local file ``path`` is a fragmented MP4 (ISO-BMFF with a top-level
    ``moof``). Progressive MP4s and non-ISO-BMFF inputs (mp3, wav, …) return False."""
    try:
        with open(path, "rb") as f:
            def _read(off: int, length: int) -> bytes:
                f.seek(off)
                return f.read(length)
            return _scan_is_fragmented(_read)
    except OSError:
        return False


def is_fragmented_mp4_reader(read) -> bool:
    """Detect fragmentation over a ``read(offset, length) -> bytes`` callable — e.g. an S3
    byte-range fetch — so a remote object is classified from a few KB of box headers
    instead of a full download. Any reader error is treated as 'not fragmented'."""
    try:
        return _scan_is_fragmented(read)
    except Exception:
        return False


def remux_to_progressive(src: str, dst: str) -> None:
    """Losslessly remux ``src`` into a progressive faststart MP4 at ``dst`` (no re-encode)."""
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", src,
         "-c", "copy", "-movflags", "+faststart", dst],
        capture_output=True,
    )
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", "replace")[:300]
        raise RuntimeError(f"ffmpeg remux failed: {err}")


def normalize_if_fragmented(path: str) -> Optional[str]:
    """If ``path`` is a fragmented MP4, remux it to a progressive faststart copy and return
    that copy's path. The caller owns the returned file (upload it, then delete it). Returns
    ``None`` when no change is needed (already progressive, or not an MP4)."""
    if not is_fragmented_mp4(path):
        return None
    fd, out = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        remux_to_progressive(path, out)
    except Exception:
        os.unlink(out)
        raise
    logger.info("media_normalize: remuxed fragmented MP4 -> progressive faststart ({})", path)
    return out
