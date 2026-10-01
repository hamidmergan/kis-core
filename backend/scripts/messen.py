"""Numbers on a podcast script: who speaks how much, how many half sentences, how spoken it is."""
import json
import re
import sys

for pfad in sys.argv[1:]:
    d = json.load(open(pfad))
    lines = d["lines"]
    namen = d.get("names", ["0", "1"])
    print(f"== {pfad.split('/')[-1]}  {len(lines)} Beitraege  {d.get('sekunden', '?')} s")
    gesamt = sum(len(l["text"].split()) for l in lines)
    for sp in sorted({l["speaker"] for l in lines}):
        w = [len(l["text"].split()) for l in lines if l["speaker"] == sp]
        print(f"  {namen[sp]:6} {len(w):3} Beitraege  {sum(w):5} Woerter ({100 * sum(w) / gesamt:.0f} %)"
              f"  Schnitt {sum(w) / len(w):.0f} W  unter 12 W: {sum(1 for x in w if x < 12)}")
    alle = " ".join(l["text"] for l in lines)
    print(f"  Schnitt gesamt {gesamt / len(lines):.1f} W je Beitrag, {gesamt} W")
    print(f"  Verkuerzungen: {len(re.findall(r"[A-Za-zäöü]+'(?:s|t|re|ll|ve|d|m)\b", alle))}"
          f"  Abbrueche (...): {alle.count('...')}  Ausrufe: {alle.count('!')}")
    w = [len(l["text"].split()) for l in lines]
    import collections
    print("  Laengen je 10 W:", sorted(collections.Counter(min(x // 10, 6) * 10 for x in w).items()))
    print("  erste Woerter:", collections.Counter(re.sub(r"[^\w]", "", l["text"].split()[0].lower()) for l in lines).most_common(5))
    ketten = {}
    for l in lines:
        k = " ".join(l["text"].split()[:4]).lower()
        ketten[k] = ketten.get(k, 0) + 1
    wdh = sorted(((n, k) for k, n in ketten.items() if n > 1), reverse=True)[:6]
    print(f"  gleiche Anfaenge: {wdh}")
