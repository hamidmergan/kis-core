/** With more than one demo module the tour must not simply take the first one. */
import { describe, expect, it } from "vitest";

import { waehleRundgangModul } from "./rundgangModul";

const kis = { uuid: "kis", owned: false, tour: false };
const pm = { uuid: "pm", owned: false, tour: true };

describe("waehleRundgangModul", () => {
  it("nimmt das markierte Modul, auch wenn es hinten steht", () => {
    expect(waehleRundgangModul([kis, pm])?.uuid).toBe("pm");
  });

  it("nimmt ohne Markierung das erste fremde Modul", () => {
    expect(waehleRundgangModul([{ ...kis }, { ...pm, tour: false }])?.uuid).toBe("kis");
  });

  it("ueberspringt eigene Module auch wenn sie markiert sind", () => {
    expect(waehleRundgangModul([{ ...pm, owned: true }, kis])?.uuid).toBe("kis");
  });

  it("gibt nichts zurueck, wenn alle Module einem selbst gehoeren", () => {
    expect(waehleRundgangModul([{ ...pm, owned: true }])).toBeUndefined();
  });

  it("kommt mit einer leeren Liste klar", () => {
    expect(waehleRundgangModul([])).toBeUndefined();
  });
});
