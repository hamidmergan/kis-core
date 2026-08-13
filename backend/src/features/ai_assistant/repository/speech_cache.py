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

DER TON LIEGT IM SPEICHER, die Zeile haelt nur die Nutzungsspur. MP3s in der Tabelle
haetten mit den Jahren jede Sicherung mitgeschleppt, und wiederhergestellt werden muss
an ihnen nichts: was fehlt, spricht der Anbieter neu. Die Zeile bleibt trotzdem, denn
nur sie weiss, wann ein Satz zuletzt gehoert wurde. Eine Aufbewahrungsregel im Bucket
kennt nur das Erstelldatum und wuerde den Satz wegwerfen, den ein Kurs jedes Semester
wieder hoert.

Zeile und Datei koennen auseinanderlaufen. Das ist eingeplant, und zwar immer in die
Richtung, aus der sich der Vorrat von selbst erholt: eine Zeile ohne Datei wird beim
naechsten Zugriff weggeraeumt und der Satz neu gesprochen.
"""

import hashlib

from src import storage
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

    Zuerst die Zeile, dann die Datei. Die Zeile ist die billigere Frage und beantwortet
    den haeufigsten Fehltreffer, einen Satz, den noch nie jemand gehoert hat, ohne einen
    Netzweg in den Speicher.

    Der Zugriff frischt ``last_used_at`` auf, denn danach entscheidet das naechtliche
    Aufraeumen. Ein Satz, den ein Kurs jedes Semester wieder hoert, soll nicht
    verschwinden, nur weil er einmal drei Monate geruht hat.

    Fehlt die Datei zur Zeile, wird die Zeile weggeraeumt und None geliefert: der
    Aufrufer spricht dann neu und legt beides wieder an. Ohne dieses Aufraeumen bliebe
    der Satz fuer immer stumm, weil die Zeile weiter einen Treffer meldet.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE aia_speech_cache SET last_used_at = NOW()
                   WHERE fingerprint = %s
                   RETURNING fingerprint""",
                (key,),
            )
            row = cur.fetchone()
        # Auch das Auffrischen des Zeitstempels ist ein Schreibvorgang. Ohne commit
        # rollt die Verbindung ihn beim Zurueckgeben in den Pool zurueck, und das
        # naechtliche Aufraeumen wuerde vielgehoerte Saetze wegwerfen.
        conn.commit()
    if not row:
        return None

    audio = storage.get_speech_audio(key)
    if audio is None:
        _vergessen(key)
        return None
    return audio


def _vergessen(key: str) -> None:
    """Eine Zeile loeschen, deren Datei es nicht mehr gibt."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM aia_speech_cache WHERE fingerprint = %s", (key,))
        conn.commit()


def put(key: str, audio: bytes) -> None:
    """Einen Ton in den Vorrat legen.

    Erst die Datei, dann die Zeile. Bricht es dazwischen ab, liegt eine Datei ohne
    Zeile herum, die der naechste Versuch unter demselben Schluessel einfach
    ueberschreibt. Andersherum entstuende eine Zeile ohne Datei, also ein Treffer, der
    nichts liefert.

    ``ON CONFLICT`` statt vorher nachzusehen: klicken zwei Lernende denselben Satz
    gleichzeitig, erzeugen beide, und der zweite Schreibvorgang darf daran nicht
    scheitern. Er frischt dann nur den Zeitstempel auf.
    """
    if not audio:
        return
    storage.save_speech_audio(key, audio)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_speech_cache (fingerprint, bytes)
                   VALUES (%s, %s)
                   ON CONFLICT (fingerprint) DO UPDATE SET last_used_at = NOW()""",
                (key, len(audio)),
            )
        conn.commit()


def prune(days: int = SPEECH_CACHE_RETENTION_DAYS) -> int:
    """Toene loeschen, die so lange niemand gehoert hat. Liefert die Anzahl.

    Laeuft naechtlich als ``cleanup.speech_cache``.

    Erst die Dateien, dann die Zeilen. Scheitert das Loeschen im Speicher, bleiben die
    Zeilen stehen und die naechste Nacht nimmt denselben Anlauf. Andersherum waere die
    Datei nach einem Abbruch fuer immer verwaist: ohne ihre Zeile weiss niemand mehr,
    dass es sie gibt.

    Die Verbindung wird zwischendurch zurueckgegeben. Der Speicher liegt entfernt, und
    eine Verbindung aus dem Pool waehrend eines Netzwegs festzuhalten kostet sie allen
    anderen.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT fingerprint FROM aia_speech_cache
                   WHERE last_used_at < NOW() - %s::interval""",
                (f"{int(days)} days",),
            )
            schluessel = [zeile[0] for zeile in cur.fetchall()]
    if not schluessel:
        return 0

    storage.delete_speech_audio(schluessel)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM aia_speech_cache WHERE fingerprint = ANY(%s)",
                (schluessel,),
            )
        conn.commit()
    return len(schluessel)
