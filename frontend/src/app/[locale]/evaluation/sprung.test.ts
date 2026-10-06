import { describe, it, expect } from "vitest";
import { springtWeiter } from "./sprung";

const fragen = [
  { type: "choice" },
  { type: "text" },
  { type: "choice" },
];

describe("Sprung zur naechsten Frage", () => {
  it("springt bei einer Auswahlfrage mit Nachfolger", () => {
    expect(springtWeiter(fragen, 0)).toBe(true);
  });

  it("springt nicht bei der letzten Frage", () => {
    expect(springtWeiter(fragen, 2)).toBe(false);
  });

  it("springt nie bei einer Textfrage", () => {
    expect(springtWeiter(fragen, 1)).toBe(false);
  });

  it("springt nicht, wenn der Index daneben liegt", () => {
    expect(springtWeiter(fragen, 9)).toBe(false);
  });

  it("springt nicht, wenn gar keine Fragen kamen", () => {
    expect(springtWeiter(undefined, 0)).toBe(false);
  });

  it("springt nicht, wenn die Frage einen Ueberspringen-Button hat", () => {
    expect(springtWeiter([{ type: "choice", skippable: true }, { type: "text" }], 0)).toBe(false);
  });
});
