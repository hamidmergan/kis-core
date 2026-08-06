import { describe, it, expect } from "vitest";
import type { ReactElement } from "react";
import { parseCitations } from "./_citations";
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

// Names of the React node types in the order they are emitted (text nodes -> "text").
function shape(nodes: ReturnType<typeof parseCitations>): string[] {
  return nodes.map((n) =>
    typeof n === "string" ? "text" : ((n as ReactElement).type as { name?: string }).name ?? "?",
  );
}
type GroupProps = { chips: Array<{ displayQNum: number | null; label: string }> };
function groupOf(nodes: ReturnType<typeof parseCitations>): GroupProps {
  const node = nodes.find(
    (n) => typeof n !== "string" && ((n as ReactElement).type as { name?: string }).name === "CitationChipGroup",
  ) as ReactElement;
  return node.props as GroupProps;
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
    // two SEPARATE stops (each folded on its own), with the prose between them
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
