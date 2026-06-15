"""Run capability probes against a registered provider and persist the result.

Called from the admin routes when a provider is created, edited, or when the
admin presses "Re-probe" on an existing row. Thin orchestrator: pulls the row,
asks the right adapter, writes back capabilities + probe_status + probe_error.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

from src import database as db
from src.services.protocols import ProbeResult, make_adapter


def probe_provider(
    provider_id: int,
    *,
    seed_capabilities: bool = False,
) -> Optional[ProbeResult]:
    """Look up a provider, run its protocol probe, persist the result.

    ``seed_capabilities=False`` (default, re-probe path): write back only the
    probe-status + error fields. The admin's hand-curated capability list
    survives untouched — EXCEPT when the current list is empty and the probe
    succeeded, in which case we seed from the result. This recovers the case
    where the initial create probe failed (bad URL / key), wiped the seeded
    fixed_capabilities to ``[]``, and a later re-probe with corrected config
    must restore them.

    ``seed_capabilities=True`` (initial create path): also overwrite the
    capability list from the probe — used the first time we register a
    provider so the admin sees a sensible starting set in the UI.

    Returns the ``ProbeResult`` (including ``status='error'`` for handled
    probe failures), or ``None`` if the provider id is unknown.
    """
    provider = db.get_provider(provider_id)
    if provider is None:
        logger.warning("probe_provider: no row for id={}", provider_id)
        return None

    result = _run_probe(
        protocol=provider["protocol"],
        base_url=provider["base_url"],
        api_key=provider.get("api_key"),
    )

    current_caps = provider.get("capabilities", []) or []
    if seed_capabilities:
        capabilities = result.capabilities
    elif not current_caps and result.status == "ok":
        capabilities = result.capabilities
    else:
        capabilities = current_caps
    db.set_probe_result(
        provider_id,
        capabilities=capabilities,
        status=result.status,
        error=result.error,
    )
    return result


def _run_probe(*, protocol: str, base_url: str, api_key: Optional[str]) -> ProbeResult:
    """Catches any unexpected adapter error so a buggy protocol cannot bring
    down the request."""
    try:
        adapter = make_adapter(protocol=protocol, base_url=base_url, api_key=api_key)
        return adapter.probe()
    except ValueError as e:
        # Unknown protocol from the DB - should not happen since the API
        # validates input, but defensive in case of stale rows.
        return ProbeResult(capabilities=[], status="error", error=str(e))
    except Exception as e:  # noqa: BLE001 - probe must never crash the caller
        logger.exception("probe failed unexpectedly for protocol={} url={}", protocol, base_url)
        return ProbeResult(
            capabilities=[],
            status="error",
            error=f"{type(e).__name__}: {e}",
        )
