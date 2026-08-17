// Die freie Zeile unter einer Quellen-Stelle, aber nur EINE.
//
// Der Chip-Vorrat laeuft inline im Zeilenrest hinter der Marke weiter (chip-row in
// globals.css) und bekommt darunter eine freie Zeile. Passt er in den Zeilenrest, ist die
// Rechnung einfach: Chips in der Textzeile, darunter die freie Zeile. Passt er nicht, rutscht
// er selbst in die freie Zeile, und die Zeile darunter waere die zweite. Genau die soll es
// nicht geben: nach JEDER Stelle kommt eine Zeile, nie zwei.
//
// CSS kann das nicht entscheiden, denn "ist umgebrochen" ist kein Zustand, den ein Selektor
// sieht. Also wird gemessen: liegt der LETZTE Chip unter der Zeile der Marke, traegt die Zeile
// `data-own-line` und der Abstand darunter faellt auf 0.
//
// Der letzte, nicht der erste: bei drei Chips passt oft noch einer hinter die Marke und erst
// die anderen zwei rutschen ab. Nach dem ersten Chip zu gehen hiess dann "nichts umgebrochen",
// und unter der Zeile mit Chip 2 und 3 stand wieder eine leere.
//
// Gemessen wird gebuendelt in einem rAF: erst ALLE Zeilen lesen, dann ALLE schreiben. Eine
// Antwort hat bis zu 58 Stellen, und lesen-schreiben-lesen-schreiben waere 58 erzwungene
// Layouts hintereinander.
//
// Die Messung haengt allein an der Breite, nicht am Aufklappen: die Chips stehen zugeklappt
// genauso im Layout (CitationChip, reserved). Ein Zeiger auf einer Stelle aendert daher
// nichts an der Zeile, und die alte Regel bleibt, dass Aufklappen kein Wort verschiebt.

const _rows = new Set<HTMLElement>();
let _queued = false;

// Breite aendert sich auch ohne Fenster-Resize: der Teiler zwischen Chat und Betrachter, eine
// ein- und ausklappende Spalte, Zoom. Darum haengt der Beobachter am Textblock der Stelle und
// nicht am Fenster. ResizeObserver nimmt dasselbe Ziel mehrfach entgegen, ohne es doppelt zu
// fuehren, also darf jede Zeile ihren Block anmelden.
//
// Die Rueckmeldung kann sich nicht aufschaukeln, obwohl sie die Hoehe des Blocks aendert, den
// sie beobachtet: der zweite Durchgang misst dieselbe Breite, findet dasselbe Ergebnis und
// toggleAttribute schreibt bei gleichem Stand nichts mehr.
const _ro = typeof ResizeObserver === "undefined" ? null
  : new ResizeObserver(() => { scheduleChipGapPass(); });

export function registerChipRow(row: HTMLElement | null): void {
  if (!row) return;
  _rows.add(row);
  const host = row.closest("p, li, td, th, blockquote, div");
  if (host && _ro) _ro.observe(host);
  scheduleChipGapPass();
}

export function unregisterChipRow(row: HTMLElement | null): void {
  if (row) _rows.delete(row);
}

export function scheduleChipGapPass(): void {
  if (_queued || typeof requestAnimationFrame === "undefined") return;
  _queued = true;
  requestAnimationFrame(() => {
    _queued = false;
    const verdicts: Array<[HTMLElement, boolean]> = [];
    for (const row of _rows) {
      if (!row.isConnected) continue;
      const head = row.previousElementSibling;
      const chip = row.lastElementChild;
      if (!head || !chip) continue;
      const h = head.getBoundingClientRect();
      const c = chip.getBoundingClientRect();
      // Ein Block ohne Hoehe ist noch nicht gesetzt oder ausgeblendet, da gibt es nichts zu
      // entscheiden.
      if (!h.height || !c.height) continue;
      // Die Mitte des Chips, nicht seine Oberkante: der Chip sitzt auf align-middle und ist
      // niedriger als die Textzeile, seine Oberkante liegt darum in derselben Zeile schon
      // unter der Oberkante der Marke.
      verdicts.push([row, (c.top + c.bottom) / 2 > h.bottom]);
    }
    for (const [row, ownLine] of verdicts) row.toggleAttribute("data-own-line", ownLine);
  });
}
