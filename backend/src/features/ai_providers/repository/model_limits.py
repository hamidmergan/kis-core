"""CRUD fuer die Tabelle model_limits.

Eine Zeile je Anbieter und Modell: wie gross sein Fenster ist, ob es denkt und
welcher Schalter das Denken abstellt. Gemessen wird einmal, gelesen bei jeder
Anfrage. Die Messlogik selbst steht in ``src.services.model_limits``, hier liegt
nur der Speicher.
"""

from typing import Optional

import psycopg2.extras

from src.core.db.pool import get_connection


_SELECT = "provider_id, model_name, window_tokens, source, thinks, think_off, updated_at"


def _row_to_dict(row) -> dict:
    return {
        "provider_id": row["provider_id"],
        "model_name": row["model_name"],
        "window_tokens": row["window_tokens"],
        "source": row["source"],
        "thinks": bool(row["thinks"]),
        "think_off": row["think_off"] or "",
        "updated_at": row["updated_at"],
    }


def get_model_limit(provider_id: int, model_name: str) -> Optional[dict]:
    """Was ueber dieses Modell bekannt ist, oder ``None`` wenn es nie gemessen wurde."""
    if not provider_id or not model_name:
        return None
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"SELECT {_SELECT} FROM model_limits "
                "WHERE provider_id = %s AND model_name = %s",
                (provider_id, model_name),
            )
            row = cur.fetchone()
            return _row_to_dict(row) if row else None


def list_model_limits() -> list[dict]:
    """Alle Messungen, fuer die Anzeige im Admin."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(f"SELECT {_SELECT} FROM model_limits ORDER BY provider_id, model_name")
            return [_row_to_dict(r) for r in cur.fetchall()]


def set_model_limit(
    provider_id: int,
    model_name: str,
    *,
    window_tokens: int,
    source: str,
    thinks: bool = False,
    think_off: str = "",
) -> None:
    """Messergebnis wegschreiben oder ersetzen."""
    if not provider_id or not model_name:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO model_limits
                       (provider_id, model_name, window_tokens, source, thinks, think_off, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, NOW())
                   ON CONFLICT (provider_id, model_name) DO UPDATE
                       SET window_tokens = EXCLUDED.window_tokens,
                           source        = EXCLUDED.source,
                           thinks        = EXCLUDED.thinks,
                           think_off     = EXCLUDED.think_off,
                           updated_at    = NOW()""",
                (provider_id, model_name, int(window_tokens), source, bool(thinks), think_off or ""),
            )
            conn.commit()


def shrink_model_window(provider_id: int, model_name: str, window_tokens: int) -> None:
    """Ein im Betrieb gelerntes, KLEINERES Fenster eintragen.

    Nur verkleinern, nie vergroessern: gelernt wird aus einer Absage, und eine Absage
    beweist nur, dass das Fenster hoechstens so gross ist. Eine gemessene Zeile darf
    dadurch ueberschrieben werden, denn die Wirklichkeit im Betrieb schlaegt die Sonde.
    Gibt es noch keine Zeile, wird eine angelegt.
    """
    if not provider_id or not model_name or window_tokens <= 0:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO model_limits
                       (provider_id, model_name, window_tokens, source, updated_at)
                   VALUES (%s, %s, %s, 'gelernt', NOW())
                   ON CONFLICT (provider_id, model_name) DO UPDATE
                       SET window_tokens = LEAST(NULLIF(model_limits.window_tokens, 0), EXCLUDED.window_tokens),
                           source        = 'gelernt',
                           updated_at    = NOW()""",
                (provider_id, model_name, int(window_tokens)),
            )
            conn.commit()


def delete_model_limits_for_provider(provider_id: int) -> None:
    """Alle Messungen eines Anbieters vergessen.

    Noetig, wenn sich seine Adresse oder sein Schluessel aendert: dann steht hinter
    demselben Modellnamen moeglicherweise ein ganz anderes Fenster.
    """
    if not provider_id:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM model_limits WHERE provider_id = %s", (provider_id,))
            conn.commit()
