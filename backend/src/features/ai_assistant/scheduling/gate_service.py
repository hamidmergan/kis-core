"""Process-wide accessor for the weighted rate gate, wired to settings + Redis.

Default OFF via ``aia_gate_enabled``. When off, ``gate_acquire*`` are no-ops so
every call path behaves exactly as before. When on, each provider call waits for
its weighted share of the global budget. Grants are logged (area + wait) so the
split can be analysed under load.

Settings (admin-tunable, live):
  aia_gate_enabled            "false"   master switch
  aia_gate_global_per_sec     "2"       shared budget, 0 = unlimited
  aia_gate_weight_chat        "2"
  aia_gate_weight_ingest      "1"
  aia_gate_weight_studio      "1"
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from loguru import logger

from .weighted_gate import RedisWeightedGate

_GATE: Optional[WeightedGate] = None
_GATE_SIG: Optional[tuple] = None


def _default_get_setting(key: str, default: str = "") -> str:
    from src.features.admin.repository.settings import get_setting

    return get_setting(key, default)


def gate_enabled(get_setting: Callable[..., str] = _default_get_setting) -> bool:
    return str(get_setting("aia_gate_enabled", "false")).strip().lower() == "true"


def _config(get_setting: Callable[..., str]) -> tuple[float, dict[str, float]]:
    global_per_sec = float(get_setting("aia_gate_global_per_sec", "2"))
    weights = {
        "chat": float(get_setting("aia_gate_weight_chat", "2")),
        "ingest": float(get_setting("aia_gate_weight_ingest", "1")),
        "studio": float(get_setting("aia_gate_weight_studio", "1")),
    }
    return global_per_sec, weights


def get_gate(get_setting: Callable[..., str] = _default_get_setting) -> WeightedGate:
    """Singleton WeightedGate, rebuilt only when the settings change."""
    global _GATE, _GATE_SIG
    global_per_sec, weights = _config(get_setting)
    sig = (global_per_sec, tuple(sorted(weights.items())))
    if _GATE is None or _GATE_SIG != sig:
        _GATE = RedisWeightedGate(global_per_sec, weights)
        _GATE_SIG = sig
    return _GATE


def gate_acquire(
    area: str,
    max_wait: float = 30.0,
    get_setting: Callable[..., str] = _default_get_setting,
) -> bool:
    """Synchronous gate for worker call sites. Returns True (proceed) when the
    gate is disabled or on timeout."""
    if not gate_enabled(get_setting):
        return True
    t0 = time.monotonic()
    ok = get_gate(get_setting).acquire(area, max_wait=max_wait)
    logger.info("aia-gate area={} waited={:.3f}s ok={}", area, time.monotonic() - t0, ok)
    return ok


async def gate_acquire_async(
    area: str,
    max_wait: float = 30.0,
    get_setting: Callable[..., str] = _default_get_setting,
) -> bool:
    """Async gate for the synchronous-but-async chat path."""
    if not gate_enabled(get_setting):
        return True
    t0 = time.monotonic()
    ok = await get_gate(get_setting).acquire_async(area, max_wait=max_wait)
    logger.info("aia-gate area={} waited={:.3f}s ok={}", area, time.monotonic() - t0, ok)
    return ok
