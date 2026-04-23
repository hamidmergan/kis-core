"""Screencast-Services: Paths, Process-Mgmt, PPTX, Video, Async-Generierung."""

from src.services.screencast.paths import (
    IMAGE_TMP_DIR,
    PPTX_TMP_DIR,
    maybe_start_cleanup_task,
)
from src.services.screencast.process import kill_job_procs, run_proc
from src.services.screencast.pptx import extract_text_per_slide, pptx_to_images
from src.services.screencast.video import (
    apply_faststart,
    concatenate_videos,
    create_slide_video,
    get_audio_duration,
)
from src.services.screencast.generation import (
    convert_slides_to_images_async,
    generate_all_scripts,
    generate_all_tts,
)

__all__ = [
    "IMAGE_TMP_DIR",
    "PPTX_TMP_DIR",
    "apply_faststart",
    "concatenate_videos",
    "convert_slides_to_images_async",
    "create_slide_video",
    "extract_text_per_slide",
    "generate_all_scripts",
    "generate_all_tts",
    "get_audio_duration",
    "kill_job_procs",
    "maybe_start_cleanup_task",
    "pptx_to_images",
    "run_proc",
]
