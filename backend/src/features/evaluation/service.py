"""Pure rules around the evaluation, without database access."""
import secrets

QUESTION_TYPES = ("scale", "text")

MAX_TITLE_CHARS = 120
MAX_INTRO_OUTRO_CHARS = 600
MAX_LINK_LABEL_CHARS = 80
MAX_LINK_URL_CHARS = 300
MAX_QUESTION_CHARS = 300
MAX_SCALE_LABEL_CHARS = 30
MAX_QUESTIONS = 20


def new_question_id() -> str:
    """Short id a question keeps for its whole life, stable across edits and answers."""
    return secrets.token_hex(4)


def default_config() -> dict:
    """A working first evaluation, so the admin edits something instead of starting blank.

    Fixed ids: nothing was saved yet, so this gets rebuilt on every read until the
    admin hits save. Random ids would then change on every read too, and a
    submission's answers would never match the questions it was shown for.
    """
    return {
        "active": False,
        "title": "Kurze Evaluation",
        "intro_text": "",
        "intro_link_label": "",
        "intro_link_url": "",
        "outro_text": "Vielen Dank, dass du dir die Zeit genommen hast.",
        "outro_link_label": "",
        "outro_link_url": "",
        "questions": [
            # General first, then the assistant, then the tools, the verdict and the open word last.
            {"id": "seed-1", "type": "scale", "text": "Wie klar war dir nach dem Rundgang, was KIS kann?",
             "scale_low": "gar nicht klar", "scale_high": "völlig klar"},
            {"id": "seed-2", "type": "scale", "text": "Wie hilfreich waren die Antworten vom KI-Assistenten Francis?",
             "scale_low": "nicht hilfreich", "scale_high": "sehr hilfreich"},
            {"id": "seed-3", "type": "scale", "text": "Wie gut konntest du nachvollziehen, woher eine Antwort von Francis stammt?",
             "scale_low": "gar nicht", "scale_high": "sehr gut"},
            {"id": "seed-4", "type": "scale", "text": "Wie leicht war es, eigenes Material in ein Modul zu laden?",
             "scale_low": "sehr mühsam", "scale_high": "sehr leicht"},
            {"id": "seed-5", "type": "text", "text": "Welches Werkzeug für Lehrende war für dich das nützlichste und welches das schwächste (z.B. Screencast, Übersetzung, Zusammenfassung, Glossar), und warum?"},
            {"id": "seed-6", "type": "text", "text": "Welches Lernwerkzeug war für dich das beste und welches das schlechteste (z.B. Karteikarten, Quiz, Datentabelle, Mindmap), und warum?"},
            {"id": "seed-7", "type": "scale", "text": "Wie einfach war die Bedienung von KIS insgesamt?",
             "scale_low": "umständlich", "scale_high": "sehr einfach"},
            {"id": "seed-8", "type": "scale", "text": "Wie wahrscheinlich ist es, dass du KIS wieder nutzt?",
             "scale_low": "eher nicht", "scale_high": "sehr wahrscheinlich"},
            {"id": "seed-9", "type": "text", "text": "Was hat gestört, gefehlt oder nicht funktioniert, und was möchtest du uns sonst noch mitgeben?"},
        ],
    }


def validate_questions(questions: list[dict]) -> list[dict]:
    """Trims and checks a question list, raises ValueError on anything unusable."""
    if not questions:
        raise ValueError("at least one question is required")
    if len(questions) > MAX_QUESTIONS:
        raise ValueError(f"at most {MAX_QUESTIONS} questions")
    bereinigt = []
    for frage in questions:
        typ = frage.get("type")
        if typ not in QUESTION_TYPES:
            raise ValueError(f"unknown question type {typ!r}")
        text = (frage.get("text") or "").strip()
        if not text:
            raise ValueError("question text must not be blank")
        if len(text) > MAX_QUESTION_CHARS:
            raise ValueError(f"question text must be at most {MAX_QUESTION_CHARS} characters")
        eintrag = {
            "id": frage.get("id") or new_question_id(),
            "type": typ,
            "text": text,
        }
        # Only a scale has ends to label, a free text field would carry them for nothing.
        if typ == "scale":
            for rand in ("scale_low", "scale_high"):
                beschriftung = (frage.get(rand) or "").strip()
                if len(beschriftung) > MAX_SCALE_LABEL_CHARS:
                    raise ValueError(f"{rand} must be at most {MAX_SCALE_LABEL_CHARS} characters")
                eintrag[rand] = beschriftung
        bereinigt.append(eintrag)
    return bereinigt


def summarize(responses: list[dict], questions: list[dict]) -> dict:
    """Turns raw submissions into the numbers the statistics tab shows.

    Submissions are only numbered, never tied back to an account: two answers
    from the same person read as two participants, which is the price of
    showing nothing that could identify anybody.
    """
    nach_frage: dict[str, list] = {frage["id"]: [] for frage in questions}
    for eintrag in responses:
        for antwort in eintrag["answers"]:
            if antwort["question_id"] in nach_frage:
                nach_frage[antwort["question_id"]].append(antwort["value"])

    fragen_auswertung = []
    for frage in questions:
        werte = nach_frage[frage["id"]]
        if frage["type"] == "scale":
            zahlen = [int(w) for w in werte if isinstance(w, (int, float)) or str(w).isdigit()]
            verteilung = {stufe: zahlen.count(stufe) for stufe in range(1, 6)}
            fragen_auswertung.append({
                "id": frage["id"],
                "type": "scale",
                "text": frage["text"],
                "answered": len(zahlen),
                "average": round(sum(zahlen) / len(zahlen), 2) if zahlen else None,
                "distribution": verteilung,
            })
        else:
            texte = [str(w).strip() for w in werte if str(w).strip()]
            fragen_auswertung.append({
                "id": frage["id"],
                "type": "text",
                "text": frage["text"],
                "answered": len(texte),
                "answers": texte,
            })

    # Oldest first, so participant 1 is the first person who answered.
    sortiert = sorted(responses, key=lambda e: e["created_at"])
    teilnahmen = [
        {
            "number": nummer,
            "created_at": eintrag["created_at"],
            "answers": eintrag["answers"],
        }
        for nummer, eintrag in enumerate(sortiert, start=1)
    ]

    return {"total": len(responses), "questions": fragen_auswertung, "responses": teilnahmen}


def validate_answers(answers: list[dict], questions: list[dict]) -> list[dict]:
    """Keeps only answers to questions that still exist, in the evaluation's own order."""
    nach_id = {antwort.get("question_id"): antwort.get("value") for antwort in answers}
    bereinigt = []
    for frage in questions:
        wert = nach_id.get(frage["id"])
        if wert is None or (isinstance(wert, str) and not wert.strip()):
            continue
        bereinigt.append({"question_id": frage["id"], "value": wert})
    if not bereinigt:
        raise ValueError("at least one answer is required")
    return bereinigt
