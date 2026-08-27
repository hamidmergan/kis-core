import { describe, it, expect } from "vitest";
import { parseCitationFields, citationsAreAdjacentSameTarget, sanitizeCitationsForMarkdown, stripCitations } from "./_citation_parse";

describe("parseCitationFields", () => {
  it("parses a nav-only page chip", () => {
    const [c] = parseCitationFields("Foo [Q1, S. 8] bar");
    expect(c.qNum).toBe(1);
    expect(c.page).toBe(8);
    expect(c.timestamp).toBeNull();
  });

  it("parses a bare page chip (no q-num)", () => {
    const [c] = parseCitationFields("[S. 5]");
    expect(c.qNum).toBeNull();
    expect(c.page).toBe(5);
  });

  it("parses a media timestamp chip (no page)", () => {
    const [c] = parseCitationFields("[1, 07:56]");
    expect(c.page).toBe(0);
    expect(c.timestamp).toBe("07:56");
  });

  it("carries an embedded source uuid", () => {
    const [c] = parseCitationFields("[Q3:abc123def456, S. 2]");
    expect(c.uuid).toBe("abc123def456");
    expect(c.page).toBe(2);
  });

  it("is forward-tolerant: a legacy '@..|..' chip parses to the page, extras discarded", () => {
    const [c] = parseCitationFields("Foo [Q1, S. 8 @123-187 | Passt die Fragestellung zum Thema?] bar");
    expect(c.qNum).toBe(1);
    expect(c.page).toBe(8);
    // No offsets/keyword fields exist anymore — the legacy extras are simply ignored.
    expect(c.timestamp).toBeNull();
    expect("offsets" in c).toBe(false);
    expect("keyword" in c).toBe(false);
  });

  it("is forward-tolerant for a legacy media chip with a keyword", () => {
    const [c] = parseCitationFields("[1, 07:56 | peer review]");
    expect(c.page).toBe(0);
    expect(c.timestamp).toBe("07:56");
  });

  it("reports match index/length so surrounding text can be sliced", () => {
    const src = "ab [1, S. 2] cd";
    const [c] = parseCitationFields(src);
    expect(src.slice(c.index, c.index + c.length)).toBe("[1, S. 2]");
  });

  it("reports match index/length spanning a legacy trailing token", () => {
    const src = "ab [1, S. 2 @3-9 | kw] cd";
    const [c] = parseCitationFields(src);
    expect(src.slice(c.index, c.index + c.length)).toBe("[1, S. 2 @3-9 | kw]");
  });
});

describe("stripCitations", () => {
  it("removes a nav-only chip entirely", () => {
    expect(stripCitations("a [1, 05:32] b [2, S. 3] c")).toBe("a  b  c");
  });

  it("removes a legacy chip with a trailing offset/keyword", () => {
    const out = stripCitations("Hallo [1, S. 8 @12-47 | ein ganzer Satz hier] Welt");
    expect(out).not.toContain("[");
    expect(out).not.toContain("@");
    expect(out).toContain("Hallo");
    expect(out).toContain("Welt");
  });

  it("removes a stray 【source】 placeholder (no page/time) next to a real chip", () => {
    const out = stripCitations("Die Abgabe ist am 03.07.2026【source】 [1, S. 6] fertig");
    expect(out).not.toContain("source");
    expect(out).not.toContain("【");
    expect(out).not.toContain("[1");      // real chip also gone on copy
    expect(out).toContain("Die Abgabe ist am 03.07.2026");
    expect(out).toContain("fertig");
  });
});

describe("sanitizeCitationsForMarkdown", () => {
  it("strips a citation wrongly appended to a thematic break (---)", () => {
    const out = sanitizeCitationsForMarkdown("--- [5, S. 4]");
    expect(out.trim()).toBe("---");          // clean separator, no chip
    expect(out).not.toContain("S. 4");
  });

  it("keeps a normal list item with a dash bullet intact", () => {
    const out = sanitizeCitationsForMarkdown("- Punkt A [1, S. 2]");
    expect(out).toContain("S. 2");           // real bullet citation survives
  });

  it("tucks a chip trailing a table header/row back into the last cell so gfm keeps the table", () => {
    // A chip behind the last pipe breaks the table.
    const raw = [
      "| Thema | Inhalt | Quelle | [Q1:abc123def456, S. 19]",
      "|-------|--------|--------|",
      "| Hauptmedien | Text, Grafik | | [Q1:abc123def456, S. 19]",
    ].join("\n");
    const lines = sanitizeCitationsForMarkdown(raw).split("\n");
    // every table line ends in a real pipe again → header matches delimiter
    expect(lines[0].trimEnd().endsWith("|")).toBe(true);
    expect(lines[2].trimEnd().endsWith("|")).toBe(true);
    // chip moved inside, right before the restored closing pipe
    expect(lines[0]).toMatch(/S\. 19\]\s*\|\s*$/);
    // both chips preserved (not stripped)
    expect(parseCitationFields(lines.join("\n")).length).toBe(2);
  });

  it("leaves a well-formed table row (chip already inside a cell) unchanged", () => {
    const raw = "| Abgabe | 03.07. [4, S. 6] |";
    const out = sanitizeCitationsForMarkdown(raw);
    expect(out.trimEnd().endsWith("|")).toBe(true);
    expect(out).not.toMatch(/\|\s*\|\s*$/);   // no phantom empty cell introduced
  });

  it("does not touch a citation trailing a non-table line", () => {
    expect(sanitizeCitationsForMarkdown("Ein Satz mit Quelle [1, S. 2]"))
      .toBe("Ein Satz mit Quelle [1, S. 2]");
  });

  it("drops a stray 【source】 placeholder but keeps the real chip", () => {
    const out = sanitizeCitationsForMarkdown("Abgabe am 03.07.2026【source】 [1, S. 6]");
    expect(out).not.toContain("source");
    expect(out).not.toContain("【");
    expect(out).toContain("[1, S. 6]");        // real chip survives for the parser
  });

  it("keeps a valid lenticular 【1, S. 6】 citation (has a page inside)", () => {
    const out = sanitizeCitationsForMarkdown("Text 【1, S. 6】 mehr");
    expect(out).toContain("【1, S. 6】");
  });

  it("lifts a table nested+indented under a bullet to column 0 with a blank line before", () => {
    const raw = [
      "- **Wichtige Termine**:",
      " | Inhalt | Termin |",
      " |---|---|",
      " | Webkonferenz | 01.04.2026 [1, S. 16] |",
      " | Abgabe | 03.07.2026 [1, S. 6] |",
    ].join("\n");
    const lines = sanitizeCitationsForMarkdown(raw).split("\n");
    const headerIdx = lines.findIndex((l) => l === "| Inhalt | Termin |");
    expect(headerIdx).toBeGreaterThan(0);
    expect(lines[headerIdx - 1]).toBe("");             // blank line before the table
    expect(lines[headerIdx + 1]).toBe("|---|---|");    // delimiter de-indented
    expect(lines[headerIdx + 2]).toBe("| Webkonferenz | 01.04.2026 [1, S. 16] |"); // row de-indented, chip kept
  });
});

describe("citationsAreAdjacentSameTarget", () => {
  const key = "src-uuid-1";

  it("merges two back-to-back citations of the same source+page", () => {
    const src = "… BibTex [1, S. 15] [1, S. 15]";
    const [a, b] = parseCitationFields(src);
    expect(citationsAreAdjacentSameTarget(src, a, b, key, key)).toBe(true);
  });

  it("merges across only-punctuation between them (real '[7] S. 8. [7] S. 8' case)", () => {
    const src = "Passt die Fragestellung zum Thema? [7, S. 8]. [7, S. 8]";
    const [a, b] = parseCitationFields(src);
    expect(citationsAreAdjacentSameTarget(src, a, b, key, key)).toBe(true);
  });

  it("does NOT merge when real text sits between them", () => {
    const src = "[1, S. 15] etwas Text dazwischen [1, S. 15]";
    const [a, b] = parseCitationFields(src);
    expect(citationsAreAdjacentSameTarget(src, a, b, key, key)).toBe(false);
  });

  it("does NOT merge when a word ends in a dot between them", () => {
    const src = "[1, S. 15] etc. [1, S. 15]";
    const [a, b] = parseCitationFields(src);
    expect(citationsAreAdjacentSameTarget(src, a, b, key, key)).toBe(false);
  });

  it("does NOT merge different pages", () => {
    const src = "[1, S. 15] [1, S. 16]";
    const [a, b] = parseCitationFields(src);
    expect(citationsAreAdjacentSameTarget(src, a, b, key, key)).toBe(false);
  });

  it("does NOT merge different sources even if adjacent on the same page number", () => {
    const src = "[1, S. 15] [2, S. 15]";
    const [a, b] = parseCitationFields(src);
    expect(citationsAreAdjacentSameTarget(src, a, b, "uuid-1", "uuid-2")).toBe(false);
  });

  it("never merges media timestamp chips", () => {
    const src = "[1, 05:32] [1, 05:32]";
    const [a, b] = parseCitationFields(src);
    expect(citationsAreAdjacentSameTarget(src, a, b, key, key)).toBe(false);
  });
});
