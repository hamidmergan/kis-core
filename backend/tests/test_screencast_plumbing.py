"""Small parts around the screencast that quietly did the wrong thing."""

import asyncio

from src.routes.screencast._shared import (
    _MAX_SCRIPT_GEN_LOCKS,
    _script_gen_locks,
    get_script_gen_lock,
    prerender_dir,
)
from src.services.screencast.naming import build_artifact_stem, translate_stem


class FakeService:
    def __init__(self):
        self.calls: list[str] = []

    def translate_filename(self, filename, source_lang, target_lang):
        self.calls.append(filename)
        return "Lecture_Notes.pptx"


def test_stem_uses_the_selected_service():
    service = FakeService()
    assert translate_stem("Vorlesungsnotizen.pptx", "DE", "EN-US", service=service) == "Lecture_Notes"
    assert service.calls == ["Vorlesungsnotizen.pptx"]


def test_stem_falls_back_when_the_service_fails():
    class Broken:
        def translate_filename(self, *a):
            raise RuntimeError("Anbieter weg")

    # Without a DeepL key the fallback path returns the original stem.
    assert translate_stem("Vorlesung.pptx", "DE", "EN-US", service=Broken()) == "Vorlesung"


def test_stem_without_service_still_works():
    assert translate_stem("", "DE", "EN-US") == "screencast"


def test_artifact_stem_appends_timestamp():
    from datetime import datetime

    assert build_artifact_stem("Lecture", datetime(2026, 7, 27, 9, 5)) == "Lecture_2026-07-27_0905"


def test_prerender_dir_is_separate_per_resolution():
    """Otherwise a 100 DPI cache gets used for a 144 DPI render."""
    a = prerender_dir("abc", 100)
    b = prerender_dir("abc", 144)
    assert a != b
    assert a.name == "dpi100" and b.name == "dpi144"


def test_script_gen_locks_do_not_grow_without_bound():
    _script_gen_locks.clear()
    for i in range(_MAX_SCRIPT_GEN_LOCKS + 50):
        get_script_gen_lock(f"job{i:04d}")
    assert len(_script_gen_locks) <= _MAX_SCRIPT_GEN_LOCKS


def test_held_lock_is_never_dropped():
    """Throwing away a held lock would allow two parallel runs."""
    async def _run():
        _script_gen_locks.clear()
        held = get_script_gen_lock("wichtig")
        await held.acquire()
        try:
            for i in range(_MAX_SCRIPT_GEN_LOCKS + 20):
                get_script_gen_lock(f"job{i:04d}")
            assert get_script_gen_lock("wichtig") is held
        finally:
            held.release()

    asyncio.run(_run())
