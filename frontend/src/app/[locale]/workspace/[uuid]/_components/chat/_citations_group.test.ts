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

// The node type names in the order they are emitted.
function shape(nodes: ReturnType<typeof parseCitations>): string[] {
  return nodes.map((n) => {
    if (typeof n === "string") return "text";
    const t = (n as ReactElement).type;
    return typeof t === "string" ? t : (t as { name?: string }).name ?? "?";
  });
}
type GroupProps = { groupId: string; tail?: string; chips: Array<{ displayQNum: number | null; label: string }> };
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
    // two SEPARATE stops (each folded on its own), with the prose between them.
    expect(shape(nodes)).toEqual(["CitationChipGroup", "text", "CitationChipGroup"]);
  });

  it("wraps a single chip too, so nothing stays open in a folded text", () => {
    // Every site stays behind its mark, even with only one chip.
    const text = "[1, S. 5] [1, S. 5]";
    const nodes = parseCitations(text, msg, ["u1"], getFilename, noop);
    expect(shape(nodes)).toEqual(["CitationChipGroup"]);
    expect(groupOf(nodes).chips).toHaveLength(1);   // the duplicate is merged away first
  });
});

describe("parseCitations — every stop has its own id", () => {
  // The id has to name the place, otherwise two sites share one choice.
  it("gives two stops with identical sources different ids", () => {
    const text = "Erstens dies. [1, S. 5] Zweitens das. [1, S. 5]";
    const groups = groupsOf(parseCitations(text, msg, ["u1"], getFilename, noop));
    expect(groups).toHaveLength(2);
    expect(groups[0].groupId).not.toBe(groups[1].groupId);
  });

  it("gives media stops of the same file but different seconds different ids", () => {
    // A media chip has no page, ids built on the page would collapse.
    const text = "Erstens dies. [1, 07:56] Zweitens das. [1, 27:30]";
    const groups = groupsOf(parseCitations(text, msg, ["u1"], getFilename, noop));
    expect(groups).toHaveLength(2);
    expect(groups[0].groupId).not.toBe(groups[1].groupId);
  });

  it("gives the same stop in two paragraphs different ids", () => {
    // Every node counts from 0, the prefix has to name it.
    const text = "Dies. [1, S. 5]";
    const a = groupOf(parseCitations(text, msg, ["u1"], getFilename, noop, "m7#0-"));
    const b = groupOf(parseCitations(text, msg, ["u1"], getFilename, noop, "m7#84-"));
    expect(a.groupId).not.toBe(b.groupId);
  });

  it("keeps the id of a stop stable while later text is still being written", () => {
    // The stream appends at the end, an open site keeps its id.
    const partial = "Erstens dies. [1, S. 5] Zweitens";
    const full = "Erstens dies. [1, S. 5] Zweitens das. [1, S. 9]";
    const before = groupOf(parseCitations(partial, msg, ["u1"], getFilename, noop, "m7#0-"));
    const after = groupOf(parseCitations(full, msg, ["u1"], getFilename, noop, "m7#0-"));
    expect(after.groupId).toBe(before.groupId);
  });
});

describe("parseCitations — die Stelle laeuft im Satz mit", () => {
  // The chips always sit in the layout and run along in the rest of the line.
  it("laesst den Text hinter der Stelle einfach weiterlaufen", () => {
    const nodes = parseCitations("Dies gilt [1, S. 5] und weiter.", msg, ["u1"], getFilename, noop);
    expect(shape(nodes)).toEqual(["text", "CitationChipGroup", "text"]);
    expect(nodes[2]).toBe(" und weiter.");
  });

  it("hands the punctuation of the finished sentence to the stop itself", () => {
    // The period belongs right behind the mark, before the reserved space.
    const nodes = parseCitations("Dies gilt [1, S. 5]. Und weiter.", msg, ["u1"], getFilename, noop);
    expect(shape(nodes)).toEqual(["text", "CitationChipGroup", "text"]);
    expect(groupOf(nodes).tail).toBe(".");
    // The space to the next sentence stays.
    expect(nodes[2]).toBe(" Und weiter.");
  });

  it("takes closing punctuation of any script along", () => {
    // Not a German rule: whatever closes the sentence in the answer's language stays.
    const nodes = parseCitations("这是 [1, S. 5]。下一句", msg, ["u1"], getFilename, noop);
    expect(shape(nodes)).toEqual(["text", "CitationChipGroup", "text"]);
    expect(groupOf(nodes).tail).toBe("。");
    expect(nodes[2]).toBe("下一句");
  });

  it("nimmt auch der letzten Stelle eines Absatzes ihren Punkt mit", () => {
    const nodes = parseCitations("Dies gilt [1, S. 5].", msg, ["u1"], getFilename, noop);
    expect(shape(nodes)).toEqual(["text", "CitationChipGroup"]);
    expect(groupOf(nodes).tail).toBe(".");
  });

  it("schluckt Leerzeichen nur zusammen mit einem Satzzeichen", () => {
    // Without punctuation the gap stays.
    const nodes = parseCitations("Dies gilt [1, S. 5]  ", msg, ["u1"], getFilename, noop);
    expect(shape(nodes)).toEqual(["text", "CitationChipGroup", "text"]);
    expect(nodes[2]).toBe("  ");
  });

  it("behandelt jede Stelle gleich, nicht nur die erste", () => {
    const nodes = parseCitations("Eins [1, S. 5]. Zwei [2, S. 8]. Drei.", msg, ["u1"], getFilename, noop);
    expect(shape(nodes)).toEqual([
      "text", "CitationChipGroup",
      "text", "CitationChipGroup", "text",
    ]);
    expect(groupsOf(nodes).map((g) => g.tail)).toEqual([".", "."]);
  });

  it("writes the punctuation exactly once", () => {
    // The site consumes what it takes along, otherwise the period appears twice.
    const nodes = parseCitations("Dies gilt [1, S. 5]. Und weiter.", msg, ["u1"], getFilename, noop);
    expect(nodes.filter((n) => typeof n === "string")).toEqual(["Dies gilt ", " Und weiter."]);
  });

  it("laesst den Punkt in einer Tabellenzelle stehen", () => {
    // A cell holds no sentence that a period ends, so nothing is taken along.
    const nodes = parseCitations("Dies gilt [1, S. 5]. Und weiter.", msg, ["u1"], getFilename, noop, "c", undefined, false);
    expect(shape(nodes)).toEqual(["text", "CitationChipGroup", "text"]);
    expect(groupOf(nodes).tail).toBe("");
    expect(nodes[2]).toBe(". Und weiter.");
  });
});

describe("parseCitations — hard ceiling of three chips per group", () => {
  // At most three chips per site, the further ones are the weakest hits.
  const long = "…dazu. [4, S. 34] [4, S. 29] [4, S. 18] [4, S. 12] [4, S. 7]";

  it("keeps only the first three chips of a longer run", () => {
    const group = groupOf(parseCitations(long, msg, ["u4"], getFilename, noop));
    expect(group.chips.map((c) => c.label)).toEqual(["S. 34", "S. 29", "S. 18"]);
  });

  it("consumes the WHOLE run, so a dropped chip leaves no raw token in the text", () => {
    const nodes = parseCitations(long, msg, ["u4"], getFilename, noop);
    // Cut markers must not reappear as raw text.
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
    // The zero trap: a chip at 00:00 ended up on the PDF branch.
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
