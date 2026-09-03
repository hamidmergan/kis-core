"""Ready-made glossary entry, note, schedule and tool examples for the guided tour.

The tour shows what a glossary entry, a note, the schedule and the four
Fachsprachentrainer tools look like. All of it lives per person, so nothing an
owner prepares is visible to a visitor: whoever starts the tour gets their own
copy here. The texts come from the demo material itself, so a course with
other files gets nothing rather than a wrong entry.

The tool examples are copies of whatever the course owner already has ready,
never freshly generated for the visitor: a live run through Karteikarten, Quiz,
Datentabelle and Mindmap costs real model time, minutes rather than seconds
(see the schedule step above, which already turned out slower than expected).
Copying is instant and free. This means the owner has to prepare two sets per
tool once themselves, in the running app, exactly as any owner would; without
that this step quietly does nothing, same as the glossary step on a course
with different files.
"""

import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from loguru import logger

from src import database as db

_TZ_BERLIN = ZoneInfo("Europe/Berlin")
_STATS_TAGE = 3
_STATS_TREFFERQUOTE = 0.8

# The demo course this content belongs to, recognised by its files.
_PDF_DATEI = "DEMO_Skript_Kapitel_1_Grundlagen.pdf"
_VIDEO_DATEI = "DEMO_Vorlesung_01_Grundlagen.mp4"

# Must match DEMO_PDF in the frontend's demoSteps.ts: the tour has this one
# ticked by the time it reaches the chat step, the citation below has to match.
_CHAT_QUELLE_DATEI = "DEMO_Folien_06_Team_und_Methoden.pdf"

_GLOSSAR = {
    # Verbatim as it stands on page 2 ("1.4 Das magische Dreieck"), the jump-back
    # highlight searches for this exact text on that page and finds nothing otherwise.
    "term_de": "magische Dreieck",
    "term_en": "Iron triangle",
    "base_form": "Magisches Dreieck",
    "definition": (
        "Leistung, Termine und Kosten eines Projekts hängen zusammen und lassen sich "
        "nicht unabhängig voneinander verschieben."
    ),
    "definition_en": (
        "Scope, time and cost of a project are tied together and cannot be moved "
        "independently of each other."
    ),
    "example_sentence": "Wer eine Ecke verschiebt, verschiebt zwangsläufig mindestens eine zweite.",
    "example_sentence_en": "Whoever moves one corner inevitably moves at least one other.",
    "page_number": 2,
}

_NOTIZ_TITEL = "Was ein Projekt ausmacht"
_NOTIZ_TEXT = (
    "Ein Projekt ist ein Vorhaben, das im Wesentlichen durch die Einmaligkeit "
    "seiner Bedingungen gekennzeichnet ist."
)
_NOTIZ_ZEIT = "01:04"

# Both verbatim from page 8/9 of the Folien-Deck, so the citation truly points
# at what it claims to.
_CHAT_FRAGE = "Was bedeutet RACI?"
_CHAT_ANTWORT_VORLAGE = (
    "RACI beschreibt vier Rollen in der Verantwortungsmatrix: R (Responsible) führt "
    "die Arbeit aus, A (Accountable) steht für das Ergebnis gerade, C (Consulted) "
    "wird vorher gefragt, und I (Informed) wird nachher unterrichtet "
    "[Q1:{uuid}, S. 8]. Wichtig ist: Je Aufgabe darf es nur genau ein A geben, "
    "sonst gibt es in der Praxis keinen echten Verantwortlichen [Q1:{uuid}, S. 9]."
)
_CHAT_BELEGE = [
    {
        "page": 8,
        "text": (
            "RACI, vier Buchstaben Buchstabe Bedeutung Anzahl je Aufgabe R Responsible "
            "führt die Arbeit aus eine oder mehrere A Accountable steht für das Ergebnis "
            "gerade genau eine C Consulted wird vorher gefragt beliebig, sparsam "
            "einsetzen I Informed wird nachher unterrichtet beliebig"
        ),
    },
    {
        "page": 9,
        "text": (
            "Die eine Regel, die zählt Es darf je Aufgabe genau ein A geben. Zwei "
            "Verantwortliche bedeuten in der Praxis keinen Verantwortlichen, weil "
            "jeder auf den anderen verweisen kann."
        ),
    },
]


_WERKZEUG_TOOLS = ("karteikarten", "quiz")
_ANZAHL_JE_WERKZEUG = 2


def _quelle(quellen: list[dict], dateiname: str) -> dict | None:
    return next((q for q in quellen if q.get("filename") == dateiname), None)


def _kopiere_exercise_sets(
    workspace_id: int, eigentuemer_id: int, user_id: int, tool: str,
) -> list[dict]:
    """Copies up to 2 ready sets, returns the new sets (with their new item ids)."""
    vorlagen = [
        s for s in db.get_exercise_sets(workspace_id, eigentuemer_id, tool=tool)
        if s.get("status") == "ready"
    ][:_ANZAHL_JE_WERKZEUG]
    neue: list[dict] = []
    for vorlage in vorlagen:
        voll = db.get_exercise_set_with_items(vorlage["id"])
        if not voll or not voll.get("items"):
            continue
        neu = db.create_exercise_set(
            workspace_id, user_id, tool, voll["title"], voll["mode"],
            voll.get("source_uuid"), voll["items"],
        )
        neue.append(neu)
    return neue


def _saet_uebungsverlauf(workspace_id: int, user_id: int, neue_sets: list[dict]) -> None:
    """Backdates answers over the last few days, so Statistik is not a blank page.

    An account nobody has practiced on yet shows nothing under Statistik, which
    reads as broken on a first visit even though it is working as designed. This
    gives every visitor a short, believable history instead of an empty one, in
    the same random-but-plausible spirit as picking correct vs. wrong per answer.
    """
    heute = datetime.now(_TZ_BERLIN).date()
    zufall = random.Random(user_id)
    # Today (Versatz 0) always gets a set: Statistik is checked right after
    # seeding, and a shuffle that happened to skip today would show a blank
    # page on the very first look even though older entries exist.
    resttage = list(range(1, _STATS_TAGE))
    zufall.shuffle(resttage)
    tag_versaetze = [0] + resttage
    while len(tag_versaetze) < len(neue_sets):
        tag_versaetze.append(zufall.randrange(_STATS_TAGE))

    zeilen: list[dict] = []
    for ex_set, versatz in zip(neue_sets, tag_versaetze):
        # One whole set per sitting, not single cards scattered across days:
        # a real round is worked through in one go, and the per-set ratio in
        # the activity feed reads as one coherent attempt instead of noise.
        tag = heute - timedelta(days=versatz)
        uhrzeit = datetime.combine(tag, datetime.min.time(), tzinfo=_TZ_BERLIN) \
            + timedelta(hours=9 + zufall.random() * 10)
        for item in ex_set.get("items", []):
            zeilen.append({
                "set_id": ex_set["id"],
                "item_id": item["id"],
                "user_id": user_id,
                "correct": zufall.random() < _STATS_TREFFERQUOTE,
                "run_no": 1,
                "answered_at": uhrzeit,
            })
    if not zeilen:
        return
    db.seed_exercise_progress(zeilen)
    db.seed_streak(workspace_id, user_id, _STATS_TAGE, heute)


def _kopiere_mindmaps(workspace_id: int, eigentuemer_id: int, user_id: int) -> int:
    vorlagen = db.get_all_aia_mindmaps(workspace_id, eigentuemer_id)[:_ANZAHL_JE_WERKZEUG]
    kopiert = 0
    for vorlage in vorlagen:
        voll = db.get_aia_mindmap(vorlage["id"])
        if not voll or not voll.get("mindmap"):
            continue
        neue_id = db.create_aia_mindmap(workspace_id, user_id, voll.get("source_ids") or [])
        db.update_aia_mindmap(neue_id, "success", mindmap=voll["mindmap"], title=voll.get("title"))
        kopiert += 1
    return kopiert


def _kopiere_data_tables(workspace_id: int, eigentuemer_id: int, user_id: int) -> int:
    vorlagen = db.get_aia_data_tables_by_workspace(workspace_id, eigentuemer_id)[:_ANZAHL_JE_WERKZEUG]
    kopiert = 0
    for vorlage in vorlagen:
        voll = db.get_aia_data_table(vorlage["id"])
        if not voll or not voll.get("table_data"):
            continue
        neue_id = db.create_aia_data_table(workspace_id, user_id, voll.get("source_ids") or [])
        db.update_aia_data_table(
            neue_id, "success", title=voll.get("title"),
            table_data=voll["table_data"], sources=voll.get("sources"),
        )
        kopiert += 1
    return kopiert


def _stelle_heute_uebung_sicher(workspace_id: int, user_id: int) -> None:
    """Tops up today with one practiced round per tool, on every tour start.

    The one-time copy above only ever runs once per visitor, so a returning
    visitor's Statistik goes stale the day after. This keeps "today" alive on
    every tour start instead, and does nothing once today already has real
    (or an earlier top-up's) activity.
    """
    if db.hat_heute_geuebt(workspace_id, user_id):
        return
    zufall = random.Random(f"{user_id}:{datetime.now(_TZ_BERLIN).date()}")
    for tool in _WERKZEUG_TOOLS:
        sets = [
            s for s in db.get_exercise_sets(workspace_id, user_id, tool=tool)
            if s.get("status") == "ready"
        ]
        if not sets:
            continue
        voll = db.get_exercise_set_with_items(zufall.choice(sets)["id"])
        if not voll or not voll.get("items"):
            continue
        ergebnisse = [
            {"item_id": item["id"], "correct": zufall.random() < _STATS_TREFFERQUOTE}
            for item in voll["items"]
        ]
        db.bulk_record_exercise_progress(voll["id"], user_id, ergebnisse, new_run=True)


def _lege_werkzeug_beispiele_an(workspace_id: int, user_id: int) -> int:
    """Copies up to 2 ready sets per Fachsprachentrainer tool from the owner.

    Marked once copying actually happened, never on an empty attempt: an owner
    who has not prepared examples yet just means later visitors try again,
    instead of a mark that permanently locks the course out.
    """
    if db.demo_tools_already_seeded(workspace_id, user_id):
        return 0
    workspace = db.get_aia_workspace_by_id(workspace_id)
    eigentuemer_id = workspace["user_id"] if workspace else None
    if eigentuemer_id is None or eigentuemer_id == user_id:
        return 0

    neue_sets: list[dict] = []
    for tool in _WERKZEUG_TOOLS:
        neue_sets += _kopiere_exercise_sets(workspace_id, eigentuemer_id, user_id, tool)
    gesamt = len(neue_sets)
    gesamt += _kopiere_mindmaps(workspace_id, eigentuemer_id, user_id)
    gesamt += _kopiere_data_tables(workspace_id, eigentuemer_id, user_id)

    if gesamt > 0:
        _saet_uebungsverlauf(workspace_id, user_id, neue_sets)
        db.mark_demo_tools_seeded(workspace_id, user_id)
    else:
        logger.info(
            "Rundgang: Kurs {} hat noch keine Werkzeug-Beispiele beim Eigentuemer, "
            "nichts kopiert", workspace_id,
        )
    return gesamt


def lege_rundgang_inhalte_an(workspace_id: int, user_id: int) -> dict:
    """Puts one glossary entry and one note in place, existing ones stay untouched."""
    quellen = db.get_aia_sources_by_workspace(workspace_id)
    pdf = _quelle(quellen, _PDF_DATEI)
    video = _quelle(quellen, _VIDEO_DATEI)
    if pdf is None or video is None:
        logger.info("Rundgang: Kurs {} traegt andere Dateien, keine Inhalte angelegt", workspace_id)
        return {"glossary": 0, "notes": 0}

    eintraege = db.bulk_create_glossary_entries(pdf["id"], user_id, [_GLOSSAR])

    notizen = db.get_aia_notes(workspace_id, user_id)
    schon_da = any(n.get("title") == _NOTIZ_TITEL for n in notizen)
    if not schon_da:
        stichwort = _NOTIZ_TEXT[:40].strip()
        beleg = f"[Q1:{video['uuid']}, {_NOTIZ_ZEIT} | {stichwort}]"
        db.create_aia_note(
            workspace_id,
            user_id,
            f"{_NOTIZ_TEXT} {beleg}",
            title=_NOTIZ_TITEL,
            source_uuids=[video["uuid"]],
        )

    # Every source in the course, not just the two the tour opens itself: the
    # schedule step shows the full timeline, not a stub tied to one material.
    if not db.get_schedule_entries(workspace_id, user_id):
        alle_uuids = [q["uuid"] for q in quellen]
        job = db.create_schedule_job(workspace_id, user_id, alle_uuids)
        from src.tasks.aia_tasks import run_generate_schedule
        run_generate_schedule.delay(job["id"], workspace_id, user_id, alle_uuids)

    werkzeuge = _lege_werkzeug_beispiele_an(workspace_id, user_id)
    _stelle_heute_uebung_sicher(workspace_id, user_id)

    return {"glossary": len(eintraege), "notes": 0 if schon_da else 1, "tools": werkzeuge}


def lege_chat_beispiel_an(workspace_id: int, user_id: int) -> bool:
    """Puts one example question and answer in the chat, but only when called.

    Kept apart from lege_rundgang_inhalte_an on purpose: the chat panel sits in
    the middle column and stays visible through every earlier step, unlike the
    glossary/notes/schedule/tools tabs that only show once their own step
    switches to them. Writing this at tour start would make it visible from
    step one, defeating the point of a guided reveal. The frontend calls this
    only when the chat step itself is reached, then reloads the message list.
    """
    if db.get_aia_messages(workspace_id, user_id, limit=1):
        # Real conversation or an earlier run of this already exists, either
        # way nothing manufactured belongs on top of it.
        return False
    quellen = db.get_aia_sources_by_workspace(workspace_id)
    quelle = _quelle(quellen, _CHAT_QUELLE_DATEI)
    if quelle is None:
        return False

    db.save_aia_message(workspace_id, user_id, "user", _CHAT_FRAGE)
    db.save_aia_message(
        workspace_id, user_id, "assistant",
        _CHAT_ANTWORT_VORLAGE.format(uuid=quelle["uuid"]),
        source_pages=[
            {
                "source_uuid": quelle["uuid"],
                "filename": quelle["filename"],
                "page_number": beleg["page"],
                "source_text": beleg["text"],
            }
            for beleg in _CHAT_BELEGE
        ],
        source_qmap=[{
            "qnum": 1, "uuid": quelle["uuid"], "filename": quelle["filename"],
            "is_media": False,
        }],
    )
    return True
