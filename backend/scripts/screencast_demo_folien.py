"""Cuts the demo video into one image and one audio file per slide, safe to run again.

    python scripts/screencast_demo_folien.py [--demo-dir backend/demo] [--neu]
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"
BILD_BREITE = 960
_SZENE = re.compile(r"pts_time:([0-9.]+).*?\n.*?lavfi\.scene_score=([0-9.]+)")


def schnitte_waehlen(kandidaten: list[tuple[float, float]], anzahl: int) -> list[float]:
    """The strongest cuts, sorted by time."""
    staerkste = sorted(kandidaten, key=lambda k: k[1], reverse=True)[:anzahl]
    return sorted(zeit for zeit, _ in staerkste)


def abschnitte(schnitte: list[float], dauer: float) -> list[tuple[float, float]]:
    """Start and end of every slide between the cuts."""
    grenzen = [0.0, *schnitte, dauer]
    return list(zip(grenzen[:-1], grenzen[1:]))


def _ffmpeg(*args: str) -> str:
    return subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostdin", *args],
        check=True, capture_output=True, text=True,
    ).stderr


def _dauer(video: Path) -> float:
    ausgabe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
        check=True, capture_output=True, text=True,
    ).stdout
    return float(ausgabe.strip())


def _kandidaten(video: Path) -> list[tuple[float, float]]:
    log = _ffmpeg(
        "-i", str(video), "-an",
        "-vf", "select='gt(scene,0.02)',metadata=print",
        "-f", "null", "-",
    )
    return [(float(z), float(s)) for z, s in _SZENE.findall(log)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo-dir", type=Path, default=DEMO_DIR)
    parser.add_argument("--neu", action="store_true", help="vorhandene Dateien ueberschreiben")
    args = parser.parse_args()

    demo = args.demo_dir
    video = demo / "output.mp4"
    skripte = json.loads((demo / "accepted_scripts.json").read_text(encoding="utf-8"))
    anzahl = len(skripte)
    ziel = demo / "folien"
    ziel.mkdir(exist_ok=True)

    kandidaten = _kandidaten(video)
    if len(kandidaten) < anzahl - 1:
        print(f"Nur {len(kandidaten)} Schnitte gefunden, {anzahl - 1} gebraucht.", file=sys.stderr)
        return 1
    teile = abschnitte(schnitte_waehlen(kandidaten, anzahl - 1), _dauer(video))

    for i, (start, ende) in enumerate(teile):
        bild = ziel / f"folie_{i:03d}.png"
        ton = ziel / f"folie_{i:03d}.mp3"
        if args.neu or not bild.exists():
            _ffmpeg("-y", "-ss", f"{start + min(0.5, (ende - start) / 2):.3f}", "-i", str(video),
                    "-frames:v", "1", "-vf", f"scale={BILD_BREITE}:-2", str(bild))
        if args.neu or not ton.exists():
            _ffmpeg("-y", "-ss", f"{start:.3f}", "-to", f"{ende:.3f}", "-i", str(video),
                    "-vn", "-c:a", "libmp3lame", "-q:a", "5", str(ton))
        print(f"Folie {i + 1}: {start:7.1f} bis {ende:7.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
