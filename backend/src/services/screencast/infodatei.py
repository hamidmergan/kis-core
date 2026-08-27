"""The info file in the ZIP: what is inside and what it was made with."""

from pathlib import Path

from src.i18n import t

# Lowercase and without an umlaut, because the word ends up in the file name.
_SPRACH_WORTE = {
    "DE": "deutsch",
    "EN-US": "englisch",
    "EN-GB": "englisch",
    "EN": "englisch",
    "FR": "franzoesisch",
    "ES": "spanisch",
    "IT": "italienisch",
    "TR": "tuerkisch",
    "AR": "arabisch",
    "RU": "russisch",
}


def sprach_wort(lang_code: str) -> str:
    """The word for the file name of the translated slides."""
    return _SPRACH_WORTE.get((lang_code or "").upper(), "uebersetzt")


def sprach_name(lang_code: str) -> str:
    """The language spelled out, empty when the code is unknown."""
    if not lang_code:
        return ""
    schluessel = f"lang.{lang_code.upper()}"
    name = t(schluessel, "de")
    return "" if name == schluessel else name


def dauer_text(sekunden: float) -> str:
    """A duration the way you would say it out loud."""
    gesamt = round(sekunden or 0)
    if gesamt < 60:
        return f"{gesamt} s"
    if gesamt < 3600:
        return f"{gesamt // 60} min {gesamt % 60} s"
    return f"{gesamt // 3600} h {(gesamt % 3600) // 60} min"


def _zahl(wert) -> str:
    """Thousands separator as in German."""
    return f"{int(wert):,}".replace(",", ".")


def _komma(wert) -> str:
    """One decimal place with a comma instead of a period."""
    return f"{float(wert):.1f}".replace(".", ",")


def _zeitpunkt(job: dict) -> str:
    wert = job.get("completed_at") or job.get("created_at")
    if not hasattr(wert, "strftime"):
        return ""
    return wert.strftime("%d.%m.%Y, %H:%M Uhr")


def _folienzahl(stats: dict, meta: dict):
    for phase in ("vertonung", "bilder", "uebersetzung"):
        zahl = (stats.get(phase) or {}).get("folien")
        if zahl:
            return zahl
    return meta.get("audio_count")


def _sprachzeile(stats: dict, meta: dict) -> str:
    uebersetzung = stats.get("uebersetzung") or {}
    quelle = sprach_name(uebersetzung.get("quelle", ""))
    ziel = sprach_name(uebersetzung.get("ziel", "") or meta.get("target_lang", ""))
    if quelle and ziel:
        return f"Sprache: {quelle} nach {ziel}"
    return f"Sprache: {ziel}" if ziel else ""


def _anbieterzeile(beschriftung: str, phase: dict) -> str:
    anbieter = phase.get("anbieter") or ""
    if not anbieter:
        return ""
    modell = phase.get("modell") or ""
    return f"{beschriftung}: {anbieter}, Modell {modell}" if modell else f"{beschriftung}: {anbieter}"


# Order and labels of the measured sections.
_PHASEN = (
    ("skripte", "Sprechtexte"),
    ("uebersetzung", "Übersetzung"),
    ("bilder", "Folienbilder"),
    ("vertonung", "Vertonung"),
    ("clips", "Videoschnitt"),
    ("untertitel", "Untertitel"),
    ("zusammenfuegen", "Zusammenfügen"),
)


def _technikteil(stats: dict) -> list[str]:
    """Providers and models per step, for admins only."""
    zeilen = ["", "--- Technik ---"]
    for schluessel, beschriftung in (
        ("skripte", "Sprechtexte"), ("uebersetzung", "Übersetzung"), ("vertonung", "Vertonung"),
    ):
        zeile = _anbieterzeile(beschriftung, stats.get(schluessel) or {})
        if zeile:
            zeilen.append(zeile)

    dpi = (stats.get("bilder") or {}).get("dpi")
    if dpi:
        zeilen.append(f"Auflösung: {dpi} dpi")

    fehler = [f"{b}: {(stats.get(k) or {})['fehler']}" for k, b in _PHASEN if (stats.get(k) or {}).get("fehler")]
    if fehler:
        zeilen.extend(["", "Abgebrochen bei:", *fehler])
    return zeilen


def baue_info(job: dict, meta: dict, *, mit_technik: bool = False) -> str:
    """The text of the info file, without ``mit_technik`` providers and models stay out."""
    stats = meta.get("stats") or {}
    zeilen = [f"Screencast: {Path(job.get('original_filename') or 'screencast').stem}"]

    zeitpunkt = _zeitpunkt(job)
    if zeitpunkt:
        zeilen.append(f"Erstellt am: {zeitpunkt}")
    zeilen.append("")

    folien = _folienzahl(stats, meta)
    if folien:
        zeilen.append(f"Folien: {_zahl(folien)}")

    zeichen = (stats.get("vertonung") or {}).get("zeichen")
    if zeichen:
        zeilen.append(f"Zeichen im Sprechtext: {_zahl(zeichen)}")

    sprachzeile = _sprachzeile(stats, meta)
    if sprachzeile:
        zeilen.append(sprachzeile)

    vertonung = stats.get("vertonung") or {}
    stimme = vertonung.get("stimme_name") or vertonung.get("stimme")
    if stimme:
        zeilen.append(f"Stimme: {stimme}")
    if vertonung.get("tempo") is not None:
        zeilen.append(f"Tempo: {_komma(vertonung['tempo'])}")

    pause = (stats.get("clips") or {}).get("folienpause")
    if pause is not None:
        zeilen.append(f"Pause zwischen Folien: {_komma(pause)} Sekunden")

    zeilen.append(f"Untertitel: {'ja' if meta.get('subtitles') else 'nein'}")

    if mit_technik and stats:
        zeilen.extend(_technikteil(stats))

    return "\n".join(zeilen) + "\n"
