import { describe, it, expect } from "vitest";
import { parseCitationFields, citationsAreAdjacentSameTarget, sanitizeCitationsForMarkdown, stripCitations } from "./_citation_parse";
import { _collapseFold, _allIndexOf } from "../viewer/_highlight";

describe("parseCitationFields", () => {
  it("parses an Architecture-B offset chip", () => {
    const [c] = parseCitationFields("Foo [Q1, S. 8 @123-187 | Passt die Fragestellung zum Thema?] bar");
    expect(c.qNum).toBe(1);
    expect(c.page).toBe(8);
    expect(c.offsets).toEqual([123, 187]);
    expect(c.keyword).toBe("Passt die Fragestellung zum Thema?");
  });

  it("leaves offsets undefined for a plain keyword chip", () => {
    const [c] = parseCitationFields("[Q2, S. 5 | Literaturverwaltung]");
    expect(c.page).toBe(5);
    expect(c.offsets).toBeUndefined();
    expect(c.keyword).toBe("Literaturverwaltung");
  });

  it("parses a media timestamp chip (no page, no offsets)", () => {
    const [c] = parseCitationFields("[1, 07:56 | peer review]");
    expect(c.page).toBe(0);
    expect(c.timestamp).toBe("07:56");
    expect(c.offsets).toBeUndefined();
    expect(c.keyword).toBe("peer review");
  });

  it("parses a table-cell offset chip with the non-pipe separator", () => {
    const [c] = parseCitationFields("| Abgabe | 03.07. [4, S. 6 @1-40 ❘ Abgabe Hausarbeit] |");
    expect(c.page).toBe(6);
    expect(c.offsets).toEqual([1, 40]);
    expect(c.keyword).toBe("Abgabe Hausarbeit");
  });

  it("carries an embedded source uuid", () => {
    const [c] = parseCitationFields("[Q3:abc123def456, S. 2 @10-20 | x]");
    expect(c.uuid).toBe("abc123def456");
    expect(c.offsets).toEqual([10, 20]);
  });

  it("reports match index/length so surrounding text can be sliced", () => {
    const src = "ab [1, S. 2 @3-9 | kw] cd";
    const [c] = parseCitationFields(src);
    expect(src.slice(c.index, c.index + c.length)).toBe("[1, S. 2 @3-9 | kw]");
  });
});

describe("stripCitations", () => {
  it("removes an offset chip entirely (incl. @start-end)", () => {
    const out = stripCitations("Hallo [1, S. 8 @12-47 | ein ganzer Satz hier] Welt");
    expect(out).not.toContain("[");
    expect(out).not.toContain("@");
    expect(out).toContain("Hallo");
    expect(out).toContain("Welt");
  });

  it("removes timestamp and plain chips too", () => {
    expect(stripCitations("a [1, 05:32 | k] b [2, S. 3] c")).toBe("a  b  c");
  });
});

describe("sanitizeCitationsForMarkdown", () => {
  it("strips a URL from the keyword so the chip still parses (real muc2026 case)", () => {
    const raw =
      "Tagungen: *ACM CHI* [5, S. 22 @181-245 | • Mensch und Computer, https://muc2026.mensch-und-computer.de/de/]. " +
      "[5, S. 22 @181-245 | • Mensch und Computer, https://muc2026.mensch-und-computer.de/de/]";
    const out = sanitizeCitationsForMarkdown(raw);
    expect(out).not.toContain("http");        // URL gone → markdown can't autolink/split it
    const fields = parseCitationFields(out);
    expect(fields.length).toBe(1);            // duplicate collapsed → one chip
    expect(fields[0].page).toBe(22);
    expect(fields[0].offsets).toEqual([181, 245]);
    expect(fields[0].keyword).toContain("Mensch und Computer");
  });

  it("collapses an exact-duplicate citation emitted back-to-back", () => {
    const raw = "X [5, S. 22 @1-9 | Mensch und Computer]. [5, S. 22 @1-9 | Mensch und Computer]";
    expect((sanitizeCitationsForMarkdown(raw).match(/S\. 22/g) || []).length).toBe(1);
  });

  it("converts the pipe separator to the table-safe glyph", () => {
    const out = sanitizeCitationsForMarkdown("[1, S. 2 | keyword]");
    expect(out).toContain("❘");
    expect(out).not.toContain("|");
  });

  it("strips a citation wrongly appended to a thematic break (---)", () => {
    const out = sanitizeCitationsForMarkdown("--- [5, S. 4 | ORGANISATORISCHES Ab dem 22.04.2026 offene]");
    expect(out.trim()).toBe("---");          // clean separator, no chip
    expect(out).not.toContain("S. 4");
  });

  it("keeps a normal list item with a dash bullet intact", () => {
    const out = sanitizeCitationsForMarkdown("- Punkt A [1, S. 2 | keyword]");
    expect(out).toContain("S. 2");           // real bullet citation survives
  });

  it("leaves a URL-only keyword as a bare offset chip (no dangling separator)", () => {
    const out = sanitizeCitationsForMarkdown("[5, S. 22 @1-5 | https://x.example/y]");
    expect(out).not.toContain("http");
    const [c] = parseCitationFields(out);
    expect(c.page).toBe(22);
    expect(c.offsets).toEqual([1, 5]);
  });
});

describe("citationsAreAdjacentSameTarget", () => {
  const key = "src-uuid-1";

  it("merges two back-to-back citations of the same source+page", () => {
    const src = "… BibTex [1, S. 15 @1-9 | a] [1, S. 15 @20-30 | b]";
    const [a, b] = parseCitationFields(src);
    expect(citationsAreAdjacentSameTarget(src, a, b, key, key)).toBe(true);
  });

  it("does NOT merge when real text sits between them", () => {
    const src = "[1, S. 15 | a] etwas Text dazwischen [1, S. 15 | b]";
    const [a, b] = parseCitationFields(src);
    expect(citationsAreAdjacentSameTarget(src, a, b, key, key)).toBe(false);
  });

  it("does NOT merge different pages", () => {
    const src = "[1, S. 15 | a] [1, S. 16 | b]";
    const [a, b] = parseCitationFields(src);
    expect(citationsAreAdjacentSameTarget(src, a, b, key, key)).toBe(false);
  });

  it("does NOT merge different sources even if adjacent on the same page number", () => {
    const src = "[1, S. 15 | a] [2, S. 15 | b]";
    const [a, b] = parseCitationFields(src);
    expect(citationsAreAdjacentSameTarget(src, a, b, "uuid-1", "uuid-2")).toBe(false);
  });

  it("never merges media timestamp chips", () => {
    const src = "[1, 05:32 | a] [1, 05:32 | b]";
    const [a, b] = parseCitationFields(src);
    expect(citationsAreAdjacentSameTarget(src, a, b, key, key)).toBe(false);
  });
});

describe("_collapseFold (backend parity)", () => {
  it("collapses whitespace and folds diacritics, keeping an index map", () => {
    const { clean, map } = _collapseFold("Café\n  über");
    expect(clean).toBe("cafe uber");
    // each clean char maps back to a valid raw index
    expect(map.length).toBe(clean.length);
    expect(map[0]).toBe(0);                 // 'c' -> raw 'C'
    expect("Café\n  über"[map[clean.indexOf("u")]]).toBe("ü");
  });

  it("maps the collapsed-space to the first whitespace char of the run", () => {
    const { clean, map } = _collapseFold("a   b");
    const spaceIdx = clean.indexOf(" ");
    expect(map[spaceIdx]).toBe(1);          // first space of the run
    expect(clean).toBe("a b");
  });
});

describe("_allIndexOf", () => {
  it("finds every occurrence up to the cap", () => {
    expect(_allIndexOf("a-a-a", "a")).toEqual([0, 2, 4]);
    expect(_allIndexOf("xxxx", "x", 2)).toEqual([0, 1]);
    expect(_allIndexOf("abc", "z")).toEqual([]);
  });
});
