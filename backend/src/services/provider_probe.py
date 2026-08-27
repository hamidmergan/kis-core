"""Probes a provider and stores the result."""

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
    """Probes a provider, seed_capabilities overrides its capability list."""
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
    """Faengt jeden unerwarteten Adapterfehler ab."""
    try:
        adapter = make_adapter(protocol=protocol, base_url=base_url, api_key=api_key)
        return adapter.probe()
    except ValueError as e:
        # Unknown protocol from the database, caught as a precaution.
        return ProbeResult(capabilities=[], status="error", error=str(e))
    except Exception as e:  # noqa: BLE001 - probe must never crash the caller
        logger.exception("probe failed unexpectedly for protocol={} url={}", protocol, base_url)
        return ProbeResult(
            capabilities=[],
            status="error",
            error=f"{type(e).__name__}: {e}",
        )
