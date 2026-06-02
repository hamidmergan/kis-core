import { describe, it, expect } from "vitest";
import { parseCitationFields, stripCitations } from "./_citation_parse";
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
