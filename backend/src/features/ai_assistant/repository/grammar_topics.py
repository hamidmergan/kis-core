"""Themen der Grammatik-Übung: Ablage je Workspace.

Ein Thema ist nur ein Name, den ein Dozent tippt. Regel und Musterbeispiele
hängen zusätzlich an der Sprache, denn "Konjunktiv II" braucht auf Deutsch ein
anderes Beispiel als derselbe Kurs auf Englisch. Deshalb zwei Tabellen und nicht
eine.

Vorher standen die Themen im Code. Ein neues kostete einen Eintrag mit Regel,
Musterpaar je Sprache und beim Ankreuz-Format noch drei falschen Formen und drei
fertigen Beispielaufgaben. Das war für zwei Themen tragbar und für dreissig nicht.
"""

import json

from psycopg2.extras import RealDictCursor

from src.core.db.pool import get_connection
from src.features.ai_assistant.repository.exercise_pool import (
    materialize_pool_items_for_topic,
)


# Grundstock, damit niemand vor einer leeren Liste steht. Bewusst deutsch gedacht:
# für eine Hochschule mit türkischen Kursen taugt "Konjunktiv II" nichts, deren
# Dozenten tippen ihre Themen selbst, und genau dafür ist der freie Text da.
SEED_TOPICS = [
    {"name": "Passiv Präsens"},
    {"name": "Passiv mit Modalverb"},
    {"name": "Perfekt"},
    {"name": "Präteritum"},
    {"name": "Konjunktiv II"},
    {"name": "Relativsätze"},
    {"name": "Nebensätze"},
    {"name": "Adjektivdeklination"},
]

# Genau ein Paar. Der Generator hat nie ein zweites gelesen: er baut aus dem
# ersten die SHAPE TO COPY fuer das Modell und zeigt es dem Lernenden ueber der
# Aufgabe. Paar zwei und drei lagen nur in der Tabelle herum und standen im
# Formular als Felder, die nichts bewirkten.
MAX_EXAMPLES = 1

_EMPTY_PAIR = {"before": "", "after": ""}


def catalog_entry(topic: dict, spec: dict) -> dict:
    """Thema plus Ausarbeitung in der Form, die die Generatoren erwarten.

    Sie bekamen dieses dict bisher aus dem Code-Katalog. Bleibt die Form gleich,
    ändert sich an den Generatoren keine Zeile.

    ``example`` ist das erste Paar, denn genau eines zeigt die Aufgabe dem
    Lernenden. ``examples`` trägt alle, die steuern gemeinsam das Modell.
    """
    examples = list(spec.get("examples") or [])
    return {
        "id": topic["id"],
        "label": topic["name"],
        "rule": spec.get("rule") or "",
        "example": examples[0] if examples else dict(_EMPTY_PAIR),
        "examples": examples,
        # Die Anweisung je Aufgabenformat, beim Ausarbeiten des Themas mitformuliert.
        # Leer bei Themen von vor diesem Feld, dann greift die Schablone.
        "task_lines": dict(spec.get("task_lines") or {}),
    }


def list_grammar_topics(workspace_id: int) -> list[dict]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, name, created_by FROM aia_grammar_topics "
                "WHERE workspace_id = %s ORDER BY name",
                (workspace_id,),
            )
            return [dict(r) for r in cur.fetchall()]


def get_grammar_topic(topic_id) -> dict | None:
    if not topic_id:
        return None
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, workspace_id, name FROM aia_grammar_topics WHERE id = %s",
                (topic_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def create_grammar_topic(workspace_id: int, name: str, created_by: int) -> dict:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO aia_grammar_topics (workspace_id, name, created_by) "
                "VALUES (%s, %s, %s) RETURNING id, name, created_by",
                (workspace_id, name.strip(), created_by),
            )
            row = dict(cur.fetchone())
        conn.commit()
    return row


def delete_grammar_topic(topic_id: int) -> None:
    """Thema entfernen, samt Ausarbeitung und Vorrat.

    Vorher wandert der Inhalt des Vorrats in die Saetze, die darauf zeigen. Eine
    Aufgabe aus dem Vorrat wird beim Bauen eines Satzes nicht kopiert, der Satz
    verweist nur. Ohne diesen Schritt haette jemand mitten im Ueben ploetzlich
    Aufgaben ohne Loesung, weil eine Lehrkraft aufgeraeumt hat.

    Fertige Saetze bleiben also stehen. Sie verlieren nur den Themen-Namen ueber
    den Aufgaben, denn ``grammar_topic_id`` wird dabei auf NULL gesetzt.
    """
    materialize_pool_items_for_topic(topic_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM aia_grammar_topics WHERE id = %s", (topic_id,))
        conn.commit()


def get_topic_spec(topic_id: int, language: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT rule, examples, task_lines FROM aia_grammar_topic_specs "
                "WHERE topic_id = %s AND language = %s",
                (topic_id, language),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def save_topic_spec(topic_id: int, language: str, rule: str, examples: list,
                    task_lines: dict | None = None) -> dict:
    """Legt die Ausarbeitung an oder ersetzt sie.

    Mehr als :data:`MAX_EXAMPLES` Paare werden abgeschnitten, statt sie
    stillschweigend zu speichern und in der Ansicht zu verlieren.
    """
    trimmed = list(examples)[:MAX_EXAMPLES]
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO aia_grammar_topic_specs "
                "(topic_id, language, rule, examples, task_lines) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (topic_id, language) DO UPDATE "
                "SET rule = EXCLUDED.rule, examples = EXCLUDED.examples, "
                "    task_lines = EXCLUDED.task_lines "
                "RETURNING rule, examples, task_lines",
                (topic_id, language, rule, json.dumps(trimmed),
                 json.dumps(task_lines) if task_lines else None),
            )
            row = dict(cur.fetchone())
        conn.commit()
    return row


def seed_grammar_topics(workspace_id: int, created_by: int) -> None:
    """Grundstock in einen frischen Workspace kopieren.

    Ohne Ausarbeitung: die entsteht beim ersten Benutzen in der jeweiligen
    Sprache, sonst würde jeder neue Kurs acht Modell-Aufrufe kosten, von denen
    die meisten nie gebraucht werden.
    """
    for entry in SEED_TOPICS:
        create_grammar_topic(workspace_id, entry["name"], created_by)
