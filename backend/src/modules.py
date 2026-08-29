"""Welche Module diese Anlage ueberhaupt hat, gesetzt einmal in der .env."""

from functools import lru_cache

from loguru import logger

ALL_MODULES: tuple[str, ...] = ("aia", "tools")

MODULE_AIA = "aia"
MODULE_TOOLS = "tools"


class ModuleConfigError(ValueError):
    """MODULES enthaelt einen Namen, den es nicht gibt."""


def parse_modules(raw: str) -> frozenset[str]:
    """Liest den MODULES-Wert, leer bedeutet alle Module."""
    teile = [t.strip().lower() for t in (raw or "").split(",")]
    gewaehlt = [t for t in teile if t]
    if not gewaehlt:
        return frozenset(ALL_MODULES)
    unbekannt = sorted(set(gewaehlt) - set(ALL_MODULES))
    if unbekannt:
        raise ModuleConfigError(
            f"MODULES kennt {', '.join(unbekannt)} nicht, erlaubt sind {', '.join(ALL_MODULES)}"
        )
    return frozenset(gewaehlt)


@lru_cache(maxsize=1)
def active_modules() -> frozenset[str]:
    """Das Profil dieser Anlage, einmal gelesen und gemerkt."""
    from src.dependencies import get_settings

    gewaehlt = parse_modules(get_settings().modules)
    logger.info("Modul-Profil: {}", ", ".join(sorted(gewaehlt)))
    return gewaehlt
