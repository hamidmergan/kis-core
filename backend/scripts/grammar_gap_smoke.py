"""Handprobe: liefert das Modell den vollen Satz plus Formtraeger statt einer Luecke?

Der Umbau vom 2026-08-12 verlaesst sich darauf, dass das Modell 'form_span' schickt und
KEINE fertige Luecke mehr. Haelt es sich nicht daran, faellt jede Luecken-Aufgabe durch
den Filter und die Sets kommen zu kurz heraus. Genau das wird hier gemessen.

Die Quelle ist absichtlich ein Grammatik-Arbeitsblatt mit Regeln DARIN, so wie die
Quellen des Sprachenzentrums (private/grammer/2/). Das war die Wurzel der Meldungen 4
und 6: "nimm die Fakten aus dem Text" ergab Saetze UEBER die Grammatik.

Der Ordner scripts/ ist nicht in den Container gemountet, deshalb ueber die Eingabe:
docker exec -i -w /app kis-backend python - < backend/scripts/grammar_gap_smoke.py
"""

import json

from src.features.ai_assistant.tasks._helpers import _get_llm_client
from src.features.ai_assistant.tasks.language_training import _source_grammar as sg
from src.features.ai_assistant.tasks.language_training._context import QuelleContext


# Ein Arbeitsblatt, wie es im Sprachenzentrum liegt: Fachinhalt UND Grammatikregeln.
QUELLE = """[Brandschutz.pdf, S. 1] Handfeuerloescher muessen jaehrlich geprueft werden.
Ein Handfeuerloescher haengt in jedem Flur. Das Gebaeude hat ein modernes
Rettungssystem. Die Feuerwehr prueft die Anlage regelmaessig. Ein Rauchmelder warnt
frueh vor Rauch. Die Mitarbeiter benutzen einen Loescher nur nach der Einweisung.

[Brandschutz.pdf, S. 2] Grammatik: Adjektivdeklination nach unbestimmtem Artikel.
Nach einem unbestimmten Artikel bekommt das Adjektiv im Nominativ Neutrum die Endung
-es, im Akkusativ Maskulinum die Endung -en. Beispiel: ein sicheres Rettungssystem,
einen roten Loescher. Das Adjektiv steht immer vor dem Nomen."""

THEMA = {
    "id": 1,
    "label": "Adjektivdeklination nach unbestimmtem Artikel",
    "rule": ("Input: a sentence with an adjective before a noun after an indefinite "
             "article. Output: the same sentence with the correct adjective ending."),
    "example": {"before": "Das ist ein neu Geraet.",
                "after": "Das ist ein neues Geraet."},
    "examples": [{"before": "Das ist ein neu Geraet.",
                  "after": "Das ist ein neues Geraet."}],
}

# Meldung 4 war eine Richtig/Falsch-Aufgabe zu Relativsaetzen, und die Quelle erklaerte
# die Regel. Deshalb ein zweiter Durchgang mit genau dieser Lage.
QUELLE_RELATIV = """[Grammatik.pdf, S. 1] Das Labor prueft die Proben, die aus dem
Betrieb kommen. Die Dozentin, deren Vorlesung ausfaellt, schickt die Folien. Der
Bericht, dessen Anhang fehlt, geht zurueck.

[Grammatik.pdf, S. 2] Grammatik: Relativsaetze im Genitiv. Das Relativpronomen im
Genitiv lautet dessen (maskulin, neutrum) und deren (feminin, Plural). Das konjugierte
Verb steht im Relativsatz immer am Ende."""

THEMA_RELATIV = {
    "id": 2,
    "label": "Relativsatz im Genitiv",
    "rule": ("Input: two sentences about the same thing. Output: one sentence with a "
             "relative clause using the genitive relative pronoun."),
    "example": {"before": "Der Kurs ist voll. Sein Titel ist neu.",
                "after": "Der Kurs, dessen Titel neu ist, ist voll."},
    "examples": [{"before": "Der Kurs ist voll. Sein Titel ist neu.",
                  "after": "Der Kurs, dessen Titel neu ist, ist voll."}],
}

WIE_VIELE = 6


def main():
    client, model, provider = _get_llm_client()
    print(f"Anbieter: {provider}, Modell: {model}\n")
    lauf(client, model, THEMA, QUELLE, "Brandschutz.pdf", ["cloze"])
    print()
    lauf(client, model, THEMA_RELATIV, QUELLE_RELATIV, "Grammatik.pdf", ["statement"])


def lauf(client, model, thema, quelle, datei, kinds):
    print(f"── {thema['label']}, Format {kinds[0]} ──")

    # Rohantwort mitlesen: die eigentliche Frage ist, WAS das Modell schickt.
    roh = []
    echt = client.chat.completions.create

    def mitlesen(**kwargs):
        antwort = echt(**kwargs)
        roh.append(antwort.choices[0].message.content or "")
        return antwort

    client.chat.completions.create = lambda **kw: mitlesen(**kw)
    # Die Quellen-Chips brauchen pgvector und sind hier nicht die Frage.
    sg.attach_chips_cited = lambda items, claims, ctx, **kw: items

    ctx = QuelleContext(
        context=quelle, first_label=datei, multi_label=datei,
        source_hint="folgender Source",
        source_by_name={datei: {"id": 1, "workspace_id": 1}},
        seen_pages_by_source={1: {1, 2}},
    )
    items, titel, _ = sg.generate_grammar_from_source(
        client, model, ctx, thema, WIE_VIELE, locale="de", kinds=kinds)

    gestellt = mit_span = mit_luecke = 0
    for text in roh:
        try:
            data = json.loads(sg._clean_llm_json(text))
        except Exception:
            print("!! Antwort war kein lesbares JSON")
            continue
        for ex in data.get("exercises") or []:
            if (ex.get("kind") or "") != kinds[0]:
                continue
            gestellt += 1
            if (ex.get("form_span") or "").strip():
                mit_span += 1
            if sg.GAP in (ex.get("sentence") or ""):
                mit_luecke += 1

    print(f"Aufrufe: {len(roh)}")
    print(f"Aufgaben geliefert: {gestellt}")
    print(f"davon mit 'form_span': {mit_span}")
    print(f"davon mit fertiger Luecke im Satz (alte Bauart): {mit_luecke}")
    print(f"durch die Filter gekommen: {len(items)} von {WIE_VIELE} bestellt")
    print(f"Titel: {titel}\n")

    for item in items:
        satz = item["front"].split("\n\n")[-1]
        print(f"  {satz}")
        print(f"    Loesung: {item['back']}   Optionen: {item.get('options')}")
    if not items:
        print("  (nichts durchgekommen, Rohantwort:)")
        print(roh[0][:1200] if roh else "  (keine Antwort)")


main()
