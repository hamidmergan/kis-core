"""Builds the screencast demo through the real tool, safe to run again.

    python3 backend/scripts/screencast_demo_bauen.py --pptx Projektstart.pptx --vergleich-pptx kurz.pptx \
        [--sprache en] [--nur gemini] [--neu] [--geduldig]

Reads demo/screencast/stimmen.json and fills demo/screencast/<sprache>/: the run of --pptx with the
first voice of the list, and in vergleich/ the shorter --vergleich-pptx voiced by every service.
The decks of the first language are voiced as they are, every other language is translated by the
tool first. Existing videos stay, so a run after a failed service only fills the gap. With
--geduldig a run stopped by a quota is resumed every 15 minutes until it is through. Needs the
backend on localhost:8000 and ADMIN_PASSWORD in .env, the own voice services must belong to the admin.
"""

import argparse
import base64
import http.client
import http.cookiejar
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[2]
DEMO_DIR = WURZEL / "backend" / "demo" / "screencast"
BACKEND = "http://localhost:8000"
ZIELSPRACHE = {"de": "DE", "en": "EN-US"}
FERTIG = ("success", "failed", "cancelled", "paused")
NEUER_ANLAUF_S = 900
# A restarted backend is back within minutes, a run that waits for a quota must outlast that.
VERBINDUNG_VERSUCHE = 60
VERBINDUNG_PAUSE_S = 30


class Api:
    def __init__(self):
        self._op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        passwort = re.search(r"^ADMIN_PASSWORD=(.*)$", (WURZEL / ".env").read_text(), re.M).group(1).strip("\"'")
        self.json("/auth/login", {"username": "admin", "password": passwort})

    def roh(self, pfad: str, daten: bytes | None = None, typ: str = "application/json", methode: str | None = None) -> bytes:
        anfrage = urllib.request.Request(BACKEND + pfad, data=daten, headers={"Content-Type": typ} if daten else {},
                                         method=methode)
        for versuch in range(VERBINDUNG_VERSUCHE):
            try:
                with self._op.open(anfrage, timeout=600) as antwort:
                    return antwort.read()
            except urllib.error.HTTPError as e:
                if e.code != 502 and e.code != 503:
                    raise RuntimeError(f"{pfad}: HTTP {e.code} {e.read()[:300]!r}") from None
            except (urllib.error.URLError, http.client.HTTPException, ConnectionError, TimeoutError):
                pass
            print(f"Backend nicht erreichbar ({pfad}), neuer Versuch in {VERBINDUNG_PAUSE_S} s", flush=True)
            time.sleep(VERBINDUNG_PAUSE_S)
        raise RuntimeError(f"{pfad}: Backend nicht erreichbar")

    def json(self, pfad: str, body: dict | None = None):
        return json.loads(self.roh(pfad, json.dumps(body).encode() if body is not None else None))

    def formular(self, pfad: str, datei: Path, felder: dict[str, str]) -> dict:
        grenze = "----demo" + str(time.time_ns())
        teile = [f'--{grenze}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in felder.items()]
        teile.append(f'--{grenze}\r\nContent-Disposition: form-data; name="file"; filename="{datei.name}"\r\n'
                     "Content-Type: application/octet-stream\r\n\r\n".encode() + datei.read_bytes() + b"\r\n")
        teile.append(f"--{grenze}--\r\n".encode())
        return json.loads(self.roh(pfad, b"".join(teile), f"multipart/form-data; boundary={grenze}"))

    def warten(self, job: str) -> dict:
        while True:
            time.sleep(5)
            stand = self.json(f"/jobs/{job}")
            if stand["status"] in FERTIG or (stand["status"] == "awaiting_user" and stand.get("result")):
                return stand


def _anbieter(api: Api) -> dict[str, int]:
    """Provider ids by name, the ids differ between machines."""
    return {p["name"]: p["id"] for p in api.json("/tts/providers-with-voices")["providers"]}


def _folien_schreiben(ordner: Path, texte: list[str], bilder: list[str]) -> None:
    (ordner / "folien").mkdir(parents=True, exist_ok=True)
    (ordner / "folientexte.json").write_text(json.dumps(texte, ensure_ascii=False, indent=2), encoding="utf-8")
    for i, bild in enumerate(bilder):
        (ordner / "folien" / f"folie_{i:03d}.png").write_bytes(base64.b64decode(bild))


def vorbereiten(api: Api, pptx: Path, sprache: str, erste: str, ordner: Path, neu: bool,
                mit_folien: bool) -> tuple[str, list[str]]:
    """A job with the deck of the language, plus its scripts. A stored deck is reused as it is."""
    gespeichert = ordner / pptx.name
    if gespeichert.exists() and (ordner / "accepted_scripts.json").exists() and not neu:
        job = api.formular("/screencast/upload-corrected", gespeichert, {})["translate_job_uuid"]
        return job, json.loads((ordner / "accepted_scripts.json").read_text(encoding="utf-8"))

    ordner.mkdir(parents=True, exist_ok=True)
    if sprache == erste:
        antwort = api.formular("/screencast/upload-corrected", pptx, {})
        job, texte, bilder = antwort["translate_job_uuid"], antwort["slide_texts"], antwort["slide_images"]
    else:
        uebersetzer = api.json("/translate/config")["providers"][0]["id"]
        job = api.formular("/screencast/translate", pptx, {"source_lang": "", "target_lang": ZIELSPRACHE[sprache],
                                                           "provider_id": str(uebersetzer)})["job_uuid"]
        ergebnis = api.warten(job).get("result") or {}
        texte, bilder = ergebnis["slide_texts"], ergebnis["slide_images"]
    if mit_folien:
        _folien_schreiben(ordner, texte, bilder)
    gespeichert.write_bytes(api.roh(f"/screencast/pptx/{job}"))
    skripte = api.json(f"/screencast/{job}/notizen")["notes"]
    (ordner / "accepted_scripts.json").write_text(json.dumps(skripte, ensure_ascii=False, indent=2), encoding="utf-8")
    return job, skripte


def vertonen(api: Api, job: str, skripte: list[str], sprache: str, stimme: dict, anbieter_id: int,
             video: Path, ton: Path | None, geduldig: bool = False) -> None:
    """One run with one voice, its video and, when asked, its audio per slide."""
    wahl = stimme["sprachen"][sprache]
    api.json("/screencast/render", {
        "scripts": skripte, "translate_job_uuid": job, "target_lang": ZIELSPRACHE[sprache],
        "voice_id": wahl["stimme"], "voice_label": wahl["name"], "slide_pause": 1.0, "dpi": 96,
        "provider_id": anbieter_id, "subtitles": False, "neu_vertonen": list(range(len(skripte))),
    })
    stand = api.warten(job)
    # The job keeps the slides it already voiced, a new attempt only asks for the rest.
    while geduldig and stand["status"] in ("failed", "paused"):
        print(f"{sprache} {stimme['id']}: {stand['status']}, neuer Anlauf in {NEUER_ANLAUF_S // 60} min", flush=True)
        time.sleep(NEUER_ANLAUF_S)
        api.roh(f"/jobs/{job}/retry", b"{}")
        stand = api.warten(job)
    if stand["status"] != "success":
        raise RuntimeError(f"Lauf {stand['status']}: {stand.get('error') or stand.get('error_message')}")
    if ton is not None:
        ton.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(api.roh(f"/screencast/audio/{job}/zip"))) as zf:
            for name in zf.namelist():
                nummer = re.search(r"(\d+)\.mp3$", name)
                if nummer:
                    (ton / f"folie_{int(nummer.group(1)):03d}.mp3").write_bytes(zf.read(name))
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(api.roh(f"/jobs/{job}/video"))


def _lauf(api: Api, namen: dict[str, int], job: str, skripte: list[str], sprache: str, stimme: dict,
          video: Path, ton: Path | None, geduldig: bool = False) -> bool:
    name = stimme["sprachen"][sprache]["anbieter"]
    try:
        if name not in namen:
            raise RuntimeError(f"Anbieter {name} fehlt")
        vertonen(api, job, skripte, sprache, stimme, namen[name], video, ton, geduldig)
        print(f"{sprache} {video.relative_to(DEMO_DIR)}: fertig", flush=True)
        return True
    except RuntimeError as e:
        print(f"{sprache} {video.relative_to(DEMO_DIR)}: {e}", file=sys.stderr, flush=True)
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pptx", type=Path, required=True, help="Foliensatz mit Sprechnotizen in der ersten Sprache")
    parser.add_argument("--vergleich-pptx", type=Path, required=True, help="derselbe Satz mit kurzen Notizen")
    parser.add_argument("--sprache", action="append", help="nur diese Sprachen, sonst alle aus stimmen.json")
    parser.add_argument("--nur", action="append", help="nur diese Stimmdienste im Vergleich (id aus stimmen.json)")
    parser.add_argument("--neu", action="store_true", help="Folien, Skripte und Videos neu erzeugen")
    parser.add_argument("--geduldig", action="store_true", help="bei Kontingentgrenzen warten statt aufgeben")
    args = parser.parse_args()

    stimmen = json.loads((DEMO_DIR / "stimmen.json").read_text(encoding="utf-8"))
    alle = list(dict.fromkeys(s for st in stimmen for s in st["sprachen"]))
    api = Api()
    namen = _anbieter(api)
    luecken = 0
    for sprache in args.sprache or alle:
        ordner = DEMO_DIR / sprache
        if args.neu or not (ordner / "video.mp4").exists():
            job, skripte = vorbereiten(api, args.pptx, sprache, alle[0], ordner, args.neu, True)
            luecken += not _lauf(api, namen, job, skripte, sprache, stimmen[0], ordner / "video.mp4", ordner / "ton")
            # The helper job would otherwise stay in the admin's history.
            api.roh(f"/jobs/{job}", methode="DELETE")

        vergleich = ordner / "vergleich"
        offen = [s for s in stimmen if (not args.nur or s["id"] in args.nur)
                 and sprache in s.get("vergleich", alle)
                 and (args.neu or not (vergleich / f"{s['id']}.mp4").exists())]
        if not offen:
            continue
        job, skripte = vorbereiten(api, args.vergleich_pptx, sprache, alle[0], vergleich, args.neu, False)
        for stimme in offen:
            luecken += not _lauf(api, namen, job, skripte, sprache, stimme, vergleich / f"{stimme['id']}.mp4", None,
                                 args.geduldig)
        api.roh(f"/jobs/{job}", methode="DELETE")
    return 1 if luecken else 0


if __name__ == "__main__":
    sys.exit(main())
