"""Die Wortzerlegung der Lernkarte nachrechnen.

Der Prompt erklaert dem Modell ausfuehrlich, was ein Wortteil ist und was nicht. Trotzdem
kam "Einstieg" als "einsteigen + leg" heraus, mit "der leg = Endung fuer den Vorgang"
darunter. Ein Prompt ist eine Bitte, und bei Temperatur 0,6 wird eine Bitte manchmal
ueberhoert. Hier steht die Rechnung, die danach kommt.

Die Rechnung kennt keine deutschen Wortlisten und keine Endungstabelle, sie vergleicht
nur Buchstaben: jeder genannte Teil muss im Begriff selbst wiederzufinden sein. Das gilt
in jeder Sprache gleich.

Verglichen wird nicht der ganze Teil, sondern sein Anfang, denn die Grundform weicht vom
Stueck im Wort ab: "Hilfsverb" wird zu "Hilfe + Verb", "Passivsaetze" zu "Passiv + Satz".
Der Anfang haelt diese Faelle aus und faellt trotzdem bei "leg" in "Einstieg" durch.

Im Zweifel fliegt die ganze Zerlegung raus. Eine Karte ohne den Kasten ist vollstaendig
brauchbar, eine Karte mit einem erfundenen Wortteil lehrt etwas Falsches.
"""

import unicodedata

# Anteil des Teils, der im Begriff stehen muss, und die Untergrenze in Zeichen. 60 Prozent
# laesst die Grundform atmen ("Satz" zu "Saetze" wird ueber "sat" gefunden) und stoppt
# trotzdem den Ablaut, der aus "steigen" ein "stieg" macht. Die Untergrenze verhindert,
# dass ein sehr kurzer Teil ueber einen einzigen Buchstaben durchrutscht.
_MIN_ANTEIL = 0.6
_MIN_ZEICHEN = 3


def _fold(text: str) -> str:
    """Nur die nackten Buchstaben: klein, ohne Umlautpunkte, ohne Fugenstriche."""
    # casefold zuerst, damit aus dem scharfen s ein doppeltes s wird; NFKD trennt danach
    # die Umlautpunkte ab, die dann als kombinierende Zeichen wegfallen.
    zerlegt = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in zerlegt if c.isalnum() and not unicodedata.combining(c))


def _steckt_im_begriff(begriff: str, teil: str) -> bool:
    laenge = max(_MIN_ZEICHEN, round(len(teil) * _MIN_ANTEIL))
    return bool(teil) and teil[:min(len(teil), laenge)] in begriff


def clean_word_parts(begriff: str, word_parts: str, word_parts_explained: str) -> tuple[str, str]:
    """Gibt (word_parts, word_parts_explained) zurueck, beides leer, wenn es nicht traegt.

    Die Erklaerung darf allein wegfallen: die Teile stimmen dann noch, nur die Zeilen
    darunter passen nicht zu ihnen.
    """
    teile = [t.strip() for t in (word_parts or "").split("+")]
    teile = [t for t in teile if t]
    # Ein einzelner Teil ist keine Zerlegung, sondern das Wort selbst.
    if len(teile) < 2:
        return "", ""

    gefaltet = _fold(begriff)
    if not all(_steckt_im_begriff(gefaltet, _fold(t)) for t in teile):
        return "", ""

    erklaerung = (word_parts_explained or "").strip()
    # Die Ansicht liest die Zeilen an "|" und das Wort davor an "=". Genauso wird hier
    # geprueft, damit die Pruefung dasselbe sieht wie der Lernende.
    zeilen = [z.strip() for z in erklaerung.split("|")] if erklaerung else []
    zeilen = [z for z in zeilen if z]
    passt = len(zeilen) == len(teile) and all(
        _fold(t) in _fold(z.split("=", 1)[0]) for t, z in zip(teile, zeilen)
    )
    return " + ".join(teile), (erklaerung if passt else "")
