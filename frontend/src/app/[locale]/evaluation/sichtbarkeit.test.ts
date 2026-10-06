import { describe, it, expect } from "vitest";
import { istSichtbar, naechsterSichtbarerIndex } from "./sichtbarkeit";

describe("Sichtbarkeit einer Frage", () => {
  it("ist sichtbar ohne show_if", () => {
    expect(istSichtbar({}, {})).toBe(true);
  });

  it("ist versteckt, wenn die vorherige Frage noch keine Antwort hat", () => {
    const frage = { show_if: { question_id: "bereich", in: ["A"] } };
    expect(istSichtbar(frage, {})).toBe(false);
  });

  it("ist sichtbar, wenn die vorherige Antwort passt (einzeln)", () => {
    const frage = { show_if: { question_id: "zurechtgefunden", in: ["Eher nein", "Nein"] } };
    expect(istSichtbar(frage, { zurechtgefunden: "Nein" })).toBe(true);
  });

  it("ist versteckt, wenn die vorherige Antwort nicht passt (einzeln)", () => {
    const frage = { show_if: { question_id: "zurechtgefunden", in: ["Eher nein", "Nein"] } };
    expect(istSichtbar(frage, { zurechtgefunden: "Ja" })).toBe(false);
  });

  it("ist sichtbar, wenn eine Mehrfachauswahl den Wert enthaelt", () => {
    const frage = { show_if: { question_id: "bereich", in: ["Lernassistent"] } };
    expect(istSichtbar(frage, { bereich: ["Lernassistent", "Dienste"] })).toBe(true);
  });

  it("ist versteckt, wenn die Mehrfachauswahl den Wert nicht enthaelt", () => {
    const frage = { show_if: { question_id: "bereich", in: ["Lernassistent"] } };
    expect(istSichtbar(frage, { bereich: ["Dienste"] })).toBe(false);
  });
});

describe("Naechster sichtbarer Index", () => {
  const fragen = [
    {},
    { show_if: { question_id: "bereich", in: ["A"] } },
    { show_if: { question_id: "bereich", in: ["B"] } },
    {},
  ];

  it("ueberspringt eine versteckte Frage vorwaerts", () => {
    expect(naechsterSichtbarerIndex(fragen, { bereich: ["B"] }, 1, 1)).toBe(2);
  });

  it("ueberspringt eine versteckte Frage rueckwaerts", () => {
    expect(naechsterSichtbarerIndex(fragen, { bereich: ["A"] }, 2, -1)).toBe(1);
  });

  it("laeuft bis ans Ende, wenn alles danach versteckt ist", () => {
    const nurVersteckt = [{}, { show_if: { question_id: "bereich", in: ["A"] } }];
    expect(naechsterSichtbarerIndex(nurVersteckt, {}, 1, 1)).toBe(2);
  });

  it("laeuft unter null, wenn alles davor versteckt ist", () => {
    const nurVersteckt = [{ show_if: { question_id: "bereich", in: ["A"] } }];
    expect(naechsterSichtbarerIndex(nurVersteckt, {}, 0, -1)).toBe(-1);
  });
});
