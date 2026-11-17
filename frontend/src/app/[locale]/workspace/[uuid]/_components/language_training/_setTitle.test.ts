import { describe, it, expect } from "vitest";
import { setDisplayTitle, withoutFileExtension } from "./_setTitle";

describe("setDisplayTitle", () => {
  it("drops the generated prefix in both languages", () => {
    expect(setDisplayTitle("Lernkarten aus Skript.pdf")).toBe("Skript.pdf");
    expect(setDisplayTitle("Grammatik-Übung von Kapitel 2")).toBe("Kapitel 2");
    expect(setDisplayTitle("Grammar exercise from Chapter 2")).toBe("Chapter 2");
    expect(setDisplayTitle("Quiz of Week 1")).toBe("Week 1");
  });

  it("leaves a name of your own alone", () => {
    expect(setDisplayTitle("Quizfragen Woche 1")).toBe("Quizfragen Woche 1");
  });
});

describe("withoutFileExtension", () => {
  it("cuts a known ending only at the end", () => {
    expect(withoutFileExtension("Vorlesung.MP4")).toBe("Vorlesung");
    expect(withoutFileExtension("a.pdf.txt")).toBe("a.pdf.txt");
  });
});
