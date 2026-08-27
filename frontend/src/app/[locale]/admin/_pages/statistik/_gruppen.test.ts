import { describe, expect, it } from "vitest";

import { gruppiert, kopfBei } from "./_gruppen";

const m = (title: string, access: "owner" | "tutor") => ({ title, access });

const EIGEN_A = m("Werkstoffkunde 2", "owner");
const EIGEN_B = m("Technisches Deutsch B2", "owner");
const BETREUT = m("Statik Grundlagen", "tutor");

describe("gruppiert", () => {
  it("stellt die eigenen Module vor die betreuten", () => {
    const raus = gruppiert([BETREUT, EIGEN_A]);

    expect(raus.map((x) => x.access)).toEqual(["owner", "tutor"]);
  });

  // Der Server sortiert schon so. Die Oberflaeche verlaesst sich nicht darauf:
  // eine Zwischenueberschrift, die mitten in einer Gruppe steht, waere falsch
  // und niemandem faellt auf, warum.
  it("mischt die beiden Gruppen nie ineinander", () => {
    const raus = gruppiert([BETREUT, EIGEN_A, BETREUT, EIGEN_B]);

    expect(raus.map((x) => x.access)).toEqual(["owner", "owner", "tutor", "tutor"]);
  });

  it("haelt die Reihenfolge innerhalb einer Gruppe fest", () => {
    const raus = gruppiert([EIGEN_A, EIGEN_B]);

    expect(raus.map((x) => x.title)).toEqual(["Werkstoffkunde 2", "Technisches Deutsch B2"]);
  });

  it("haelt eine leere Liste aus", () => {
    expect(gruppiert([])).toEqual([]);
  });
});

describe("kopfBei", () => {
  it("setzt ueber die erste Zeile eine Ueberschrift", () => {
    expect(kopfBei(gruppiert([EIGEN_A, BETREUT]), 0)).toBe("owner");
  });

  it("setzt eine zweite, wo die Gruppe wechselt", () => {
    expect(kopfBei(gruppiert([EIGEN_A, BETREUT]), 1)).toBe("tutor");
  });

  it("laesst die Zeilen dazwischen ohne", () => {
    const liste = gruppiert([EIGEN_A, EIGEN_B, BETREUT]);

    expect(kopfBei(liste, 1)).toBeNull();
  });

  // Anders als auf der Startseite, wo eine einzelne Gruppe immer "was ich
  // betreue" heisst. Hier waeren es zwei verschiedene Dinge, und wer nur
  // fremde Module betreut, wuesste sonst nicht, dass keins davon ihm gehoert.
  it("schreibt die Ueberschrift auch, wenn es nur eine Gruppe gibt", () => {
    expect(kopfBei(gruppiert([BETREUT]), 0)).toBe("tutor");
  });
});
