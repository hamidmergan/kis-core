"""Smoke test: does the model find the right spots and not the known false hits?"""

from src.features.ai_assistant.tasks._helpers import _get_llm_client
from src.features.ai_assistant.tasks.studio.schedule._discover import (
    _discover_in_blocks,
    _locate,
)

# (block, should something be found?)
BLOCKS = [
    ("Ders programi\nSinav: 12.05.2026 saat 10:00\n"
     "Sunum tarihleri daha sonra duyurulacak.\nOdev teslimi: 20.06.2026", True),
    ("Calendario del curso\nExamen final: 15 de julio de 2026\n"
     "Tutorias: fecha a convenir con el profesor.", True),
    ("Programme du cours\nLes dates de soutenance sont a convenir avec l'enseignant.\n"
     "Rendu du dossier: 30.04.2026", True),
    ("Kursplan\nDie Vorlesung findet woechentlich dienstags um 10:00 Uhr statt und "
     "wird aufgezeichnet. Die Folien liegen in Moodle.", False),
    ("Course schedule\nMidterm exam on 12.05.2026 at 10:00 in room A1.\n"
     "All materials are available in the learning platform.", False),
    ("Und dann ab dem 22. April wird es, wie schon vorhin besprochen, offene "
     "Sprechstunden geben. Und alles Weitere, wann die Peer Reviews stattfinden sollen "
     "und so weiter und so fort, koennen Sie nochmal im Kursplan nachschauen. An dieser "
     "Stelle haben Sie jetzt noch Fragen. Kann ich noch auf etwas eingehen?", False),
    ("| Online-Praesenz: tba, mgl. Schreibwerkstatt, Poster         "
     "| 27.06.2026, 10:00-14.30 Uhr                              |                    |",
     False),
]


def main():
    client, model, provider = _get_llm_client()
    print(f"Anbieter: {provider}, Modell: {model}\n")
    blocks = [(i, text) for i, (text, _soll) in enumerate(BLOCKS)]
    found = _discover_in_blocks(client, model, blocks)

    fehler = 0
    for i, (text, soll) in enumerate(BLOCKS):
        # Only the open spot counts here, not the date hits of the same call.
        phrase = (found.get(i) or {}).get("tbd")
        if phrase is not None and _locate(text, phrase) is None:
            phrase = None  # nicht im Text, wird verworfen
        ok = (phrase is not None) == soll
        fehler += 0 if ok else 1
        zeichen = "ok " if ok else "FEHLER"
        was = repr(phrase) if phrase else "nichts"
        print(f"[{i}] {zeichen} soll={'Fund' if soll else 'nichts':6} ist={was}")
    print(f"\n{len(BLOCKS) - fehler}/{len(BLOCKS)} richtig")


if __name__ == "__main__":
    main()
