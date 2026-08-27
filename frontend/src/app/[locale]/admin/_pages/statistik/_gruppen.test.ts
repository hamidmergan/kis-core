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

  // The interface does not rely on the server's sort order.
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

  // The heading appears even with a single group.
  it("schreibt die Ueberschrift auch, wenn es nur eine Gruppe gibt", () => {
    expect(kopfBei(gruppiert([BETREUT]), 0)).toBe("tutor");
  });
});
