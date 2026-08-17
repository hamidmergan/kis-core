import { describe, it, expect } from "vitest";
import type { ReactElement } from "react";
import { chipClickArgs, parseCitations } from "./_citations";
import type { ChatMessage } from "../../_types";

// Minimal multi-source message so displayQNum stays visible (single-source drops [n]).
const msg = {
  role: "assistant",
  content: "",
  source_qmap: [
    { qnum: 1, uuid: "u1", filename: "A.pdf" },
    { qnum: 2, uuid: "u2", filename: "B.pdf" },
    { qnum: 3, uuid: "u3", filename: "C.pdf" },
    { qnum: 4, uuid: "u4", filename: "KoSM-11_Negative-Folgen.pdf" },
  ],
  source_pages: [],
} as unknown as ChatMessage;

const getFilename = (uuid: string) =>
  ({ u1: "A.pdf", u2: "B.pdf", u3: "C.pdf", u4: "KoSM-11_Negative-Folgen.pdf" }[uuid] ?? "");
const noop = () => {};

// Names of the React node types in the order they are emitted (text nodes -> "text",
// intrinsic elements like the line break -> their tag name).
function shape(nodes: ReturnType<typeof parseCitations>): string[] {
  return nodes.map((n) => {
    if (typeof n === "string") return "text";
    const t = (n as ReactElement).type;
    return typeof t === "string" ? t : (t as { name?: string }).name ?? "?";
  });
}
type GroupProps = { groupId: string; tail?: string; ownRow?: boolean; chips: Array<{ displayQNum: number | null; label: string }> };
function groupsOf(nodes: ReturnType<typeof parseCitations>): GroupProps[] {
  return nodes
    .filter((n) => typeof n !== "string" && ((n as ReactElement).type as { name?: string }).name === "CitationChipGroup")
    .map((n) => (n as ReactElement).props as GroupProps);
}
function groupOf(nodes: ReturnType<typeof parseCitations>): GroupProps {
  return groupsOf(nodes)[0];
}

describe("parseCitations — adjacent-chip accordion", () => {
  it("folds three adjacent same-source page chips into one group", () => {
    // Exactly the reported case: [4] S. 34  [4] S. 29  [4] S. 18 (only spaces between).
    const text = "…bei Jugendlichen. [4, S. 34] [4, S. 29] [4, S. 18]";
    const nodes = parseCitations(text, msg, ["u4"], getFilename, noop);
    expect(shape(nodes)).toEqual(["text", "CitationChipGroup"]);

    const group = groupOf(nodes);
    expect(group.chips).toHaveLength(3);
    // First chip is the leftmost; it carries the source number and first page.
    expect(group.chips[0].displayQNum).toBe(4);
    expect(group.chips[0].label).toBe("S. 34");
    expect(group.chips.map((c) => c.label)).toEqual(["S. 34", "S. 29", "S. 18"]);
  });

  it("does NOT merge chips separated by real text into one stop", () => {
    const text = "[1, S. 5] und auch [2, S. 8]";
    const nodes = parseCitations(text, msg, ["u1"], getFilename, noop);
    // two SEPARATE stops (each folded on its own), with the prose between them. The stop
    // ends its line, so the prose after it starts on the next one.
    expect(shape(nodes)).toEqual(["CitationChipGroup", "text", "CitationChipGroup"]);
  });

  it("wraps a single chip too, so nothing stays open in a folded text", () => {
    // Every stop is collapsed behind its mark, however many chips it holds. A lone chip
    // rendered bare would be the only visible source label on the page and read as noise.
    const text = "[1, S. 5] [1, S. 5]";
    const nodes = parseCitations(text, msg, ["u1"], getFilename, noop);
    expect(shape(nodes)).toEqual(["CitationChipGroup"]);
    expect(groupOf(nodes).chips).toHaveLength(1);   // the duplicate is merged away first
  });
});

describe("parseCitations — every stop has its own id", () => {
  // The id is what the open/closed choice is stored under. Two stops sharing one id share
  // one choice: opening either one opens BOTH as soon as the tree is rebuilt, e.g. when a
  // chip click opens the viewer. So the id must name the PLACE, never the content.
  it("gives two stops with identical sources different ids", () => {
    const text = "Erstens dies. [1, S. 5] Zweitens das. [1, S. 5]";
    const groups = groupsOf(parseCitations(text, msg, ["u1"], getFilename, noop));
    expect(groups).toHaveLength(2);
    expect(groups[0].groupId).not.toBe(groups[1].groupId);
  });

  it("gives media stops of the same file but different seconds different ids", () => {
    // The worst case in practice: a media chip carries no page (0 for all of them), so an
    // id built from source + page collapses every stop of one file into a single id.
    const text = "Erstens dies. [1, 07:56] Zweitens das. [1, 27:30]";
    const groups = groupsOf(parseCitations(text, msg, ["u1"], getFilename, noop));
    expect(groups).toHaveLength(2);
    expect(groups[0].groupId).not.toBe(groups[1].groupId);
  });

  it("gives the same stop in two paragraphs different ids", () => {
    // Each markdown node parses on its own and its offsets restart at 0, so the prefix has
    // to carry the message and the position of the node.
    const text = "Dies. [1, S. 5]";
    const a = groupOf(parseCitations(text, msg, ["u1"], getFilename, noop, "m7#0-"));
    const b = groupOf(parseCitations(text, msg, ["u1"], getFilename, noop, "m7#84-"));
    expect(a.groupId).not.toBe(b.groupId);
  });

  it("keeps the id of a stop stable while later text is still being written", () => {
    // Streaming appends, so a stop that is already on screen keeps its position and must
    // keep its id, otherwise an opened stop folds itself away mid-answer.
    const partial = "Erstens dies. [1, S. 5] Zweitens";
    const full = "Erstens dies. [1, S. 5] Zweitens das. [1, S. 9]";
    const before = groupOf(parseCitations(partial, msg, ["u1"], getFilename, noop, "m7#0-"));
    const after = groupOf(parseCitations(full, msg, ["u1"], getFilename, noop, "m7#0-"));
    expect(after.groupId).toBe(before.groupId);
  });
});

describe("parseCitations — jede Stelle bekommt ihre eigene Chipzeile", () => {
  // Die Chips einer Stelle stehen IMMER im Layout (nur unsichtbar, solange die Stelle zu
  // ist), damit ein Zeiger kein Wort verschiebt. Frueher lagen sie im Zeilenrest des Satzes:
  // passte der Vorrat noch hin, sah man nichts, passte er nicht, erschien eine Leerzeile.
  // Ob also eine Zeile dazukam, entschied allein die Satzlaenge. Deshalb haengt der Vorrat
  // jetzt IMMER eine freie Zeile an (`ownRow`), und der Block dahinter bricht selbst um, ein
  // eigenes <br> gibt es nicht mehr. Die Chips beginnen dabei im Zeilenrest hinter der Marke.
  it("bricht ohne <br> um, die Chipzeile macht das selbst", () => {
    const nodes = parseCitations("Dies gilt [1, S. 5] und weiter.", msg, ["u1"], getFilename, noop);
    expect(shape(nodes)).toEqual(["text", "CitationChipGroup", "text"]);
    expect(groupOf(nodes).ownRow).toBe(true);
  });

  it("hands the punctuation of the finished sentence to the stop itself", () => {
    // The period must sit right behind the mark, AHEAD of the room the hidden chips hold.
    // Left in the text it landed behind that room and hung alone in the middle of the line.
    const nodes = parseCitations("Dies gilt [1, S. 5]. Und weiter.", msg, ["u1"], getFilename, noop);
    expect(shape(nodes)).toEqual(["text", "CitationChipGroup", "text"]);
    expect(groupOf(nodes).tail).toBe(".");
    expect(nodes[2]).toBe("Und weiter.");
  });

  it("takes closing punctuation of any script along", () => {
    // Not a German rule: whatever closes the sentence in the answer's language stays.
    const nodes = parseCitations("这是 [1, S. 5]。下一句", msg, ["u1"], getFilename, noop);
    expect(shape(nodes)).toEqual(["text", "CitationChipGroup", "text"]);
    expect(groupOf(nodes).tail).toBe("。");
    expect(nodes[2]).toBe("下一句");
  });

  it("gibt auch der letzten Stelle eines Absatzes ihre Zeile", () => {
    // Genau hier lag der zweite Unterschied: ohne eigene Zeile hing der Vorrat im Zeilenrest
    // des letzten Satzes und der Absatz brachte sein eigenes mb-2 mit. Der Abstand nach einer
    // Stelle sah am Absatzende anders aus als mitten im Absatz.
    const nodes = parseCitations("Dies gilt [1, S. 5].", msg, ["u1"], getFilename, noop);
    expect(shape(nodes)).toEqual(["text", "CitationChipGroup"]);
    expect(groupOf(nodes).tail).toBe(".");
    expect(groupOf(nodes).ownRow).toBe(true);
  });

  it("frisst die Leerzeichen zwischen Stelle und naechstem Satz", () => {
    // Sonst faengt die neue Zeile mit einem Leerzeichen an und der Satz steht eingerueckt.
    const nodes = parseCitations("Dies gilt [1, S. 5]  ", msg, ["u1"], getFilename, noop);
    expect(shape(nodes)).toEqual(["text", "CitationChipGroup"]);
  });

  it("gibt jeder Stelle eine Zeile, nicht nur der ersten", () => {
    const nodes = parseCitations("Eins [1, S. 5]. Zwei [2, S. 8]. Drei.", msg, ["u1"], getFilename, noop);
    expect(shape(nodes)).toEqual([
      "text", "CitationChipGroup",
      "text", "CitationChipGroup", "text",
    ]);
    expect(groupsOf(nodes).map((g) => g.tail)).toEqual([".", "."]);
    expect(groupsOf(nodes).map((g) => g.ownRow)).toEqual([true, true]);
  });

  it("writes the punctuation exactly once", () => {
    // The stop consumes what it takes along, otherwise the period is drawn twice: once by
    // the stop and once by the text that follows it.
    const nodes = parseCitations("Dies gilt [1, S. 5]. Und weiter.", msg, ["u1"], getFilename, noop);
    expect(nodes.filter((n) => typeof n === "string")).toEqual(["Dies gilt ", "Und weiter."]);
  });

  it("bleibt in einer Tabellenzelle inline", () => {
    // A cell has no sentence flow to break. The room for the chips is still reserved, which
    // widens the column a little — the price for a table that never jumps.
    const nodes = parseCitations("Dies gilt [1, S. 5]. Und weiter.", msg, ["u1"], getFilename, noop, "c", undefined, false);
    expect(shape(nodes)).toEqual(["text", "CitationChipGroup", "text"]);
    expect(groupOf(nodes).tail).toBe("");
    expect(groupOf(nodes).ownRow).toBe(false);
    expect(nodes[2]).toBe(". Und weiter.");
  });
});

describe("parseCitations — hard ceiling of three chips per group", () => {
  // A group carries at most 3 chips: one visible plus two behind the caret. Longer runs are
  // trimmed, so opening a group can never unroll into a wall of pills. Chips arrive
  // closest-first, so the dropped ones are the weakest matches.
  const long = "…dazu. [4, S. 34] [4, S. 29] [4, S. 18] [4, S. 12] [4, S. 7]";

  it("keeps only the first three chips of a longer run", () => {
    const group = groupOf(parseCitations(long, msg, ["u4"], getFilename, noop));
    expect(group.chips.map((c) => c.label)).toEqual(["S. 34", "S. 29", "S. 18"]);
  });

  it("consumes the WHOLE run, so a dropped chip leaves no raw token in the text", () => {
    const nodes = parseCitations(long, msg, ["u4"], getFilename, noop);
    // Only the leading prose is emitted as text: the capped-away "[4, S. 12] [4, S. 7]"
    // must not reappear as literal text after the group.
    expect(nodes.filter((n) => typeof n === "string")).toEqual(["…dazu. "]);
  });

  it("still folds a run of exactly three into one group", () => {
    const text = "…dazu. [4, S. 34] [4, S. 29] [4, S. 18]";
    const nodes = parseCitations(text, msg, ["u4"], getFilename, noop);
    expect(shape(nodes)).toEqual(["text", "CitationChipGroup"]);
    expect(groupOf(nodes).chips).toHaveLength(3);
  });
});


describe("chipClickArgs — was ein Klick weitergibt", () => {
  const medien = {
    clickPage: 7,
    clickSeconds: 96.4,
    clickEndSeconds: 180.2,
    clickChunkStart: 60.0,
    clickHighlight: undefined,
    claim: "Die Aussage der Antwort.",
  };

  it("reicht bei Medien Chunk-Anfang und -Ende weiter", () => {
    const a = chipClickArgs(medien);
    expect(a.istMedien).toBe(true);
    expect(a.page).toBe(0);
    expect(a.endTime).toBe(180.2);
    expect(a.chunkStart).toBe(60.0);
    expect(a.sourceText).toBe("Die Aussage der Antwort.");
  });

  it("verliert bei 00:00 nichts — die Sekunde 0 ist keine fehlende Zeit", () => {
    // Die Null-Falle: `clickSeconds ? … : …` schickte einen Chip auf 00:00 in den
    // PDF-Zweig, ohne Chunk-Anfang und ohne Ende. Auf den Chunk-Anfang zeigt ein Chip
    // aber genau dann, wenn keine Zeile sicher genug war — also wenn das Transkript den
    // ganzen Abschnitt markieren soll und beides dafuer braucht.
    const a = chipClickArgs({ ...medien, clickSeconds: 0, clickChunkStart: 0 });
    expect(a.istMedien).toBe(true);
    expect(a.page).toBe(0);
    expect(a.endTime).toBe(180.2);
    expect(a.chunkStart).toBe(0);
    expect(a.sourceText).toBe("Die Aussage der Antwort.");
  });

  it("bleibt bei einer PDF-Seite auf Seite und Wortlaut", () => {
    const a = chipClickArgs({
      clickPage: 7, clickSeconds: undefined, clickEndSeconds: undefined,
      clickChunkStart: undefined, clickHighlight: "wortwoertlich", claim: "egal",
    });
    expect(a.istMedien).toBe(false);
    expect(a.page).toBe(7);
    expect(a.sourceText).toBe("wortwoertlich");
    expect(a.endTime).toBeUndefined();
    expect(a.chunkStart).toBeUndefined();
  });
});
