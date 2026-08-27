"""Finds files in storage the database forgot, classified carefully."""

import re
from dataclasses import dataclass, field

# users/{user_id}/jobs/{job_uuid}/...
_JOB = re.compile(r"^(users/\d+/jobs/[^/]+)/.+$")
# users/{user_id}/aia/workspaces/{workspace_uuid}/...
_WORKSPACE = re.compile(r"^(users/\d+/aia/workspaces/[^/]+)/(.+)$")

# Areas with their own retention rule stay out.
_FREMDE_BEREICHE = ("tmp/", "backups/", "aia/speech/")


@dataclass
class Bestand:
    """What the database knows, as key prefixes."""

    job_praefixe: set[str] = field(default_factory=set)
    workspace_praefixe: set[str] = field(default_factory=set)
    quell_basen: dict[str, set[str]] = field(default_factory=dict)


def als_schluessel(pfad: str, wurzel: str = "") -> str:
    """Brings an absolute path into key form."""
    if wurzel and pfad.startswith(wurzel):
        return pfad[len(wurzel):]
    return pfad


def _art(schluessel: str, bestand: Bestand) -> str | None:
    """Kind of finding, or None when the file has a database row."""
    if schluessel.startswith(_FREMDE_BEREICHE):
        return None

    treffer = _JOB.match(schluessel)
    if treffer:
        return None if treffer.group(1) in bestand.job_praefixe else "job"

    treffer = _WORKSPACE.match(schluessel)
    if not treffer:
        # Not in the known scheme: report it, but never classify it as orphaned.
        return "unbekannt"

    workspace, rest = treffer.group(1), treffer.group(2)
    if workspace not in bestand.workspace_praefixe:
        return "workspace"
    if not rest.startswith("sources/"):
        # Whoever creates something like this knows better than this check.
        return "unbekannt"

    basen = bestand.quell_basen.get(workspace, set())
    if any(schluessel.startswith(basis) for basis in basen):
        return None
    return "quelle"


def finde_verwaiste(
    schluessel: list[str], bestand: Bestand, wurzel: str = ""
) -> dict[str, list[str]]:
    """Classifies every file and returns only the kinds with findings."""
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
    """Splits into old enough and too fresh, too fresh when in doubt."""
    if mindest_stunden <= 0:
        return list(pfade), []
    grenze = jetzt - mindest_stunden * 3600
    alt, frisch = [], []
    for pfad in pfade:
        stempel = alter_lesen(pfad)
        (alt if stempel is not None and stempel <= grenze else frisch).append(pfad)
    return alt, frisch


def zusammenfassen(verwaiste: dict[str, list[str]]) -> dict[str, int]:
    """Count per kind plus the total."""
    zahlen = {art: len(pfade) for art, pfade in verwaiste.items()}
    zahlen["gesamt"] = sum(zahlen.values())
    return zahlen


# --- database side ---


def bestand_aus_datenbank() -> Bestand:
    """Reads which jobs, course rooms and sources still exist."""
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
