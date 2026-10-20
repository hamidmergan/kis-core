"""Checks each provider per function with one real call, the same model and voice the app would use."""

from __future__ import annotations

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from datetime import datetime
from typing import Optional

from loguru import logger

from src.features.ai_providers.repository import provider_checks
from src.features.ai_providers.repository.feature_routes import get_route
from src.features.ai_providers.repository.providers import list_providers_with_capability
from src.limits import (
    PROVIDER_CHECK_DROPDOWN_MAX_AGE_SECONDS,
    PROVIDER_CHECK_DROPDOWN_WAIT_SECONDS,
    PROVIDER_CHECK_DROPDOWN_WORKERS,
    PROVIDER_CHECK_MAX_AGE_SECONDS,
    PROVIDER_CHECK_MIN_GAP_SECONDS,
    PROVIDER_CHECK_SEAT_WAIT_SECONDS,
)
from src.services import provider_slots
from src.services.feature_route_check import run_feature_route_test
from src.services.provider_transport import FEATURE_BUCKET

# The functions a person actually picks a provider for, in display order.
FEATURES: tuple[str, ...] = ("chat", "tts", "image_gen")

_lock = threading.Lock()
_last_run = 0.0


def _model_for(route: Optional[dict], provider_id: int) -> Optional[str]:
    """The model the app sends to this provider for the function, None when it has none there."""
    if not route:
        return None
    models = route.get("provider_models") or {}
    if str(provider_id) in models:
        return models[str(provider_id)]
    return route.get("model_name") if route.get("provider_id") == provider_id else None


def targets() -> list[tuple[str, dict, Optional[str]]]:
    """Every provider the app can really use per function: it has the function and a model for it."""
    out = []
    for feature in FEATURES:
        route = get_route(feature)
        for p in list_providers_with_capability(feature):
            model = _model_for(route, p["id"])
            if model is None and not (feature == "tts" and p.get("voices")):
                continue
            out.append((feature, p, model))
    return out


def _check_one(feature: str, provider: dict, model: Optional[str]) -> None:
    """One real call, inside a seat when the provider caps the bucket, so a running job is not disturbed."""
    bucket = FEATURE_BUCKET[feature]
    cap = (provider.get("concurrency") or {}).get(bucket)

    def call():
        return run_feature_route_test(
            feature=feature,
            protocol=provider["protocol"],
            base_url=provider["base_url"],
            api_key=provider.get("api_key"),
            model_name=model,
            voices=provider.get("voices") or [],
        )

    try:
        if cap:
            with provider_slots.slot(f"{provider['id']}:{bucket}", limit=int(cap),
                                     wait_seconds=PROVIDER_CHECK_SEAT_WAIT_SECONDS):
                result = call()
        else:
            result = call()
        status, error = result.status, result.error
    except provider_slots.ProviderFull:
        status, error = "busy", None
    except Exception as e:  # noqa: BLE001 - one broken check must not hide the others
        logger.exception("Anbieter-Check {} {} abgestürzt", provider["name"], feature)
        status, error = "error", f"{type(e).__name__}: {e}"
    if status != "ok":
        logger.info("Anbieter-Check {} {} ({}): {} {}", provider["name"], feature, model, status, error)
    provider_checks.set_check(provider["id"], feature, status=status, error=error)


def run_checks(*, force: bool) -> None:
    """Runs all checks at once, skipped when another run is going or one just finished."""
    global _last_run
    if not _lock.acquire(blocking=False):
        # Someone else is checking right now, wait for that result instead of calling twice.
        with _lock:
            return
    try:
        if force and time.time() - _last_run < PROVIDER_CHECK_MIN_GAP_SECONDS:
            return
        if not force and not _stale():
            return
        todo = targets()
        with ThreadPoolExecutor(max_workers=max(1, len(todo))) as pool:
            list(pool.map(lambda t: _check_one(*t), todo))
        _last_run = time.time()
    finally:
        _lock.release()


def _stale() -> bool:
    """True when any usable provider has no result yet or only one older than the limit."""
    stored = provider_checks.list_checks()
    now = time.time()
    for feature, p, _ in targets():
        row = stored.get((p["id"], feature))
        if row is None or now - datetime.fromisoformat(row["checked_at"]).timestamp() > PROVIDER_CHECK_MAX_AGE_SECONDS:
            return True
    return False


def status() -> dict:
    """Name, result and time of the last real call per usable provider, grouped by function."""
    stored = provider_checks.list_checks()
    out: dict[str, list] = {f: [] for f in FEATURES}
    for feature, p, _ in targets():
        row = stored.get((p["id"], feature)) or {}
        out[feature].append({
            "name": p["name"],
            "status": row.get("status"),
            "checked_at": row.get("checked_at"),
        })
    return out


_pool = ThreadPoolExecutor(max_workers=PROVIDER_CHECK_DROPDOWN_WORKERS, thread_name_prefix="provider-check")
_running: dict[tuple[int, str], Future] = {}
# When each check last started in this process, so a result that could not be stored does not lift the cap.
_last_start: dict[tuple[int, str], float] = {}
_running_lock = threading.Lock()


def _age(row: Optional[dict]) -> float:
    """Seconds since the stored result, infinite without one."""
    if not row:
        return float("inf")
    return time.time() - datetime.fromisoformat(row["checked_at"]).timestamp()


def _check_soon(feature: str, provider: dict, model: Optional[str], stored_age: float) -> Optional[Future]:
    """The running check for that provider, a new one once both results are old, else None."""
    key = (provider["id"], feature)
    with _running_lock:
        laufend = _running.get(key)
        if laufend is not None:
            return laufend
        seit_start = time.time() - _last_start.get(key, float("-inf"))
        if min(stored_age, seit_start) <= PROVIDER_CHECK_DROPDOWN_MAX_AGE_SECONDS:
            return None
        future = _pool.submit(_check_one, feature, provider, model)
        _last_start[key] = time.time()
        _running[key] = future

    def forget(done: Future) -> None:
        with _running_lock:
            if _running.get(key) is done:
                _running.pop(key, None)

    future.add_done_callback(forget)
    return future


def refused_ids(feature: str, provider_ids: Optional[set[int]] = None) -> set[int]:
    """Providers whose real call for the function fails, every older result is checked again at once and in parallel."""
    if feature not in FEATURES:
        return set()
    todo = [(p, model) for f, p, model in targets()
            if f == feature and (provider_ids is None or p["id"] in provider_ids)]
    stored = provider_checks.list_checks()
    futures = []
    for p, model in todo:
        alter = _age(stored.get((p["id"], feature)))
        f = _check_soon(feature, p, model, alter)
        # An old result is shown right away while the new check runs, only a missing one is waited for.
        if f is not None and alter == float("inf"):
            futures.append(f)
    if futures:
        # A check still running after the wait counts as passed, the next opening sees its result.
        wait(futures, timeout=PROVIDER_CHECK_DROPDOWN_WAIT_SECONDS)
        stored = provider_checks.list_checks()
    return {p["id"] for p, _ in todo if (stored.get((p["id"], feature)) or {}).get("status") == "error"}
