import { describe, it, expect } from "vitest";
import { YoutubeLogo } from "@phosphor-icons/react";
import {
  _embedQmapIntoCitations,
  _formatApiError,
  _isMediaFile,
  _fileKind,
  _formatTime,
  _md,
  _guardMathDollars,
  _mathToUnicode,
  _sourceChipKey,
  _chunkLabel,
  _getChipIcon,
  _youtubeIdOf,
  splitFilename,
  parseFlashcards,
  parseQuiz,
} from "./_utils";

// ── _embedQmapIntoCitations ──────────────────────────────────────────────────
describe("_embedQmapIntoCitations", () => {
  it("embeds the source uuid into a new-format [1, ...] citation", () => {
    const out = _embedQmapIntoCitations("See [1, S. 2 | kw].", [{ qnum: 1, uuid: "abc123" }]);
    expect(out).toBe("See [Q1:abc123, S. 2 | kw].");
  });

  it("also upgrades old-format [Q1, ...] citations", () => {
    const out = _embedQmapIntoCitations("See [Q1, S. 2].", [{ qnum: 1, uuid: "abc123" }]);
    expect(out).toBe("See [Q1:abc123, S. 2].");
  });

  it("returns the text unchanged when qmap is empty", () => {
    expect(_embedQmapIntoCitations("[1, S. 2]", [])).toBe("[1, S. 2]");
  });

  it("leaves citations whose qnum is not in the qmap untouched", () => {
    expect(_embedQmapIntoCitations("[1, S. 2]", [{ qnum: 9, uuid: "x" }])).toBe("[1, S. 2]");
  });
});

// ── _formatApiError ──────────────────────────────────────────────────────────
describe("_formatApiError", () => {
  it("returns a plain string detail", () => {
    expect(_formatApiError({ detail: "boom" })).toBe("boom");
  });

  it("joins a FastAPI validation array on msg", () => {
    expect(_formatApiError({ detail: [{ msg: "too short" }, { msg: "bad type" }] }))
      .toBe("too short; bad type");
  });

  it("stringifies array items without a msg field", () => {
    expect(_formatApiError({ detail: [{ code: 7 }] })).toBe('{"code":7}');
  });

  it("stringifies an object detail", () => {
    expect(_formatApiError({ detail: { a: 1 } })).toBe('{"a":1}');
  });

  it("returns null for non-object / missing detail", () => {
    expect(_formatApiError(null)).toBeNull();
    expect(_formatApiError("nope")).toBeNull();
    expect(_formatApiError({})).toBeNull();
  });
});

// ── _isMediaFile / _fileKind / _getChipIcon ──────────────────────────────────
describe("_isMediaFile", () => {
  it.each([".mp3", ".mp4", ".wav", ".flac", ".m4a", ".webm", ".youtube"])("is true for %s", (ext) => {
    expect(_isMediaFile(`clip${ext}`)).toBe(true);
  });
  it("is case-insensitive", () => {
    expect(_isMediaFile("CLIP.MP4")).toBe(true);
  });
  it("is false for documents and extensionless names", () => {
    expect(_isMediaFile("paper.pdf")).toBe(false);
    expect(_isMediaFile("README")).toBe(false);
  });
});

describe("_fileKind", () => {
  it.each([
    ["slides.pdf", "pdf"],
    ["lecture.mp4", "video"],
    ["talk.webm", "video"],
    ["talk.youtube", "youtube"],
    ["audio.mp3", "audio"],
    ["sound.flac", "audio"],
    ["notes.docx", "doc"],
    ["Arbeitszeitgesetz.page", "page"],
  ] as const)("classifies %s as %s", (name, kind) => {
    expect(_fileKind(name)).toBe(kind);
  });
});

describe("_getChipIcon", () => {
  it("returns a component for every file kind", () => {
    for (const f of ["a.pdf", "a.mp4", "a.mp3", "a.docx", "a.youtube", "a.page"]) {
      expect(_getChipIcon(f)).toBeTruthy();
    }
  });
  it("gives a YouTube source its own icon", () => {
    expect(_getChipIcon("a.youtube")).toBe(YoutubeLogo);
    expect(_getChipIcon("a.mp4")).not.toBe(YoutubeLogo);
  });
});

describe("_youtubeIdOf", () => {
  it("reads the id only for a YouTube source with a link", () => {
    expect(_youtubeIdOf({ filename: "a.youtube", source_url: "https://youtu.be/dQw4w9WgXcQ" })).toBe("dQw4w9WgXcQ");
    expect(_youtubeIdOf({ filename: "a.youtube", source_url: null })).toBeUndefined();
    expect(_youtubeIdOf({ filename: "a.mp4", source_url: "https://youtu.be/dQw4w9WgXcQ" })).toBeUndefined();
  });
});

// ── _formatTime ──────────────────────────────────────────────────────────────
describe("_formatTime", () => {
  it.each([
    [0, "0:00"],
    [5, "0:05"],
    [65, "1:05"],
    [600, "10:00"],
    [3661, "1:01:01"],
  ] as const)("formats %i seconds as %s", (secs, expected) => {
    expect(_formatTime(secs)).toBe(expected);
  });
});

// ── _md (XSS-safe markdown) ──────────────────────────────────────────────────
describe("_md", () => {
  it("renders bold and italic", () => {
    expect(_md("**hi**")).toBe("<strong>hi</strong>");
    expect(_md("*hi*")).toBe("<em>hi</em>");
  });

  it("escapes HTML before applying markdown (no injection)", () => {
    expect(_md("<script>alert(1)</script>")).toBe("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(_md("a & b")).toBe("a &amp; b");
  });

  it("escapes HTML inside bold spans", () => {
    expect(_md("**<img>**")).toBe("<strong>&lt;img&gt;</strong>");
  });

  it("flattens LaTeX to Unicode, since flashcards have no KaTeX", () => {
    expect(_md("Aktiv $\\rightarrow$ Passiv")).toBe("Aktiv → Passiv");
  });
});

// ── _sourceChipKey ───────────────────────────────────────────────────────────
describe("_sourceChipKey", () => {
  it("keys media chips by timestamp", () => {
    expect(_sourceChipKey("1:05", 0, 65, null)).toBe("m:1:05:65");
  });
  it("keys PDF chips by page + highlight", () => {
    expect(_sourceChipKey("S. 2", 2, null, "kw")).toBe("p:S. 2:2:kw");
  });
  it("defaults missing page and highlight", () => {
    expect(_sourceChipKey("S. 0", null, null, null)).toBe("p:S. 0:0:");
  });
});

// ── _chunkLabel ──────────────────────────────────────────────────────────────
describe("_chunkLabel", () => {
  it("uses a formatted timestamp for media with a start time", () => {
    expect(_chunkLabel("v.mp4", 3, 65)).toBe("1:05");
  });
  it("falls back to German 'Teil N' for media without tChip", () => {
    expect(_chunkLabel("v.mp4", 3)).toBe("Teil 3");
  });
  it("falls back to German 'S. N' for documents without tChip", () => {
    expect(_chunkLabel("doc.pdf", 2)).toBe("S. 2");
  });
  it("uses the localized translator when provided", () => {
    const tChip = (key: string, v?: { num: number }) =>
      key === "page" ? `p. ${v?.num}` : `Part ${v?.num}`;
    expect(_chunkLabel("doc.pdf", 2, null, tChip)).toBe("p. 2");
    expect(_chunkLabel("v.mp4", 3, null, tChip)).toBe("Part 3");
  });
  it("names media with neither a time nor a part by its file alone", () => {
    // Invented grammar sentences often have no spot, then the chip names only the file.
    expect(_chunkLabel("v.mp4", null, null)).toBe("");
  });
});

// ── parseFlashcards ──────────────────────────────────────────────────────────
describe("parseFlashcards", () => {
  it("parses 'front | back' lines and strips list numbering", () => {
    expect(parseFlashcards("1. Photosynthese | Umwandlung von Licht")).toEqual([
      { front: "Photosynthese", back: "Umwandlung von Licht" },
    ]);
  });
  it("skips lines without a separator or with an empty side", () => {
    expect(parseFlashcards("no separator here\n2. Front | \n | Back")).toEqual([]);
  });
  it("parses multiple cards", () => {
    expect(parseFlashcards("A | 1\nB | 2")).toEqual([
      { front: "A", back: "1" },
      { front: "B", back: "2" },
    ]);
  });
});

// ── parseQuiz ────────────────────────────────────────────────────────────────
describe("parseQuiz", () => {
  it("parses a question with options and marks the ✓ one correct", () => {
    // Option words avoid the letters r/i/c/h/t/g — see the known-bug test below.
    const text = "1. Welche Farbe?\nA. Apple ✓\nB. Banana\nC. Lemon";
    expect(parseQuiz(text)).toEqual([
      { question: "Welche Farbe?", options: ["Apple", "Banana", "Lemon"], correct: 0 },
    ]);
  });

  it("supports the (richtig) marker and a non-zero correct index", () => {
    const text = "1. Frage?\nA. Apple\nB. Banana (richtig)";
    const out = parseQuiz(text);
    expect(out[0].correct).toBe(1);
  });

  it("parses several questions", () => {
    const text = "1. Eins?\nA. Apple ✓\nB. Banana\n2. Zwei?\nA. Lemon ✓\nB. Pomelo";
    expect(parseQuiz(text)).toHaveLength(2);
  });

  // Guard against the old bug that stripped single letters out of the answers.
  it("strips only the markers, never letters from the option words", () => {
    const out = parseQuiz("1. Q?\nA. Right ✓\nB. Other (richtig)");
    expect(out[0].options).toEqual(["Right", "Other"]);
    expect(out[0].correct).toBe(1);
  });
});

// ── _guardMathDollars ────────────────────────────────────────────────────────
describe("_guardMathDollars", () => {
  it("keeps a LaTeX command untouched so KaTeX can render it", () => {
    const raw = 'z. B. "Ich bin arbeitslos" $\\rightarrow$ "Wenn ich nicht arbeitslos wäre"';
    expect(_guardMathDollars(raw)).toBe(raw);
  });

  it("keeps real formulas untouched", () => {
    expect(_guardMathDollars("Die Formel $x^2 + y_1$ gilt.")).toBe("Die Formel $x^2 + y_1$ gilt.");
    expect(_guardMathDollars("Bruch $\\frac{a}{b}$ hier.")).toBe("Bruch $\\frac{a}{b}$ hier.");
  });

  it("keeps a short symbol-only span untouched", () => {
    expect(_guardMathDollars("Sei $n$ die Anzahl.")).toBe("Sei $n$ die Anzahl.");
    expect(_guardMathDollars("Es gilt $a+b$ immer.")).toBe("Es gilt $a+b$ immer.");
  });

  it("escapes currency pairs so prose does not turn into a formula", () => {
    expect(_guardMathDollars("Das kostet 5$ und jenes 10$ pro Monat."))
      .toBe("Das kostet 5\\$ und jenes 10\\$ pro Monat.");
    expect(_guardMathDollars("Preise: $5 und $10 im Jahr."))
      .toBe("Preise: \\$5 und \\$10 im Jahr.");
  });

  it("escapes a numeric currency range instead of reading it as a formula", () => {
    // Only digits and punctuation in between means money and is protected.
    expect(_guardMathDollars("Kosten 5$-10$ pro Stunde."))
      .toBe("Kosten 5\\$-10\\$ pro Stunde.");
  });

  it("keeps a pure-number calculation as math, so no dollar leaks into the text", () => {
    // It has no letter but is a calculation and not a price.
    expect(_guardMathDollars("also 24 ($11 + 13$).")).toBe("also 24 ($11 + 13$).");
    expect(_guardMathDollars("Paare $(11, 10)$ und $(24, 10)$."))
      .toBe("Paare $(11, 10)$ und $(24, 10)$.");
  });

  it("keeps spaced formulas as math (relation/operator with a variable)", () => {
    // With a letter and an operator it is a formula, despite the spaces.
    expect(_guardMathDollars("Sei $x = 5$ gegeben.")).toBe("Sei $x = 5$ gegeben.");
    expect(_guardMathDollars("Dann $a - b$ und $a + b$.")).toBe("Dann $a - b$ und $a + b$.");
  });

  it("leaves display math alone", () => {
    expect(_guardMathDollars("Formel:\n\n$$E = mc^2$$\n")).toBe("Formel:\n\n$$E = mc^2$$\n");
  });

  it("leaves an unclosed dollar alone while the answer is still streaming", () => {
    expect(_guardMathDollars("Ich bin arbeitslos $\\right")).toBe("Ich bin arbeitslos $\\right");
  });

  it("never touches dollars inside code spans or fences", () => {
    expect(_guardMathDollars("Nutze `echo 5$ und 10$` im Terminal."))
      .toBe("Nutze `echo 5$ und 10$` im Terminal.");
    expect(_guardMathDollars("```\nPRICE=5$\nMAX=10$\n```"))
      .toBe("```\nPRICE=5$\nMAX=10$\n```");
  });

  it("is idempotent, so re-running it on a growing stream stays stable", () => {
    const once = _guardMathDollars("Das kostet 5$ und jenes 10$.");
    expect(_guardMathDollars(once)).toBe(once);
  });

  it("passes text without dollars straight through", () => {
    expect(_guardMathDollars("Ein Satz ohne Sonderzeichen.")).toBe("Ein Satz ohne Sonderzeichen.");
  });
});

// ── _mathToUnicode ───────────────────────────────────────────────────────────
describe("_mathToUnicode", () => {
  it("turns a LaTeX arrow into the plain Unicode character", () => {
    expect(_mathToUnicode('"Ich bin arbeitslos" $\\rightarrow$ "Wenn ich nicht arbeitslos wäre"'))
      .toBe('"Ich bin arbeitslos" → "Wenn ich nicht arbeitslos wäre"');
  });

  it("maps common operators and comparisons", () => {
    expect(_mathToUnicode("$5 \\times 3$ und $a \\leq b$")).toBe("5 × 3 und a ≤ b");
    expect(_mathToUnicode("$\\alpha + \\beta$")).toBe("α + β");
  });

  it("flattens fractions, roots and sub-/superscripts", () => {
    expect(_mathToUnicode("$\\frac{a}{b}$")).toBe("a/b");
    expect(_mathToUnicode("$\\sqrt{2}$")).toBe("√(2)");
    expect(_mathToUnicode("$x^2 + y_1$")).toBe("x² + y₁");
  });

  it("handles display math", () => {
    expect(_mathToUnicode("$$E = mc^2$$")).toBe("E = mc²");
  });

  it("drops the backslash of an unknown command instead of showing it raw", () => {
    expect(_mathToUnicode("$\\foobar x$")).toBe("foobar x");
  });

  it("leaves currency alone, same rule as the renderer", () => {
    expect(_mathToUnicode("Das kostet 5$ und jenes 10$ pro Monat."))
      .toBe("Das kostet 5$ und jenes 10$ pro Monat.");
  });

  it("passes text without dollars straight through", () => {
    expect(_mathToUnicode("Ein Satz ohne Formeln.")).toBe("Ein Satz ohne Formeln.");
  });
});

// ── splitFilename ────────────────────────────────────────────────────────────
describe("splitFilename", () => {
  it("trennt Namensteil und Endung", () => {
    expect(splitFilename("vorlesung.pdf")).toEqual(["vorlesung", ".pdf"]);
  });

  it("trennt am letzten Punkt", () => {
    expect(splitFilename("teil.1.woche.mp4")).toEqual(["teil.1.woche", ".mp4"]);
  });

  it("liefert eine leere Endung, wenn kein Punkt da ist", () => {
    expect(splitFilename("ohnepunkt")).toEqual(["ohnepunkt", ""]);
  });

  it("behandelt einen fuehrenden Punkt als Namensteil", () => {
    // '.gitignore' is the name, not an extension without a name.
    expect(splitFilename(".gitignore")).toEqual([".gitignore", ""]);
  });
});


describe("page sources", () => {
  it("are cited by section and open at it", async () => {
    const { _chunkLabel, _pageSourceHref } = await import("./_utils");
    expect(_chunkLabel("Gesetz.page", 8)).toBe("Abschnitt 8");
    expect(_pageSourceHref("ws", "src", 8)).toBe("/workspace/ws/page/src?abschnitt=8");
    expect(_pageSourceHref("ws", "src")).toBe("/workspace/ws/page/src");
  });
});
