"""Der Vorrat für gesprochene Beispielsätze.

Ein Satz kostet vier bis fünf Sekunden beim Anbieter. Ohne Vorrat zahlt jede Person
in einem Kurs diesen Preis erneut, und dieselbe Person nach jedem Neuladen der Seite
noch einmal. Das ist die teuerste Art, immer dasselbe zu bekommen.

Der Vorrat gilt fuer ALLE. Am Ton ist nichts persoenlich: er ist eine reine Funktion
aus Satz, Anbieter, Stimme und Tempo, und der Satz steht ohnehin im gemeinsamen
Kursmaterial. Ein Vorrat je Person wuerde denselben Satz in einem Kurs mit dreissig
Leuten dreissigmal erzeugen, also genau die Verschwendung, gegen die er gebaut ist.

Der Schluessel ist der SATZ, nicht das Wort und nicht die Karte. Zwei Karten mit
demselben Beispielsatz teilen sich einen Ton, und ein neu erzeugter Kartensatz greift
auf das zu, was ein alter schon gesprochen hat. Haengte der Vorrat an der Kartennummer,
waere er nach jeder Neuerzeugung leer.

Wie der Aufgaben-Vorrat waechst er als Nebenprodukt der Nutzung. Es gibt keinen
Bau-Auftrag und keinen Knopf: was niemand anhoert, entsteht auch nicht.
"""

import hashlib

import psycopg2

from src.core.db.pool import get_connection

# Wie lange ein ungehoerter Ton liegen bleibt. Wer ihn danach doch braucht, wartet
# einmal fuenf Sekunden und hat ihn wieder. Bewusst keine Admin-Einstellung: die Zahl
# laesst sich weder messen noch sinnvoll erraten, und ein Regler mehr hilft niemandem.
SPEECH_CACHE_RETENTION_DAYS = 90


def normalize_sentence(sentence: str) -> str:
    """Den Satz so zurechtlegen, wie er auch beim Anbieter ankommt.

    Der Sprachclient faltet Zeilenumbrueche und Randleerzeichen ohnehin zusammen. Wird
    hier anders normalisiert als dort, bekommen zwei Saetze, die identisch gesprochen
    werden, verschiedene Fingerabdruecke, und der Vorrat greift nie.
    """
    return " ".join(line.strip() for line in (sentence or "").splitlines() if line.strip())


def fingerprint(sentence: str, provider_id: int, voice_id: str, speed: float,
                model: str = "") -> str:
    """Der Schluessel eines Tons.

    Alles, was den Klang aendert, geht ein. Stimme und Anbieter, weil derselbe Satz
    mit einer anderen Stimme ein anderer Ton ist, und das Tempo aus demselben Grund.

    Das MODELL gehoert ebenfalls dazu, obwohl es nicht am Anbieter haengt, sondern in
    der Route "Text in Sprache" steht. Ohne es liefert der Vorrat nach einem
    Modellwechsel weiter den alten Klang, und nichts entwertet ihn, ausser dass ihn
    neunzig Tage niemand hoert.

    Die Teile werden durch ein Nullbyte getrennt, damit sich keine zwei verschiedenen
    Kombinationen zu derselben Zeichenkette zusammenschieben lassen.
    """
    roh = "\x00".join((
        normalize_sentence(sentence),
        str(provider_id),
        voice_id or "",
        f"{float(speed):.2f}",
        model or "",
    ))
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()


def get(key: str) -> bytes | None:
    """Den Ton zu einem Fingerabdruck holen, oder None.

    Der Zugriff frischt ``last_used_at`` auf, denn danach entscheidet das naechtliche
    Aufraeumen. Ein Satz, den ein Kurs jedes Semester wieder hoert, soll nicht
    verschwinden, nur weil er einmal drei Monate geruht hat.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE aia_speech_cache SET last_used_at = NOW()
                   WHERE fingerprint = %s
                   RETURNING audio""",
                (key,),
            )
            row = cur.fetchone()
        # Auch das Auffrischen des Zeitstempels ist ein Schreibvorgang. Ohne commit
        # rollt die Verbindung ihn beim Zurueckgeben in den Pool zurueck, und das
        # naechtliche Aufraeumen wuerde vielgehoerte Saetze wegwerfen.
        conn.commit()
    if not row or row[0] is None:
        return None
    return bytes(row[0])


def put(key: str, audio: bytes) -> None:
    """Einen Ton in den Vorrat legen.

    ``ON CONFLICT`` statt vorher nachzusehen: klicken zwei Lernende denselben Satz
    gleichzeitig, erzeugen beide, und der zweite Schreibvorgang darf daran nicht
    scheitern. Er frischt dann nur den Zeitstempel auf.
    """
    if not audio:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_speech_cache (fingerprint, audio, bytes)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (fingerprint) DO UPDATE SET last_used_at = NOW()""",
                (key, psycopg2.Binary(audio), len(audio)),
            )
        conn.commit()


def prune(days: int = SPEECH_CACHE_RETENTION_DAYS) -> int:
    """Toene loeschen, die so lange niemand gehoert hat. Liefert die Anzahl.

    Laeuft naechtlich als ``cleanup.speech_cache``.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM aia_speech_cache WHERE last_used_at < NOW() - %s::interval",
                (f"{int(days)} days",),
            )
            geloescht = cur.rowcount or 0
        conn.commit()
    return geloescht
