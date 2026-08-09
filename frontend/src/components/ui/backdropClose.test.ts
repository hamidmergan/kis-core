import { describe, expect, it } from "vitest";

import { backdropClose, newBackdropPress } from "./backdropClose";

/** Ein Ereignis, wie React es liefert: worauf gedrueckt wurde und wo der Griff sitzt. */
function ereignis(target: unknown, currentTarget: unknown) {
  return { target, currentTarget } as never;
}

const HINTERGRUND = { name: "hintergrund" };
const FELD = { name: "eingabefeld" };

describe("backdropClose", () => {
  it("schliesst beim Klick auf den Hintergrund", () => {
    let zu = false;
    const h = backdropClose(newBackdropPress(), () => { zu = true; });
    h.onMouseDown(ereignis(HINTERGRUND, HINTERGRUND));
    h.onClick(ereignis(HINTERGRUND, HINTERGRUND));
    expect(zu).toBe(true);
  });

  it("bleibt offen, wenn das Markieren im Feld begann und daneben endete", () => {
    // Genau der Fall, der genervt hat: der Browser feuert den Klick dann auf dem
    // gemeinsamen Elternteil, also auf dem Hintergrund.
    let zu = false;
    const h = backdropClose(newBackdropPress(), () => { zu = true; });
    h.onMouseDown(ereignis(FELD, HINTERGRUND));
    h.onClick(ereignis(HINTERGRUND, HINTERGRUND));
    expect(zu).toBe(false);
  });

  it("bleibt offen, wenn der Klick den Inhalt trifft", () => {
    let zu = false;
    const h = backdropClose(newBackdropPress(), () => { zu = true; });
    h.onMouseDown(ereignis(FELD, HINTERGRUND));
    h.onClick(ereignis(FELD, HINTERGRUND));
    expect(zu).toBe(false);
  });

  it("vergisst den vorherigen Griff nicht bis zum naechsten Druck", () => {
    // Nach einem Markieren muss ein echter Klick daneben wieder schliessen.
    let zu = 0;
    const press = newBackdropPress();
    const h = backdropClose(press, () => { zu += 1; });
    h.onMouseDown(ereignis(FELD, HINTERGRUND));
    h.onClick(ereignis(HINTERGRUND, HINTERGRUND));
    h.onMouseDown(ereignis(HINTERGRUND, HINTERGRUND));
    h.onClick(ereignis(HINTERGRUND, HINTERGRUND));
    expect(zu).toBe(1);
  });

  it("schliesst nicht, solange es abgeschaltet ist", () => {
    // Fuer Fenster, die waehrend des Speicherns nicht weggehen duerfen.
    let zu = false;
    const press = newBackdropPress();
    const h = backdropClose(press, () => { zu = true; }, false);
    h.onMouseDown(ereignis(HINTERGRUND, HINTERGRUND));
    h.onClick(ereignis(HINTERGRUND, HINTERGRUND));
    expect(zu).toBe(false);
  });
});
