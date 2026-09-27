"""The data table in packets: the columns are fixed once, every further packet only adds rows."""

import contextvars
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger

from src.services.upstream_errors import is_upstream_busy


def packets(parts: list[str], max_chars: int, max_packets: int = 0) -> list[list[str]]:
    """Greedy packets in part order, an oversize part travels alone."""
    out: list[list[str]] = []
    current: list[str] = []
    size = 0
    for part in parts:
        if current and size + len(part) > max_chars:
            out.append(current)
            current, size = [], 0
            # Beyond the cap the material is left out, one table must not run all afternoon.
            if max_packets and len(out) >= max_packets:
                return out
        current.append(part)
        size += len(part)
    if current:
        out.append(current)
    return out


def merge_tables(tables: list[dict | None]) -> dict | None:
    """Title and columns from the first packet that named them, rows of all of them after."""
    fertig: dict | None = None
    for table in tables:
        if not isinstance(table, dict):
            continue
        if fertig is None or not fertig.get("columns"):
            kopf = {k: v for k, v in table.items() if k != "rows"}
            fertig = {**kopf, "rows": list(fertig.get("rows") or [])} if fertig else {**kopf, "rows": []}
        spalten = len(fertig.get("columns") or [])
        for row in table.get("rows") or []:
            zellen = row.get("cells") if isinstance(row, dict) else None
            # A later packet may answer with its own idea of the table.
            if not isinstance(zellen, list) or (spalten and len(zellen) != spalten):
                continue
            fertig["rows"].append(row)
    return fertig if fertig and (fertig.get("columns") or fertig.get("rows")) else None


# Measured on the schedule: the provider runs two big requests side by side, a third slows all of them.
_PARALLEL_PACKETS = 2


def run_packets(packets_: list[list[str]], ask) -> dict | None:
    """Asks packet by packet: the first sets the columns, the rest only add rows."""
    if not packets_:
        return None
    texte = ["\n\n---\n\n".join(p) for p in packets_]

    voll: list[Exception] = []
    erste = _frage(ask, texte[0], None, voll)
    spalten = (erste or {}).get("columns")
    rest: list[dict | None] = [None] * (len(texte) - 1)
    if len(texte) > 1:
        with ThreadPoolExecutor(max_workers=_PARALLEL_PACKETS) as pool:
            futures = {pool.submit(contextvars.copy_context().run, _frage, ask, t, spalten, voll): i
                       for i, t in enumerate(texte[1:])}
            for fut in as_completed(futures):
                rest[futures[fut]] = fut.result()
    tabelle = merge_tables([erste, *rest])
    if tabelle is None and voll:
        # Not one packet came back because the provider was full, so the whole table waits and runs again.
        raise voll[0]
    return tabelle


def _frage(ask, text: str, columns, voll: list[Exception]) -> dict | None:
    """One packet, a packet the provider cannot answer costs only its own rows."""
    try:
        return ask(text, columns)
    except Exception as e:  # noqa: BLE001 - the other packets go on
        logger.warning("Datentabelle: Paket nicht beantwortet: {}", e)
        if is_upstream_busy(e):
            voll.append(e)
        return None
