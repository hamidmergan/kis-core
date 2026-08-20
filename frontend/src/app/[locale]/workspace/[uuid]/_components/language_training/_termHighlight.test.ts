import { describe, it, expect } from "vitest";
import { splitExample } from "./_termHighlight";

const bold = (sentence: string, forms: (string | undefined)[]) =>
  splitExample(sentence, forms).filter(s => s.focus).map(s => s.text);

describe("splitExample", () => {
  it("markiert das gelernte Wort im Satz", () => {
    const parts = splitExample("Ich schreibe ein Inhaltsverzeichnis.", ["Inhaltsverzeichnis"]);
    expect(parts.map(p => p.text).join("")).toBe("Ich schreibe ein Inhaltsverzeichnis.");
    expect(bold("Ich schreibe ein Inhaltsverzeichnis.", ["Inhaltsverzeichnis"])).toEqual(["Inhaltsverzeichnis"]);
  });

  it("findet die gebeugte Form", () => {
    expect(bold("Beide Inhaltsverzeichnisse fehlen.", ["Inhaltsverzeichnis"])).toEqual(["Inhaltsverzeichnisse"]);
    expect(bold("Die Arbeiten sind fertig.", ["Arbeit"])).toEqual(["Arbeiten"]);
  });

  it("markiert nur ganze Woerter, nie ein Stueck aus einem laengeren Wort", () => {
    expect(bold("Das Inhaltsverzeichnis ist lang.", ["Inhalt"])).toEqual([]);
    expect(bold("Ein Sachverzeichnis fehlt.", ["Verzeichnis"])).toEqual([]);
  });

  it("nimmt den Artikel von der Grundform weg", () => {
    expect(bold("Das Verzeichnis ist lang.", ["das Verzeichnis"])).toEqual(["Verzeichnis"]);
  });

  it("nutzt die mitgelieferten Verbformen", () => {
    expect(bold("Er hat den Text geschrieben.", ["schreiben", "er hat geschrieben"])).toEqual(["geschrieben"]);
  });

  it("markiert jede Stelle im Satz", () => {
    expect(bold("Der Filter und der Filter.", ["Filter"])).toEqual(["Filter", "Filter"]);
  });

  it("laesst den Satz in Ruhe, wenn nichts passt", () => {
    expect(splitExample("Ein anderer Satz.", ["Inhaltsverzeichnis"])).toEqual([{ text: "Ein anderer Satz.", focus: false }]);
    expect(splitExample("Ein anderer Satz.", [undefined, ""])).toEqual([{ text: "Ein anderer Satz.", focus: false }]);
  });

  it("ignoriert die Gross- und Kleinschreibung", () => {
    expect(bold("die arbeit ist fertig.", ["Arbeit"])).toEqual(["arbeit"]);
  });
});
