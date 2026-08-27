"""Finds stored files that no longer have a database row."""
import argparse
import sys
import time
from pathlib import Path

# Make 'src.*' importable no matter where this is called from.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from src import storage
from src.services import storage_audit

# Kinds with an unambiguous mapping, only those may be deleted.
_LOESCHBAR = ("job", "workspace", "quelle")

_BESCHREIBUNG = {
    "job": "Job-Dateien ohne Eintrag in der Tabelle jobs",
    "workspace": "Dateien eines Workspace, den es nicht mehr gibt",
    "quelle": "Transkripte und Untertitel ohne die Quelle dazu",
    "unbekannt": "passt nicht ins bekannte Schema, wird NICHT geloescht",
}


def _kopf(pfad: str) -> dict:
    """Size and mtime of a stored file, empty when it cannot be read."""
    try:
        if storage.USE_S3:
            from src.storage import _S3_BUCKET, _s3  # type: ignore[attr-defined]
            antwort = _s3().head_object(Bucket=_S3_BUCKET, Key=pfad)
            return {
                "groesse": antwort["ContentLength"],
                "stempel": antwort["LastModified"].timestamp(),
            }
        stat = Path(pfad).stat()
        return {"groesse": stat.st_size, "stempel": stat.st_mtime}
    except Exception:
        return {}


def _lesbar(bytes_: int) -> str:
    wert = float(bytes_)
    for einheit in ("B", "KB", "MB", "GB"):
        if wert < 1024 or einheit == "GB":
            return f"{wert:.1f} {einheit}"
        wert /= 1024
    return f"{wert:.1f} GB"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Findet Dateien im Speicher, zu denen es keinen Eintrag mehr gibt.",
    )
    ap.add_argument("--delete", action="store_true",
                    help="wirklich loeschen (ohne dieses Flag wird nur gemeldet)")
    ap.add_argument("--full", action="store_true", help="alle Pfade ausgeben, nicht nur eine Probe")
    ap.add_argument("--size", action="store_true",
                    help="Groesse ermitteln (eine Abfrage je Datei, bei entferntem Speicher langsam)")
    ap.add_argument("--min-age-hours", type=float, default=24.0,
                    help="Dateien juenger als das nie loeschen (Vorgabe 24, schuetzt laufende Uploads)")
    args = ap.parse_args()

    modus = "S3" if storage.USE_S3 else f"lokal ({storage.STORAGE_ROOT})"
    wurzel = "" if storage.USE_S3 else f"{storage.STORAGE_ROOT}/"
    print(f"Speicher: {modus}")

    print("Lese Bestand aus der Datenbank ...")
    bestand = storage_audit.bestand_aus_datenbank()
    print(f"  {len(bestand.job_praefixe)} Jobs, {len(bestand.workspace_praefixe)} Workspaces, "
          f"{sum(len(b) for b in bestand.quell_basen.values())} Quellen")

    print("Liste den Speicher unter users/ ...")
    schluessel = storage.list_keys("users/")
    print(f"  {len(schluessel)} Dateien")

    verwaist = storage_audit.finde_verwaiste(schluessel, bestand, wurzel=wurzel)
    zahlen = storage_audit.zusammenfassen(verwaist)

    if not verwaist:
        print("\nNichts verwaist. Jede Datei hat einen Eintrag.")
        return 0

    print(f"\nOhne Eintrag: {zahlen['gesamt']} von {len(schluessel)} Dateien")
    for art, pfade in verwaist.items():
        zeile = f"  {art:<11} {len(pfade):>6}  {_BESCHREIBUNG[art]}"
        if args.size:
            zeile += f"  [{_lesbar(sum(_kopf(p).get('groesse', 0) for p in pfade))}]"
        print(zeile)
        for pfad in (pfade if args.full else pfade[:5]):
            print(f"      {pfad}")
        if not args.full and len(pfade) > 5:
            print(f"      ... und {len(pfade) - 5} weitere (--full zeigt alle)")

    if not args.delete:
        print("\nNur gemeldet, nichts geloescht. Mit --delete wirklich loeschen.")
        return 0

    kandidaten = [p for art in _LOESCHBAR for p in verwaist.get(art, [])]
    zu_loeschen, zu_frisch = storage_audit.trenne_nach_alter(
        kandidaten,
        lambda p: _kopf(p).get("stempel"),
        mindest_stunden=args.min_age_hours,
        jetzt=time.time(),
    )
    uebersprungen = len(verwaist.get("unbekannt", []))
    print(f"\nLoesche {len(zu_loeschen)} Dateien ...")
    if uebersprungen:
        print(f"  {uebersprungen} unter 'unbekannt' bleiben liegen, die ordnet dieses Skript nicht ein.")
    if zu_frisch:
        print(f"  {len(zu_frisch)} sind juenger als {args.min_age_hours} h und bleiben liegen "
              f"(koennten laufende Uploads sein).")

    geloescht, fehler = 0, 0
    for pfad in zu_loeschen:
        try:
            storage.delete_file(pfad)
            geloescht += 1
        except Exception as e:
            fehler += 1
            print(f"  FEHLER bei {pfad}: {e}")
    print(f"Fertig: {geloescht} geloescht, {fehler} Fehler.")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
