"""Bestandsaufnahme: welche Dateien im Speicher hat die Datenbank vergessen.

Das regulaere Aufraeumen geht immer von der Datenbank aus. Es fragt, welche
Eintraege abgelaufen sind, und loescht deren Dateien. Eine Datei, deren Zeile es
nicht mehr gibt, kann es also nie finden. Fuer ``users/`` gibt es auch keine
Regel im Speicher, die nach Zeit aufraeumt, die greift nur fuer ``tmp/`` und
``backups/``.

Entstanden sind solche Reste vor allem so: bis zum Praefix-Loeschen entfernte
das Loeschen einer Quelle nur die Hauptdatei, Transkript und Untertitel blieben
liegen. Neu entstehen kann das nicht mehr, was liegt bleibt aber liegen.

Die Einordnung hier ist bewusst vorsichtig. Alles, was nicht eindeutig zum
bekannten Schema gehoert, landet unter ``unbekannt`` statt unter einer Art, die
zum Loeschen freigegeben wuerde.
"""

import re
from dataclasses import dataclass, field

# users/{user_id}/jobs/{job_uuid}/...
_JOB = re.compile(r"^(users/\d+/jobs/[^/]+)/.+$")
# users/{user_id}/aia/workspaces/{workspace_uuid}/...
_WORKSPACE = re.compile(r"^(users/\d+/aia/workspaces/[^/]+)/(.+)$")

# Bereiche mit eigener Aufbewahrungsregel im Speicher. Die raeumt der Bucket
# selbst nach Zeit auf, eine Bestandsaufnahme hat dort nichts zu suchen.
_FREMDE_BEREICHE = ("tmp/", "backups/")


@dataclass
class Bestand:
    """Was die Datenbank kennt, als Schluessel-Praefixe.

    ``quell_basen`` ist nach Workspace-Praefix gruppiert. Damit bleibt die
    Pruefung je Datei auf die Quellen eines Workspace beschraenkt, das sind
    hoechstens ein paar Dutzend.
    """

    job_praefixe: set[str] = field(default_factory=set)
    workspace_praefixe: set[str] = field(default_factory=set)
    quell_basen: dict[str, set[str]] = field(default_factory=dict)


def als_schluessel(pfad: str, wurzel: str = "") -> str:
    """Absoluten Pfad auf die Schluesselform bringen.

    Ohne S3 stehen in der Datenbank und im Speicher absolute Pfade, mit S3
    relative Schluessel. Beide Seiten muessen dieselbe Form haben, sonst faende
    die Pruefung alles verwaist.
    """
    if wurzel and pfad.startswith(wurzel):
        return pfad[len(wurzel):]
    return pfad


def _art(schluessel: str, bestand: Bestand) -> str | None:
    """Art des Fundes, oder None wenn die Datei einen Eintrag hat."""
    if schluessel.startswith(_FREMDE_BEREICHE):
        return None

    treffer = _JOB.match(schluessel)
    if treffer:
        return None if treffer.group(1) in bestand.job_praefixe else "job"

    treffer = _WORKSPACE.match(schluessel)
    if not treffer:
        # Nicht im bekannten Schema. Kann Absicht sein, kann ein Rest sein.
        # Melden, aber nie als verwaist einordnen.
        return "unbekannt"

    workspace, rest = treffer.group(1), treffer.group(2)
    if workspace not in bestand.workspace_praefixe:
        return "workspace"
    if not rest.startswith("sources/"):
        # Zum Beispiel das nie benutzte outputs/. Wer das anlegt, weiss es
        # besser als diese Pruefung.
        return "unbekannt"

    basen = bestand.quell_basen.get(workspace, set())
    if any(schluessel.startswith(basis) for basis in basen):
        return None
    return "quelle"


def finde_verwaiste(
    schluessel: list[str], bestand: Bestand, wurzel: str = ""
) -> dict[str, list[str]]:
    """Ordnet jede Datei ein. Liefert nur die Arten, zu denen es Funde gibt.

    Die Listen sind sortiert, damit zwei Laeufe dasselbe melden und sich zwei
    Berichte vergleichen lassen.
    """
    funde: dict[str, list[str]] = {}
    for pfad in schluessel:
        art = _art(als_schluessel(pfad, wurzel), bestand)
        if art:
            funde.setdefault(art, []).append(pfad)
    return {art: sorted(pfade) for art, pfade in sorted(funde.items())}


def trenne_nach_alter(
    pfade: list[str],
    alter_lesen,
    mindest_stunden: float,
    jetzt: float,
) -> tuple[list[str], list[str]]:
    """Teilt in (alt genug, zu frisch). ``alter_lesen`` liefert einen Unix-Zeitstempel.

    Ein laufender Upload hat seine Datei schon abgelegt, aber die Zeile in der
    Datenbank noch nicht geschrieben. Ohne diese Schranke wuerde ein Aufraeumen
    zum falschen Zeitpunkt genau diese Datei treffen.

    Ist der Zeitstempel nicht lesbar, gilt die Datei als zu frisch. Im Zweifel
    nicht loeschen.
    """
    if mindest_stunden <= 0:
        return list(pfade), []
    grenze = jetzt - mindest_stunden * 3600
    alt, frisch = [], []
    for pfad in pfade:
        stempel = alter_lesen(pfad)
        (alt if stempel is not None and stempel <= grenze else frisch).append(pfad)
    return alt, frisch


def zusammenfassen(verwaiste: dict[str, list[str]]) -> dict[str, int]:
    """Anzahl je Art plus Gesamtzahl."""
    zahlen = {art: len(pfade) for art, pfade in verwaiste.items()}
    zahlen["gesamt"] = sum(zahlen.values())
    return zahlen


# --- Datenbank-Seite ---


def bestand_aus_datenbank() -> Bestand:
    """Liest, welche Jobs, Workspaces und Quellen es noch gibt.

    Nur Lesezugriffe. Die Quellen kommen ueber ihren gespeicherten ``file_path``
    herein, nicht ueber eine selbst gebaute Kennung: was die Quelle besitzt,
    steht in der Spalte, und genau die benutzt auch das Loeschen.
    """
    from src.database import get_connection
    from src.storage import STORAGE_ROOT, USE_S3, aia_source_base, aia_workspace_prefix, job_prefix

    wurzel = "" if USE_S3 else f"{STORAGE_ROOT}/"
    bestand = Bestand()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, job_uuid FROM jobs")
            bestand.job_praefixe = {job_prefix(uid, uuid) for uid, uuid in cur.fetchall()}

            cur.execute("SELECT id, user_id, uuid FROM aia_workspaces")
            workspaces = cur.fetchall()
            nach_id = {ws_id: aia_workspace_prefix(uid, uuid) for ws_id, uid, uuid in workspaces}
            bestand.workspace_praefixe = set(nach_id.values())

            cur.execute("SELECT workspace_id, file_path FROM aia_sources")
            for ws_id, file_path in cur.fetchall():
                praefix = nach_id.get(ws_id)
                if not praefix or not file_path:
                    continue
                basis = als_schluessel(aia_source_base(file_path), wurzel)
                bestand.quell_basen.setdefault(praefix, set()).add(basis)
    return bestand
