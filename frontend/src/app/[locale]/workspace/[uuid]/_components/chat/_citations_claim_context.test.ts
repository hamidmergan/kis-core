import { describe, it, expect } from "vitest";
import { createElement, type ReactElement } from "react";
import { withCitations } from "./_citations";
import type { ChatMessage } from "../../_types";

// Reproduces how a markdown renderer actually hands a paragraph to withCitations: bold runs
// arrive as their own <strong> elements, splitting the surrounding sentence into several
// string siblings. A citation chip right after such a run must still see the whole sentence,
// not just the text since the last bold run, otherwise the PDF highlight finds nothing.
const msg = {
  role: "assistant",
  content: "",
  source_qmap: [{ qnum: 18, uuid: "u18", filename: "Kapitel_4.pdf" }],
  source_pages: [],
} as unknown as ChatMessage;

const getFilename = () => "Kapitel_4.pdf";
const noop = () => {};

type GroupProps = { chips: Array<{ claim?: string }> };
function firstClaim(nodes: React.ReactNode): string | undefined {
  const arr = nodes as ReactElement[];
  const group = arr.find((n) => typeof n !== "string" && (n.type as { name?: string })?.name === "CitationChipGroup");
  return (group?.props as GroupProps | undefined)?.chips[0]?.claim;
}

describe("withCitations — claim context across bold runs", () => {
  it("carries the plain text of an earlier bold run into the claim", () => {
    const children = [
      "Der ",
      createElement("strong", { key: "b" }, "kritische Pfad"),
      " besteht aus allen Vorgängen ohne Gesamtpuffer (Zeitreserve für eine Kette) [18, S. 3] Weiter.",
    ];
    const claim = firstClaim(withCitations(children, msg, ["u18"], getFilename, noop));
    expect(claim).toBe(
      "Der kritische Pfad besteht aus allen Vorgängen ohne Gesamtpuffer (Zeitreserve für eine Kette)",
    );
  });

  it("carries text across two bold runs", () => {
    const children = [
      "Der ",
      createElement("strong", { key: "b1" }, "kritische Pfad"),
      " braucht ",
      createElement("strong", { key: "b2" }, "Gesamtpuffer"),
      " als Reserve [18, S. 3].",
    ];
    const claim = firstClaim(withCitations(children, msg, ["u18"], getFilename, noop));
    expect(claim).toBe("Der kritische Pfad braucht Gesamtpuffer als Reserve");
  });

  it("resets the carry after a citation, so a later one does not repeat the first sentence", () => {
    const children = [
      "Satz eins mit ",
      createElement("strong", { key: "b" }, "Begriff"),
      " endet [18, S. 3]. Satz zwei ohne Fettung endet auch [18, S. 4].",
    ];
    const claim = firstClaim(withCitations(children, msg, ["u18"], getFilename, noop));
    expect(claim).toBe("Satz eins mit Begriff endet");
  });

  it("stays correct for a plain string with no preceding sibling", () => {
    const children = ["Ein Satz ohne Fettung [18, S. 3]."];
    const claim = firstClaim(withCitations(children, msg, ["u18"], getFilename, noop));
    expect(claim).toBe("Ein Satz ohne Fettung");
  });
});
