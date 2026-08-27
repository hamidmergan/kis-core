"""Temp directories and the periodic cleanup task for screencast uploads."""

import asyncio
import shutil
import time
from pathlib import Path

from loguru import logger

# Shared volume - accessible by celery-worker (mounted at /app/storage)
PPTX_TMP_DIR = Path("/app/storage/screencast_tmp")
IMAGE_TMP_DIR = Path("/app/storage/screencast_tmp/images")

_cleanup_task: asyncio.Task | None = None


async def _cleanup_old_pptx_files() -> None:
    """Periodically delete PPTX temp files and pre-rendered image dirs older than 1 hour."""
    while True:
        await asyncio.sleep(300)  # check every 5 minutes
        try:
            cutoff = time.time() - 3600
            if PPTX_TMP_DIR.exists():
                for f in PPTX_TMP_DIR.glob("*.pptx"):
                    try:
                        if f.stat().st_mtime < cutoff:
                            f.unlink(missing_ok=True)
                            logger.info("Cleanup: deleted expired PPTX {}", f.name)
                    except OSError:
                        pass
            if IMAGE_TMP_DIR.exists():
                for d in IMAGE_TMP_DIR.iterdir():
                    if d.is_dir():
                        try:
                            if d.stat().st_mtime < cutoff:
                                shutil.rmtree(d, ignore_errors=True)
                                logger.info("Cleanup: deleted expired image dir {}", d.name)
                        except OSError:
                            pass
        except Exception as e:
            logger.warning("Cleanup error: {}", e)


def maybe_start_cleanup_task() -> None:
    """Start the background cleanup task if not already running."""
    global _cleanup_task
    if _cleanup_task is None or _cleanup_task.done():
        try:
            _cleanup_task = asyncio.create_task(_cleanup_old_pptx_files())
        except RuntimeError:
            pass  # No running event loop yet
